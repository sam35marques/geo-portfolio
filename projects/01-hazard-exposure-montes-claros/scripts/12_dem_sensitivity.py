"""P01 — passo 12: sensibilidade dos resultados ao MDE (GLO-30 x ALOS RTC x FABDEM).

Pergunta: quanto a exposição muda se trocarmos o MDE principal (Copernicus
GLO-30, modelo de SUPERFÍCIE) por outro MDE aberto?

  - ALOS PALSAR RTC: 12,5 m nominal, mas reamostrado de um SRTM de ~30 m;
  - FABDEM V1-2: GLO-30 com árvores e prédios removidos (terreno nu, 30 m).

Para cada MDE alternativo (config: terrain.sensitivity_dems), a cadeia é a
MESMA do fluxo principal (passos 3, 4 e 6):
  1. reprojeta para EPSG:31983 a 30 m, na mesma grade do GLO-30 (comparação célula a célula);
  2. declividade (Horn) e roteamento de fluxo (pysheds);
  3. HAND com drenagem ≥ 2 km² (limiar principal) e h ∈ {1, 2, 3, 5} m;
  4. amostra no ponto representativo das edificações (confiança 0,75) e soma a população.

O GLO-30 entra como referência, lido dos rasters do passo 3/4 (não é recalculado),
de modo que os números dele batem com exposure_summary.csv.

Saídas (outputs/tables/):
  dem_sensitivity_exposure.csv    MDE × perigo × limiar → área, edificações, população
  dem_sensitivity_vs_sgb2014.csv  MDE × h → concordância do HAND com a carta SGB 2014
  dem_sensitivity_agreement.csv   MDE → diferença de altitude e sobreposição das zonas com o GLO-30

Os rasters derivados ficam em data/interim/p01/ e NÃO são publicados
(o FABDEM tem licença não comercial; ver DATA_SOURCES.md).

Rodar da raiz do repositório (depois de 03, 04, 05 e 06):
    python projects/01-hazard-exposure-montes-claros/scripts/12_dem_sensitivity.py
"""

import argparse
from glob import glob
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask, rasterize

from geoportfolio import terrain
from geoportfolio.io import has_layer, load_aoi, load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]


def read(path):
    with rasterio.open(path) as src:
        return src.read(1)


def jaccard(a, b):
    """Sobreposição de duas zonas: área da interseção / área da união (0–100%)."""
    union = (a | b).sum()
    return round(100 * (a & b).sum() / union, 1) if union else np.nan


def build_dem(name, files, ref_path, I, cell_km2, acc_thr):
    """Reprojeta o MDE alternativo para a grade do GLO-30 e calcula declividade e HAND.

    Retorna (dem, slope, hand) como matrizes na grade de referência.
    """
    with rasterio.open(ref_path) as ref:
        bounds, crs, res = ref.bounds, ref.crs, ref.res[0]
    dem_path = I / f"dem_{name}_31983_30m.tif"
    # mesmos limites (já alinhados a 30 m) => mesma grade do GLO-30
    terrain.mosaic_reproject(files, tuple(bounds), crs.to_string(), res, dem_path)
    with rasterio.open(dem_path) as src:
        dem, transform = src.read(1), src.transform
    slope = terrain.slope_percent(dem, res)
    terrain.write_raster(slope, I / f"slope_pct_{name}.tif", transform, crs)

    grid, dem_cond, fdir, acc = terrain.flow_routing(dem_path)
    acc_km2 = np.asarray(acc, dtype="float64") * cell_km2
    hand = np.asarray(terrain.compute_hand(grid, dem_cond, fdir, acc_km2 >= acc_thr), dtype="float32")
    terrain.write_raster(hand, I / f"hand_{name}_acc{acc_thr:g}km2.tif", transform, crs)
    return dem, slope, hand


