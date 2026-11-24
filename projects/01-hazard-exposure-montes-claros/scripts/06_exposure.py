"""P01 — passo 6: exposição de edificações e população aos perigos.

Regra (DECISIONS 2026-11-24): a edificação está exposta se o seu ponto
representativo cai numa célula (ou polígono) de perigo.

Perigos:
  (a) declividade ≥ 30% (Lei 6.766/79)
  (b) HAND ≤ h, h ∈ {1, 2, 3, 5} m, com drenagem ≥ 1, 2 ou 3 km²
  (c) setores de risco alto/muito alto do SGB 2012
  (any) qualquer perigo, na configuração principal: (a) ou HAND ≤ 3 m (2 km²) ou (c)
  (ref) referência: classes Alta+Média de inundação da carta SGB 2014

Só entram edificações dentro do perímetro urbano.

Saídas (outputs/tables/):
  exposure_summary.csv            perigo × limiar × confiança → edificações, área, população
  sensitivity_hand.csv            HAND: h × limiar de drenagem (confiança 0,75)
  sensitivity_ob_confidence.csv   perigos principais × confiança 0,65/0,70/0,75
  exposure_by_region.csv          por Região de Planejamento (configuração principal)
e as colunas de exposição por edificação em data/processed/p01/buildings_exposure.gpkg

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/06_exposure.py
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from geoportfolio.io import load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]
TABLES = PROJECT_DIR / "outputs" / "tables"


def sample(raster_path, xs, ys):
    """Valor do raster na célula que contém cada ponto (NaN fora da grade)."""
    with rasterio.open(raster_path) as src:
        arr = src.read(1)
        rows, cols = rasterio.transform.rowcol(src.transform, xs, ys)
    rows, cols = np.asarray(rows), np.asarray(cols)
    ok = (rows >= 0) & (rows < arr.shape[0]) & (cols >= 0) & (cols < arr.shape[1])
    out = np.full(len(xs), np.nan, dtype="float32")
    out[ok] = arr[rows[ok], cols[ok]]
    return out


def summarize(b, mask, pop_col, label):
    """Contagem, área construída e população das edificações em `mask`."""
    total_pop = b[pop_col].sum()
    return {
        **label,
        "buildings": int(mask.sum()),
        "buildings_pct": round(100 * mask.mean(), 2),
        "built_area_km2": round(b.loc[mask, "area_in_meters"].sum() / 1e6, 3),
        "population": int(round(b.loc[mask, pop_col].sum())),
        "population_pct": round(100 * b.loc[mask, pop_col].sum() / total_pop, 2),
    }


def main(city: str) -> None:
    cfg = load_config(city)
    th = cfg["thresholds"]
    metric = cfg["crs"]["metric"]
    I = cfg["paths"]["interim_p01"]
    P = cfg["paths"]["processed_p01"]

    b = gpd.read_file(P / "buildings_population.gpkg", layer="buildings")
    b = b[b.inside_aoi].copy()
    pts = b.geometry.representative_point()
    xs, ys = pts.x.to_numpy(), pts.y.to_numpy()

    # --- valores de perigo em cada edificação --------------------------------------
    b["slope_pct"] = sample(I / "slope_pct_glo30.tif", xs, ys)
    for thr in th["stream_threshold_km2"]:
        b[f"hand_acc{thr:g}"] = sample(I / f"hand_glo30_acc{thr:g}km2.tif", xs, ys)

    zip_path = cfg["paths"]["sgb_risk_zip"].as_posix()
    sect = gpd.read_file(f"zip://{zip_path}!Shape/MG_MC_SR_CPRM_atualizado.shp").to_crs(metric)
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=pts, crs=b.crs), sect[["NUM_SETOR", "geometry"]],
                  how="left", predicate="within")
    b["sgb2012_sector"] = j[~j.index.duplicated()]["NUM_SETOR"]

    sgb14 = gpd.read_file(cfg["paths"]["sgb_inundation_2014"]).to_crs(metric)
    sgb14 = sgb14[sgb14["CLASSE"].str[0].isin(["A", "M"])]
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=pts, crs=b.crs), sgb14[["geometry"]], how="left", predicate="within")
    b["sgb2014_inund_high_med"] = ~j[~j.index.duplicated()]["index_right"].isna()

    # --- máscaras principais -------------------------------------------------------
    s_thr, h_main, acc_main = th["slope_pct_legal"], th["hand_m_main"], th["stream_threshold_km2_main"]
    steep = b["slope_pct"] >= s_thr
    flood = b[f"hand_acc{acc_main:g}"] <= h_main
    sector = b["sgb2012_sector"].notna()
    anyh = steep | flood | sector
    b["exp_slope"] = steep
    b["exp_hand"] = flood
    b["exp_sgb2012"] = sector
    b["exp_any"] = anyh

    confs = th["open_buildings_confidence"]
    pop_cols = {c: f"pop_c{int(round(c * 100)):03d}" for c in confs}

    # --- exposure_summary ----------------------------------------------------------
    rows = []
    for c, pc in pop_cols.items():
        bc = b[b.confidence >= c]
        st = bc["slope_pct"] >= s_thr
        se = bc["sgb2012_sector"].notna()
        rows.append(summarize(bc, pd.Series(True, index=bc.index), pc,
                              {"hazard": "all buildings in perimeter", "parameter": "", "confidence_min": c}))
        rows.append(summarize(bc, st, pc, {"hazard": "slope", "parameter": f">= {s_thr}%", "confidence_min": c}))
        for thr in th["stream_threshold_km2"]:
            for h in th["hand_m"]:
                rows.append(summarize(bc, bc[f"hand_acc{thr:g}"] <= h, pc,
                                      {"hazard": "flood-prone (HAND)", "parameter": f"HAND <= {h} m; streams >= {thr:g} km2",
                                       "confidence_min": c}))
        rows.append(summarize(bc, se, pc, {"hazard": "SGB 2012 risk sector", "parameter": "high (4 sectors)", "confidence_min": c}))
        fl = bc[f"hand_acc{acc_main:g}"] <= h_main
        rows.append(summarize(bc, st | fl | se, pc,
                              {"hazard": "any hazard", "parameter": f"slope >= {s_thr}% or HAND <= {h_main} m ({acc_main:g} km2) or SGB 2012",
                               "confidence_min": c}))
        rows.append(summarize(bc, bc["sgb2014_inund_high_med"], pc,
                              {"hazard": "reference: SGB 2014 inundation", "parameter": "Alta + Media", "confidence_min": c}))
    t = pd.DataFrame(rows)
    t.to_csv(TABLES / "exposure_summary.csv", index=False)

    main_c = th["open_buildings_confidence_main"]
    tm = t[t.confidence_min == main_c]
    print(f"Exposição (confiança ≥ {main_c}), perigos principais:")
    key = tm[tm.hazard.isin(["all buildings in perimeter", "slope", "SGB 2012 risk sector", "any hazard",
                             "reference: SGB 2014 inundation"])
             | (tm.parameter == f"HAND <= {h_main} m; streams >= {acc_main:g} km2")]
    print(key.drop(columns="confidence_min").to_string(index=False))

    # --- sensibilidades ------------------------------------------------------------
    sh = tm[tm.hazard == "flood-prone (HAND)"].copy()
    sh[["hand_m", "stream_threshold_km2"]] = sh.parameter.str.extract(r"HAND <= (\d+) m; streams >= ([\d.]+)").astype(float)
    sh = sh[["hand_m", "stream_threshold_km2", "buildings", "built_area_km2", "population", "population_pct"]]
    sh.to_csv(TABLES / "sensitivity_hand.csv", index=False)
    print("\nSensibilidade HAND (população exposta):")
    print(sh.pivot(index="hand_m", columns="stream_threshold_km2", values="population").to_string())

    main_haz = (t.hazard.isin(["slope", "SGB 2012 risk sector", "any hazard"])
                | (t.parameter == f"HAND <= {h_main} m; streams >= {acc_main:g} km2"))
    so = t[main_haz][["hazard", "parameter", "confidence_min", "buildings", "built_area_km2", "population"]]
    so.to_csv(TABLES / "sensitivity_ob_confidence.csv", index=False)
    print("\nSensibilidade à confiança do Open Buildings:")
    print(so.pivot_table(index="hazard", columns="confidence_min", values=["buildings", "population"]).to_string())

    # --- por Região de Planejamento (configuração principal) -----------------------
    pc = pop_cols[main_c]
    bc = b[b.confidence >= main_c]
    g = bc.groupby("region")
    reg = pd.DataFrame({
        "buildings": g.size(),
        "population": g[pc].sum(),
        "pop_slope": g.apply(lambda d: d.loc[d.exp_slope, pc].sum()),
        "pop_flood_hand": g.apply(lambda d: d.loc[d.exp_hand, pc].sum()),
        "pop_sgb2012": g.apply(lambda d: d.loc[d.exp_sgb2012, pc].sum()),
        "pop_any": g.apply(lambda d: d.loc[d.exp_any, pc].sum()),
        "buildings_any": g["exp_any"].sum(),
    })
    reg["pop_any_pct"] = 100 * reg.pop_any / reg.population
    reg = reg.round(1).sort_values("pop_any", ascending=False)
    reg.to_csv(TABLES / "exposure_by_region.csv")
    print("\nPor Região de Planejamento (confiança 0,75):")
    print(reg.to_string())
    print(f"edificações sem região: {bc.region.isna().sum()}")

    # --- saída por edificação ------------------------------------------------------
    b.to_file(P / "buildings_exposure.gpkg", layer="buildings", driver="GPKG")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
