"""P01 — passo 4: HAND e concordância com as referências do SGB.

O que faz:
1. refaz o roteamento de fluxo no MDE GLO-30 do passo 3 (mesmo resultado);
2. calcula o HAND para cada limiar de drenagem (config: thresholds.stream_threshold_km2)
   -> data/interim/p01/hand_glo30_acc{X}km2.tif
3. mede, dentro do perímetro urbano, a área com HAND ≤ h para h em {1, 2, 3, 5} m;
4. compara HAND ≤ h com a carta de suscetibilidade a inundação do SGB (2014):
     - sgb_capture_pct  = % da área SGB (classes Alta+Média, ≤ 3 m na legenda)
                          que cai em HAND ≤ h
     - hand_in_sgb_pct  = % da área HAND ≤ h que cai em qualquer classe SGB
   (concordância com um produto oficial, NÃO validação independente: ver DECISIONS)
5. compara declividade ≥ 30% com a suscetibilidade a movimento de massa (SGB 2014);
6. checagem qualitativa com os 4 setores de risco SGB 2012.

Saídas em outputs/tables/: hand_area_sensitivity.csv, hand_vs_sgb2014.csv,
slope_vs_sgb2014.csv, sgb2012_sectors_check.csv

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/04_hand.py
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask, rasterize

from geoportfolio import terrain
from geoportfolio.io import load_aoi, load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]
TABLES = PROJECT_DIR / "outputs" / "tables"


def rasterize_classes(gdf, field, mapping, shape, transform):
    """Rasteriza polígonos em códigos inteiros (0 = fora). Célula pelo centro."""
    shapes = ((g, mapping[v]) for g, v in zip(gdf.geometry, gdf[field]) if v in mapping)
    return rasterize(shapes, out_shape=shape, transform=transform, fill=0, dtype="uint8")


def main(city: str) -> None:
    cfg = load_config(city)
    th = cfg["thresholds"]
    res = cfg["terrain"]["resolution_m"]
    metric = cfg["crs"]["metric"]
    I = cfg["paths"]["interim_p01"]
    cell_km2 = res * res / 1e6

    aoi = load_aoi(cfg)
    dem_path = I / "dem_glo30_31983_30m.tif"
    with rasterio.open(dem_path) as src:
        shape, transform, crs = src.shape, src.transform, src.crs
    inside = geometry_mask(aoi.geometry, out_shape=shape, transform=transform, invert=True)
    with rasterio.open(I / "slope_pct_glo30.tif") as src:
        slope = src.read(1)

    # --- 1-2. Fluxo e HAND por limiar ---------------------------------------------
    grid, dem_cond, fdir, acc = terrain.flow_routing(dem_path)
    acc_km2 = np.asarray(acc, dtype="float64") * cell_km2
    hands = {}
    for thr in th["stream_threshold_km2"]:
        hand = np.asarray(terrain.compute_hand(grid, dem_cond, fdir, acc_km2 >= thr), dtype="float32")
        hands[thr] = hand
        terrain.write_raster(hand, I / f"hand_glo30_acc{thr:g}km2.tif", transform, crs)
        h_in = hand[inside]
        print(f"HAND (drenagem ≥ {thr:g} km²): mediana no perímetro {np.nanmedian(h_in):.1f} m, "
              f"NaN {np.isnan(h_in).mean():.2%}")

    # --- 3. Área com HAND ≤ h ------------------------------------------------------
    aoi_km2 = inside.sum() * cell_km2
    rows = []
    for thr, hand in hands.items():
        for h in th["hand_m"]:
            sel = inside & (hand <= h)
            rows.append({"stream_threshold_km2": thr, "hand_m": h,
                         "area_km2": round(sel.sum() * cell_km2, 2),
                         "area_pct_of_perimeter": round(100 * sel.sum() * cell_km2 / aoi_km2, 2)})
    t_area = pd.DataFrame(rows)
    t_area.to_csv(TABLES / "hand_area_sensitivity.csv", index=False)
    print("\nÁrea com HAND ≤ h dentro do perímetro:")
    print(t_area.pivot(index="hand_m", columns="stream_threshold_km2", values="area_km2").to_string())

    # --- 4. HAND x SGB 2014 (inundação) --------------------------------------------
    sgb_inund = gpd.read_file(cfg["paths"]["sgb_inundation_2014"]).to_crs(metric)
    # os rótulos vêm com acento ("Média"); normaliza pela primeira letra
    sgb_inund["cls"] = sgb_inund["CLASSE"].str[0].map({"A": "high", "M": "medium", "B": "low"})
    codes = rasterize_classes(sgb_inund, "cls", {"high": 3, "medium": 2, "low": 1}, shape, transform)
    sgb_hm = inside & (codes >= 2)     # Alta + Média (≤ 3 m na legenda do SGB)
    sgb_any = inside & (codes >= 1)
    rows = []
    for thr, hand in hands.items():
        for h in th["hand_m"]:
            sel = inside & (hand <= h)
            rows.append({
                "stream_threshold_km2": thr, "hand_m": h,
                "hand_area_km2": round(sel.sum() * cell_km2, 2),
                "sgb_high_medium_km2": round(sgb_hm.sum() * cell_km2, 2),
                "sgb_any_km2": round(sgb_any.sum() * cell_km2, 2),
                "sgb_high_capture_pct": round(100 * (sel & (codes == 3) & inside).sum() / max((inside & (codes == 3)).sum(), 1), 1),
                "sgb_high_medium_capture_pct": round(100 * (sel & sgb_hm).sum() / max(sgb_hm.sum(), 1), 1),
                "hand_in_sgb_any_pct": round(100 * (sel & sgb_any).sum() / max(sel.sum(), 1), 1),
                "hand_in_sgb_high_medium_pct": round(100 * (sel & sgb_hm).sum() / max(sel.sum(), 1), 1),
            })
    t_sgb = pd.DataFrame(rows)
    t_sgb.to_csv(TABLES / "hand_vs_sgb2014.csv", index=False)
    print("\nHAND x SGB 2014 (inundação), dentro do perímetro:")
    print(t_sgb.to_string(index=False))

    # --- 5. Declividade x SGB 2014 (movimento de massa) ----------------------------
    sgb_mm = gpd.read_file(cfg["paths"]["sgb_mass_movement_2014"]).to_crs(metric)
    sgb_mm["cls"] = sgb_mm["CLASSE"].str[0].map({"A": "high", "M": "medium", "B": "low"})
    mm = rasterize_classes(sgb_mm, "cls", {"high": 3, "medium": 2, "low": 1}, shape, transform)
    steep = inside & (slope >= th["slope_pct_legal"])
    rows = []
    for name, code in [("high", 3), ("medium", 2), ("low", 1)]:
        cls = inside & (mm == code)
        rows.append({"sgb_class": name, "class_area_km2": round(cls.sum() * cell_km2, 2),
                     "steep_in_class_km2": round((cls & steep).sum() * cell_km2, 2),
                     "pct_of_class_steep": round(100 * (cls & steep).sum() / max(cls.sum(), 1), 1),
                     "pct_of_steep_in_class": round(100 * (cls & steep).sum() / max(steep.sum(), 1), 1)})
    t_mm = pd.DataFrame(rows)
    t_mm.to_csv(TABLES / "slope_vs_sgb2014.csv", index=False)
    print(f"\nDeclividade ≥ {th['slope_pct_legal']}% x SGB 2014 (movimento de massa):")
    print(t_mm.to_string(index=False))

    # --- 6. Setores SGB 2012 (checagem qualitativa) --------------------------------
    zip_path = cfg["paths"]["sgb_risk_zip"].as_posix()
    sect = gpd.read_file(f"zip://{zip_path}!Shape/MG_MC_SR_CPRM_atualizado.shp").to_crs(metric)
    hmain = hands[th["stream_threshold_km2_main"]]
    rows = []
    for _, s in sect.iterrows():
        m = geometry_mask([s.geometry], out_shape=shape, transform=transform, invert=True, all_touched=True)
        rows.append({
            "sector": s["NUM_SETOR"], "place": s["LOCAL"], "type": s["TIPOLOGIA"],
            "cells": int(m.sum()),
            "hand_median_m": round(float(np.nanmedian(hmain[m])), 1),
            f"pct_hand_le_{th['hand_m_main']}m": round(100 * float(np.mean(hmain[m] <= th["hand_m_main"])), 1),
            "slope_median_pct": round(float(np.nanmedian(slope[m])), 1),
            "slope_max_pct": round(float(np.nanmax(slope[m])), 1),
            f"pct_slope_ge_{th['slope_pct_legal']}": round(100 * float(np.mean(slope[m] >= th["slope_pct_legal"])), 1),
        })
    t_sec = pd.DataFrame(rows)
    t_sec.to_csv(TABLES / "sgb2012_sectors_check.csv", index=False)
    print("\nSetores SGB 2012 (HAND com drenagem ≥ "
          f"{th['stream_threshold_km2_main']:g} km²):")
    print(t_sec.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
