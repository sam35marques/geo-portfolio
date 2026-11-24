"""P01 — passo 5: edificações e população dasimétrica.

O que faz:
1. lê o CSV do Open Buildings (export do GEE) e reprojeta para EPSG:31983;
2. atribui cada edificação a um setor censitário 2022 e a uma Região de
   Planejamento, pelo ponto representativo do polígono;
3. para cada limiar de confiança (0,65 / 0,70 / 0,75), distribui a população
   do setor (v0001) entre as edificações do setor, proporcional à área;
4. marca as edificações dentro do perímetro urbano;
5. grava data/processed/p01/buildings_population.gpkg e a tabela
   outputs/tables/dasymetric_summary.csv.

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/05_buildings_population.py
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from geoportfolio.exposure import assign_by_point, dasymetric_population, read_open_buildings_csv
from geoportfolio.io import load_aoi, load_config, load_planning_regions

PROJECT_DIR = Path(__file__).resolve().parents[1]


def main(city: str) -> None:
    cfg = load_config(city)
    metric = cfg["crs"]["metric"]
    confs = cfg["thresholds"]["open_buildings_confidence"]
    out_dir = cfg["paths"]["processed_p01"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Edificações -----------------------------------------------------------
    b = read_open_buildings_csv(cfg["paths"]["open_buildings"], metric)
    print(f"Open Buildings lidas: {len(b):,} | confiança mín. {b.confidence.min():.3f}")

    # --- 2. Setores e regiões -----------------------------------------------------
    code = str(cfg["city"]["ibge_code"])
    tracts = gpd.read_file(cfg["paths"]["census_tracts"], where=f"CD_MUN = '{code}'").to_crs(metric)
    tracts["pop"] = pd.to_numeric(tracts["v0001"], errors="coerce").fillna(0)
    # O export do GEE cobre só um retângulo em volta do perímetro. Setores que
    # saem dele teriam toda a população jogada nas poucas edificações exportadas.
    # Correção: usa só a fração da população proporcional à área coberta
    # (premissa: densidade uniforme na parte não coberta).
    bbox = gpd.GeoSeries([box(*cfg["open_buildings_export_bbox_4326"])], crs="EPSG:4326").to_crs(metric).iloc[0]
    tracts["frac_covered"] = (tracts.geometry.intersection(bbox).area / tracts.area).clip(0, 1)
    tracts["pop_covered"] = tracts["pop"] * tracts["frac_covered"]
    n_cut = int((tracts.frac_covered < 0.999).sum())
    print(f"Setores parcialmente fora do export: {n_cut} | pop. descontada: "
          f"{tracts['pop'].sum() - tracts['pop_covered'].sum():,.0f}")
    tract_pop = tracts.set_index("CD_SETOR")["pop_covered"]

    b["tract"] = assign_by_point(b, tracts, ["CD_SETOR"])["CD_SETOR"]
    regions = load_planning_regions(cfg)
    b["region"] = assign_by_point(b, regions, ["region"])["region"]
    aoi = load_aoi(cfg)
    b["inside_aoi"] = b.geometry.representative_point().within(aoi.geometry.iloc[0])
    print(f"Fora de qualquer setor do município: {b.tract.isna().sum():,} "
          f"| dentro do perímetro: {b.inside_aoi.sum():,}")

    # --- 3. Dasimetria por limiar de confiança ----------------------------------------
    rows = []
    for c in confs:
        col = f"pop_c{int(round(c * 100)):03d}"
        sel = (b.confidence >= c) & b.tract.notna()
        b[col] = 0.0
        b.loc[sel, col] = dasymetric_population(b.loc[sel], "tract", "area_in_meters", tract_pop)

        tracts_with_b = set(b.loc[sel, "tract"])
        lost = tracts[(tracts["pop_covered"] > 0.5) & ~tracts.CD_SETOR.isin(tracts_with_b)]
        in_aoi = sel & b.inside_aoi
        rows.append({
            "confidence_min": c,
            "buildings_municipality": int(sel.sum()),
            "buildings_in_perimeter": int(in_aoi.sum()),
            "built_area_in_perimeter_km2": round(b.loc[in_aoi, "area_in_meters"].sum() / 1e6, 2),
            "population_municipality_census": int(tracts["pop"].sum()),
            "population_in_export_extent": int(round(tracts["pop_covered"].sum())),
            "population_allocated_municipality": int(round(b[col].sum())),
            "population_in_perimeter": int(round(b.loc[in_aoi, col].sum())),
            "tracts_with_pop_but_no_buildings": len(lost),
            "population_not_allocated": int(round(lost["pop_covered"].sum())),
        })
    t = pd.DataFrame(rows)
    out_tab = PROJECT_DIR / "outputs" / "tables" / "dasymetric_summary.csv"
    t.to_csv(out_tab, index=False)
    print(t.T.to_string())

    # --- 4. Saída ---------------------------------------------------------------------
    keep = ["ob_id", "area_in_meters", "confidence", "tract", "region", "inside_aoi"] + \
           [f"pop_c{int(round(c * 100)):03d}" for c in confs] + ["geometry"]
    out = out_dir / "buildings_population.gpkg"
    b[keep].to_file(out, layer="buildings", driver="GPKG")
    print(f"-> {out}\n-> {out_tab}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
