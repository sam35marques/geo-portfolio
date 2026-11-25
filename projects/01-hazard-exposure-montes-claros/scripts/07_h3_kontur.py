"""P01 — passo 7: agregação em H3 r8 e comparação Kontur Population × Censo 2022.

O que faz:
1. descompacta a Kontur Population (gpkg.gz) para data/interim/shared (uma vez);
2. lê só os hexágonos da área do export e mantém os de centro dentro do perímetro;
3. soma a população dasimétrica (Censo 2022 nas edificações, confiança 0,75)
   e a população exposta (qualquer perigo e HAND ≤ 3 m) por célula H3 r8;
4. compara Kontur × dasimetria por célula: totais, correlação, erro absoluto,
   viés por faixa de densidade;
5. grava outputs/exposure_h3_r8.gpkg (só agregados) e as tabelas
   h3_population_comparison.csv, kontur_vs_census_summary.csv,
   kontur_vs_census_by_density.csv.

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/07_h3_kontur.py
"""

import argparse
import gzip
import shutil
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import box

from geoportfolio.h3utils import cells_to_gdf, points_to_h3
from geoportfolio.io import load_aoi, load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]


def main(city: str) -> None:
    cfg = load_config(city)
    th = cfg["thresholds"]
    res = cfg["h3"]["resolution"]
    P = cfg["paths"]["processed_p01"]
    TABLES = cfg["paths"]["outputs_p01"] / "tables"
    pc = f"pop_c{int(round(th['open_buildings_confidence_main'] * 100)):03d}"

    # --- 1. Kontur ----------------------------------------------------------------
    gz = cfg["paths"]["kontur"]
    kpath = cfg["paths"]["interim"] / "shared" / gz.name.removesuffix(".gz")
    if not kpath.exists():
        kpath.parent.mkdir(parents=True, exist_ok=True)
        print(f"Descompactando {gz.name} ...")
        with gzip.open(gz, "rb") as fi, open(kpath, "wb") as fo:
            shutil.copyfileobj(fi, fo, length=1 << 20)

    # --- 2. Hexágonos de centro dentro do perímetro --------------------------------
    aoi = load_aoi(cfg, to_crs="EPSG:4326")
    bbox = box(*cfg["open_buildings_export_bbox_4326"])
    kontur = gpd.read_file(kpath, bbox=gpd.GeoSeries([bbox], crs=4326).to_crs(3857).iloc[0].bounds)
    print(f"Kontur: {len(kontur):,} hexágonos lidos | colunas: {list(kontur.columns)}")
    kontur = kontur[["h3", "population"]].rename(columns={"population": "pop_kontur"})
    assert all(h3.get_resolution(c) == res for c in kontur.h3.head(50)), "resolução H3 inesperada"

    poly = aoi.geometry.iloc[0]
    # células cujo centro cai no perímetro (mesma regra do h3.geo_to_cells)
    cells = set(h3.geo_to_cells(poly, res))
    # só células totalmente dentro do retângulo do export (para a dasimetria ser completa)
    hexes = cells_to_gdf(sorted(cells))
    hexes = hexes[hexes.within(bbox)]
    print(f"Células H3 r{res} com centro no perímetro e dentro do export: {len(hexes):,}")

    # --- 3. Dasimetria e exposição por célula ---------------------------------------
    b = gpd.read_file(P / "buildings_population.gpkg", layer="buildings")
    b = b[b.confidence >= th["open_buildings_confidence_main"]]
    b["h3"] = points_to_h3(b, res)
    e = gpd.read_file(P / "buildings_exposure.gpkg", layer="buildings", ignore_geometry=True)
    e = e[e.confidence >= th["open_buildings_confidence_main"]][["ob_id", "exp_any", "exp_hand", "exp_slope"]]
    b = b.merge(e, on="ob_id", how="left")
    for c in ["exp_any", "exp_hand", "exp_slope"]:
        b[c] = b[c].fillna(False).astype(bool)

    agg = b.groupby("h3").agg(
        buildings=("ob_id", "size"),
        pop_census=(pc, "sum"),
        pop_exposed_any=(pc, lambda s: s[b.loc[s.index, "exp_any"]].sum()),
        pop_exposed_flood=(pc, lambda s: s[b.loc[s.index, "exp_hand"]].sum()),
        pop_exposed_slope=(pc, lambda s: s[b.loc[s.index, "exp_slope"]].sum()),
        buildings_exposed_any=("exp_any", "sum"),
    )
    hexes = hexes.merge(agg, left_on="h3", right_index=True, how="left").merge(kontur, on="h3", how="left")
    num = ["buildings", "pop_census", "pop_exposed_any", "pop_exposed_flood", "pop_exposed_slope",
           "buildings_exposed_any", "pop_kontur"]
    hexes[num] = hexes[num].fillna(0)
    hexes["diff_kontur_minus_census"] = hexes.pop_kontur - hexes.pop_census
    hexes["share_exposed_any"] = np.where(hexes.pop_census > 0, hexes.pop_exposed_any / hexes.pop_census, 0)

    out_gpkg = cfg["paths"]["outputs_p01"] / "exposure_h3_r8.gpkg"
    hexes.round(2).to_file(out_gpkg, layer="h3_r8", driver="GPKG")
    hexes.drop(columns="geometry").round(2).to_csv(TABLES / "h3_population_comparison.csv", index=False)

    # --- 4. Kontur × Censo --------------------------------------------------------
    x, y = hexes.pop_census.to_numpy(), hexes.pop_kontur.to_numpy()
    both = (x > 0) | (y > 0)
    r = np.corrcoef(x[both], y[both])[0, 1]
    summ = pd.DataFrame([{
        "h3_resolution": res,
        "cells": int(len(hexes)),
        "cells_with_population": int(both.sum()),
        "pop_census_dasymetric": int(round(x.sum())),
        "pop_kontur_2023": int(round(y.sum())),
        "total_ratio_kontur_over_census": round(y.sum() / x.sum(), 3),
        "pearson_r": round(r, 3),
        "r2": round(r * r, 3),
        "mae_per_cell": round(np.mean(np.abs(y - x)[both]), 1),
        "median_abs_diff_per_cell": round(np.median(np.abs(y - x)[both]), 1),
        "share_abs_diff_of_total_pct": round(100 * np.abs(y - x).sum() / x.sum(), 1),
        "cells_kontur_zero_census_pos": int(((y == 0) & (x > 0)).sum()),
        "cells_kontur_pos_census_zero": int(((y > 0) & (x == 0)).sum()),
    }])
    summ.to_csv(TABLES / "kontur_vs_census_summary.csv", index=False)
    print("\nKontur × Censo (dasimetria), H3 r8 dentro do perímetro:")
    print(summ.T.to_string())

    # viés por faixa de densidade (população do Censo por célula)
    bins = [-0.1, 0, 500, 1500, 3000, np.inf]
    labels = ["0", "1-500", "501-1500", "1501-3000", ">3000"]
    hexes["census_band"] = pd.cut(hexes.pop_census, bins=bins, labels=labels)
    dens = hexes.groupby("census_band", observed=False).agg(
        cells=("h3", "size"), pop_census=("pop_census", "sum"), pop_kontur=("pop_kontur", "sum"))
    dens[["pop_census", "pop_kontur"]] = dens[["pop_census", "pop_kontur"]].round(0)
    dens["ratio_kontur_over_census"] = (dens.pop_kontur / dens.pop_census.replace(0, np.nan)).round(3)
    dens.to_csv(TABLES / "kontur_vs_census_by_density.csv")
    print("\nPor faixa de população do Censo por célula:")
    print(dens.to_string())

    print(f"\nPopulação exposta (qualquer perigo) somada nas células: {hexes.pop_exposed_any.sum():,.0f}")
    print(f"-> {out_gpkg}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