def main(city: str) -> None:
    cfg = load_config(city)
    th = cfg["thresholds"]
    root = cfg["paths"]["root"]
    metric = cfg["crs"]["metric"]
    I = cfg["paths"]["interim_p01"]
    P = cfg["paths"]["processed_p01"]
    TABLES = cfg["paths"]["outputs_p01"] / "tables"
    res = cfg["terrain"]["resolution_m"]
    cell_km2 = res * res / 1e6
    acc_thr, h_main, s_thr = th["stream_threshold_km2_main"], th["hand_m_main"], th["slope_pct_legal"]
    conf = th["open_buildings_confidence_main"]
    pop_col = f"pop_c{int(round(conf * 100)):03d}"

    # --- grade de referência (GLO-30) e máscaras -----------------------------------
    ref_path = I / "dem_glo30_31983_30m.tif"
    with rasterio.open(ref_path) as src:
        shape, transform = src.shape, src.transform
    aoi = load_aoi(cfg)
    inside = geometry_mask(aoi.geometry, out_shape=shape, transform=transform, invert=True)

    has_sgb = has_layer(cfg, "sgb_inundation_2014")
    sgb_codes = np.zeros(shape, dtype="uint8")   # sem carta do SGB: tabela de concordância não é escrita
    if has_sgb:
        sgb = gpd.read_file(cfg["paths"]["sgb_inundation_2014"]).to_crs(metric)
        sgb["code"] = sgb["CLASSE"].str[0].map({"A": 3, "M": 2, "B": 1})
        sgb_codes = rasterize(((g, c) for g, c in zip(sgb.geometry, sgb["code"]) if c == c),
                              out_shape=shape, transform=transform, fill=0, dtype="uint8")
    sgb_high = inside & (sgb_codes == 3)
    sgb_hm = inside & (sgb_codes >= 2)
    sgb_any = inside & (sgb_codes >= 1)

    # edificações: mesma seleção do passo 6 (dentro do perímetro, confiança principal)
    b = gpd.read_file(P / "buildings_exposure.gpkg", layer="buildings")
    b = b[b.confidence >= conf].copy()
    pts = b.geometry.representative_point()
    rows_b, cols_b = rasterio.transform.rowcol(transform, pts.x.to_numpy(), pts.y.to_numpy())
    rows_b, cols_b = np.asarray(rows_b), np.asarray(cols_b)
    pop = b[pop_col].to_numpy()
    total_pop = pop.sum()
    sector = b["sgb2012_sector"].notna().to_numpy()

    # --- MDEs: referência + alternativos ---------------------------------------------
    dems = {"glo30": {"label": "Copernicus GLO-30 (main)",
                      "dem": read(ref_path),
                      "slope": read(I / "slope_pct_glo30.tif"),
                      "hand": read(I / f"hand_glo30_acc{acc_thr:g}km2.tif")}}
    for name, spec in cfg["terrain"]["sensitivity_dems"].items():
        files = sorted(Path(p) for p in glob(str(root / spec["files"])))
        if not files:
            print(f"AVISO: {name} pulado (nenhum arquivo em {spec['files']})")
            continue
        print(f"Processando {name}: {len(files)} arquivo(s)…")
        dem, slope, hand = build_dem(name, files, ref_path, I, cell_km2, acc_thr)
        dems[name] = {"label": spec["label"], "dem": dem, "slope": slope, "hand": hand}

    # --- tabelas -----------------------------------------------------------------
    exp_rows, sgb_rows, agr_rows = [], [], []
    g = dems["glo30"]
    g_steep = inside & (g["slope"] >= s_thr)
    g_flood = inside & (g["hand"] <= h_main)
    for name, d in dems.items():
        slope_b = d["slope"][rows_b, cols_b]
        hand_b = d["hand"][rows_b, cols_b]

        def add(hazard, parameter, zone, mask_b):
            exp_rows.append({
                "dem": name, "dem_label": d["label"], "hazard": hazard, "parameter": parameter,
                "area_km2": round(zone.sum() * cell_km2, 2) if zone is not None else np.nan,
                "buildings": int(mask_b.sum()),
                "population": int(round(pop[mask_b].sum())),
                "population_pct": round(100 * pop[mask_b].sum() / total_pop, 2),
            })

        steep_zone = inside & (d["slope"] >= s_thr)
        add("slope", f">= {s_thr}%", steep_zone, slope_b >= s_thr)
        for h in th["hand_m"]:
            add("flood-prone (HAND)", f"HAND <= {h} m; streams >= {acc_thr:g} km2",
                inside & (d["hand"] <= h), hand_b <= h)
        add("any hazard", f"slope >= {s_thr}% or HAND <= {h_main} m ({acc_thr:g} km2)"
            + (" or SGB 2012" if sector.any() else ""),
            None, (slope_b >= s_thr) | (hand_b <= h_main) | sector)

        for h in th["hand_m"]:
            sel = inside & (d["hand"] <= h)
            sgb_rows.append({
                "dem": name, "hand_m": h, "hand_area_km2": round(sel.sum() * cell_km2, 2),
                "sgb_high_capture_pct": round(100 * (sel & sgb_high).sum() / max(sgb_high.sum(), 1), 1),
                "sgb_high_medium_capture_pct": round(100 * (sel & sgb_hm).sum() / max(sgb_hm.sum(), 1), 1),
                "hand_in_sgb_any_pct": round(100 * (sel & sgb_any).sum() / max(sel.sum(), 1), 1),
            })

        # diferença de altitude em relação ao GLO-30, dentro do perímetro
        diff = (d["dem"] - g["dem"])[inside]
        diff = diff[np.isfinite(diff)]
        agr_rows.append({
            "dem": name, "dem_label": d["label"],
            "elev_diff_mean_m": round(float(diff.mean()), 2),
            "elev_diff_median_m": round(float(np.median(diff)), 2),
            "elev_diff_sd_m": round(float(diff.std()), 2),
            "elev_diff_abs_p95_m": round(float(np.percentile(np.abs(diff), 95)), 2),
            f"steep_ge_{s_thr}pct_jaccard_vs_glo30_pct": jaccard(steep_zone, g_steep),
            f"hand_le_{h_main}m_jaccard_vs_glo30_pct": jaccard(inside & (d["hand"] <= h_main), g_flood),
            f"hand_le_{h_main}m_share_inside_glo30_zone_pct":
                round(100 * ((inside & (d["hand"] <= h_main)) & g_flood).sum()
                      / max((inside & (d["hand"] <= h_main)).sum(), 1), 1),
        })

    t_exp = pd.DataFrame(exp_rows)
    t_sgb = pd.DataFrame(sgb_rows)
    t_agr = pd.DataFrame(agr_rows)
    t_exp.to_csv(TABLES / "dem_sensitivity_exposure.csv", index=False)
    if has_sgb:
        t_sgb.to_csv(TABLES / "dem_sensitivity_vs_sgb2014.csv", index=False)
    t_agr.to_csv(TABLES / "dem_sensitivity_agreement.csv", index=False)

    print("\nPopulação exposta por MDE:")
    print(t_exp.pivot_table(index=["hazard", "parameter"], columns="dem", values="population",
                            sort=False).to_string())
    print("\nÁrea (km²) por MDE:")
    print(t_exp.pivot_table(index=["hazard", "parameter"], columns="dem", values="area_km2",
                            sort=False).to_string())
    if has_sgb:
        print("\nHAND x SGB 2014:")
        print(t_sgb.to_string(index=False))
    print("\nConcordância com o GLO-30:")
    print(t_agr.drop(columns="dem_label").to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
