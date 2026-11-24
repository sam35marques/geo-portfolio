"""P01 — passo 3: MDE, declividade, fluxo e escolha do limiar de drenagem.

O que faz:
1. junta os tiles do Copernicus GLO-30 e reprojeta para EPSG:31983 a 30 m,
   num domínio = perímetro urbano + buffer (config: terrain.domain_buffer_m);
2. calcula a declividade (%) pelo método de Horn;
3. condiciona o MDE e calcula direção (D8) e acumulação de fluxo (pysheds);
4. para cada limiar candidato de área de contribuição, compara a rede de
   drenagem derivada com os córregos mapeados no Atlas Hidrográfico,
   dentro do perímetro urbano:
     - recall    = % do comprimento dos córregos do Atlas a até X m da rede derivada
     - precision = % das células da rede derivada a até X m de um córrego do Atlas
     - razão de comprimento = rede derivada / Atlas
   -> outputs/tables/stream_threshold_vs_atlas.csv

O HAND é calculado no passo 4, depois de fixado o limiar (DECISIONS.md).

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/03_terrain.py
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask, rasterize
from scipy.ndimage import distance_transform_edt

from geoportfolio import terrain
from geoportfolio.io import load_aoi, load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]


def main(city: str) -> None:
    cfg = load_config(city)
    tcfg = cfg["terrain"]
    metric = cfg["crs"]["metric"]
    res = tcfg["resolution_m"]
    out_dir = cfg["paths"]["interim_p01"]
    out_dir.mkdir(parents=True, exist_ok=True)

    aoi = load_aoi(cfg)
    domain = aoi.buffer(tcfg["domain_buffer_m"])

    # --- 1. MDE no domínio ------------------------------------------------------
    tiles = sorted(Path(cfg["paths"]["glo30_dir"]).glob("*.tif"))
    dem_path = out_dir / "dem_glo30_31983_30m.tif"
    terrain.mosaic_reproject(tiles, tuple(domain.total_bounds), metric, res, dem_path)
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        transform, crs = src.transform, src.crs
    print(f"MDE: {dem.shape[1]} x {dem.shape[0]} células, "
          f"{np.nanmin(dem):.0f}–{np.nanmax(dem):.0f} m, NaN = {np.isnan(dem).mean():.2%}")

    # máscara do perímetro urbano na grade (True = dentro)
    inside = geometry_mask(aoi.geometry, out_shape=dem.shape, transform=transform, invert=True)

    # --- 2. Declividade ---------------------------------------------------------
    slope = terrain.slope_percent(dem, res)
    terrain.write_raster(slope, out_dir / "slope_pct_glo30.tif", transform, crs)
    s_in = slope[inside & np.isfinite(slope)]
    thr_slope = cfg["thresholds"]["slope_pct_legal"]
    print(f"Declividade no perímetro: mediana {np.median(s_in):.1f}%, "
          f"p95 {np.percentile(s_in, 95):.1f}%, ≥{thr_slope}%: {np.mean(s_in >= thr_slope):.2%} da área")

    # --- 3. Fluxo ---------------------------------------------------------------
    grid, dem_cond, fdir, acc = terrain.flow_routing(dem_path)
    acc_km2 = np.asarray(acc, dtype="float64") * (res * res) / 1e6
    terrain.write_raster(np.asarray(dem_cond, dtype="float32"), out_dir / "dem_glo30_conditioned.tif", transform, crs)
    terrain.write_raster(np.asarray(fdir).astype("int16"), out_dir / "flowdir_d8_glo30.tif", transform, crs, nodata=0)
    terrain.write_raster(acc_km2.astype("float32"), out_dir / "flowacc_km2_glo30.tif", transform, crs)
    print(f"Acumulação máxima: {acc_km2.max():,.0f} km²")

    # --- 4. Limiar de drenagem x Atlas ------------------------------------------
    atlas = gpd.read_file(cfg["paths"]["atlas_streams"]).to_crs(metric)
    atlas_in = atlas.clip(aoi)
    atlas_len_km = atlas_in.length.sum() / 1000
    # pontos a cada 10 m ao longo dos córregos do Atlas (para medir comprimento)
    pts, kinds = [], []
    for geom, kind in zip(atlas_in.geometry, atlas_in["TIPO_CURSO"].fillna("unknown")):
        for line in getattr(geom, "geoms", [geom]):
            n = max(int(line.length // 10), 1)
            pts += [line.interpolate(d) for d in np.linspace(0, line.length, n + 1)]
            kinds += [kind] * (n + 1)
    rows, cols = rasterio.transform.rowcol(transform, [p.x for p in pts], [p.y for p in pts])
    rows, cols = np.asarray(rows), np.asarray(cols)
    kinds = np.asarray(kinds)

    # distância (m) de cada célula ao córrego do Atlas mais próximo
    atlas_mask = rasterize(((g, 1) for g in atlas_in.geometry), out_shape=dem.shape,
                           transform=transform, fill=0, all_touched=True).astype(bool)
    dist_to_atlas = distance_transform_edt(~atlas_mask) * res

    tol = tcfg["stream_match_tolerance_m"]
    rows_out = []
    for thr in tcfg["stream_threshold_candidates_km2"]:
        streams = acc_km2 >= thr
        dist_to_derived = distance_transform_edt(~streams) * res
        hit = dist_to_derived[rows, cols] <= tol
        recall = np.mean(hit)
        recall_natural = np.mean(hit[kinds == "natural"])
        recall_canal = np.mean(hit[kinds == "canalizado"])
        # mediana da distância dos córregos do Atlas à rede derivada (desencontro de posição)
        median_offset = np.median(dist_to_derived[rows, cols])
        cells_in = streams & inside
        precision = np.mean(dist_to_atlas[cells_in] <= tol) if cells_in.any() else np.nan
        # comprimento aproximado: nº de células × resolução × 1,1 (fator médio p/ diagonais)
        derived_len_km = cells_in.sum() * res * 1.1 / 1000
        f1 = 2 * precision * recall / (precision + recall)
        rows_out.append({
            "threshold_km2": thr,
            "derived_length_km": round(derived_len_km, 1),
            "atlas_length_km": round(atlas_len_km, 1),
            "length_ratio": round(derived_len_km / atlas_len_km, 2),
            "recall_pct": round(100 * recall, 1),
            "recall_natural_pct": round(100 * recall_natural, 1),
            "recall_canalized_pct": round(100 * recall_canal, 1),
            "median_offset_m": round(float(median_offset), 1),
            "precision_pct": round(100 * precision, 1),
            "f1_pct": round(100 * f1, 1),
            "tolerance_m": tol,
        })
    tab = pd.DataFrame(rows_out)
    out_tab = PROJECT_DIR / "outputs" / "tables" / "stream_threshold_vs_atlas.csv"
    tab.to_csv(out_tab, index=False)
    print("\nLimiar de drenagem x córregos do Atlas (dentro do perímetro):")
    print(tab.to_string(index=False))
    print(f"-> {out_tab}")

    # resumo do terreno (todo número citado sai de uma tabela)
    summary = pd.DataFrame([{
        "dem": "Copernicus GLO-30", "crs": metric, "pixel_m": res,
        "domain_buffer_m": tcfg["domain_buffer_m"],
        "slope_median_pct_in_aoi": round(float(np.median(s_in)), 2),
        "slope_p95_pct_in_aoi": round(float(np.percentile(s_in, 95)), 2),
        f"area_slope_ge_{thr_slope}pct_in_aoi_pct": round(100 * float(np.mean(s_in >= thr_slope)), 2),
        f"area_slope_ge_{thr_slope}pct_in_aoi_km2": round(float(np.sum(s_in >= thr_slope)) * res * res / 1e6, 2),
        "atlas_stream_length_in_aoi_km": round(atlas_len_km, 2),
    }])
    summary.to_csv(PROJECT_DIR / "outputs" / "tables" / "terrain_summary_glo30.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
