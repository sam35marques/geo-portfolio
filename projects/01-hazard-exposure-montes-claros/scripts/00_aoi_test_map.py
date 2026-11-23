"""Fase 0 — teste de aceite: mapa da AOI no estilo padrão.

O que faz:
1. carrega a configuração da cidade (config/<cidade>.yaml);
2. baixa o limite municipal do IBGE (se ainda não existir em data/raw);
3. recorta o MDE ALOS PALSAR para a AOI e reprojeta para o CRS métrico
   (SIRGAS 2000 / UTM 23S) -> data/interim/shared/dem_aoi_<crs>.tif (COG);
4. desenha o mapa (hipsometria + sombreamento + limite) com geoportfolio.carto;
5. salva PNG e SVG em outputs/maps/ e um resumo em outputs/tables/.

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/00_aoi_test_map.py
    python projects/01-hazard-exposure-montes-claros/scripts/00_aoi_test_map.py --city outra_cidade
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401  (registra o acessor .rio no xarray)
import xarray as xr
from matplotlib.patches import Patch
from rasterio.enums import Resampling

from geoportfolio import carto
from geoportfolio.io import load_aoi, load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]


def main(city: str) -> None:
    cfg = load_config(city)
    metric = cfg["crs"]["metric"]

    # --- 1. AOI ---------------------------------------------------------------
    aoi = load_aoi(cfg)  # já no CRS métrico
    print(f"AOI: {len(aoi)} polígono(s), área = {aoi.area.sum() / 1e6:,.1f} km²")

    # --- 2. MDE: recorte + reprojeção ------------------------------------------
    dem = xr.open_dataarray(cfg["paths"]["dem"], engine="rasterio", mask_and_scale=True).squeeze()
    # recorta no CRS do próprio MDE (evita reprojetar o arquivo inteiro)
    aoi_dem_crs = aoi.to_crs(dem.rio.crs)
    dem_clip = dem.rio.clip(aoi_dem_crs.geometry, all_touched=True, drop=True)
    # bilinear: adequado para variável contínua (altitude)
    dem_m = dem_clip.rio.reproject(metric, resampling=Resampling.bilinear, nodata=np.nan)

    out_dem = cfg["paths"]["interim"] / "shared" / f"dem_aoi_{metric.replace(':', '').lower()}.tif"
    out_dem.parent.mkdir(parents=True, exist_ok=True)
    dem_m.rio.to_raster(out_dem, driver="COG", compress="DEFLATE", dtype="float32")
    print(f"MDE recortado e reprojetado -> {out_dem}")

    z = dem_m.values
    res = abs(dem_m.rio.resolution()[0])
    aoi_area_km2 = aoi.area.sum() / 1e6
    # cobertura: área dos pixels válidos dentro da AOI / área da AOI.
    # (all_touched=True inclui pixels de borda, então pode passar um pouco de 100%)
    valid_area_km2 = np.isfinite(z).sum() * res**2 / 1e6
    stats = {
        "city": cfg["city"]["name"],
        "aoi_area_km2": round(float(aoi_area_km2), 2),
        "dem_crs_original": str(dem.rio.crs),
        "dem_crs_output": metric,
        "dem_pixel_m": round(float(res), 3),
        "elev_min_m": float(np.nanmin(z)),
        "elev_max_m": float(np.nanmax(z)),
        "elev_mean_m": round(float(np.nanmean(z)), 1),
        "dem_coverage_of_aoi_pct": round(float(100 * valid_area_km2 / aoi_area_km2), 2),
    }
    print(stats)

    # --- 3. Mapa ----------------------------------------------------------------
    fig, ax, side = carto.new_map(
        f"{cfg['city']['name']} ({cfg['city']['state']}), Brazil — study area",
        "Municipal boundary over elevation (test map, Phase 0)",
    )
    x0, y0, x1, y1 = dem_m.rio.bounds()
    extent = (x0, x1, y0, y1)
    shade = carto.hillshade(np.nan_to_num(z, nan=np.nanmean(z)), res)
    shade = np.where(np.isfinite(z), shade, np.nan)

    im = ax.imshow(z, cmap=carto.HYPSO, extent=extent, interpolation="nearest")
    ax.imshow(shade, cmap="gray", alpha=0.35, extent=extent, interpolation="nearest")
    aoi.boundary.plot(ax=ax, color=carto.AOI_EDGE, linewidth=0.6)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    carto.add_legend(side, [Patch(facecolor="none", edgecolor=carto.AOI_EDGE, label="Municipal boundary (IBGE)")],
                     "Legend")
    carto.add_colorbar(fig, side, im, "Elevation (m)")
    side.text(0.0, 0.30,
              f"Area: {stats['aoi_area_km2']:,.0f} km²\n"
              f"Elevation: {stats['elev_min_m']:.0f}–{stats['elev_max_m']:.0f} m\n"
              f"DEM pixel: {cfg['dem']['nominal_resolution_m']} m (effective ~{cfg['dem']['effective_resolution_m']} m)",
              fontsize=6, color=carto.INK, va="top", linespacing=1.6)
    carto.finish_map(
        fig, ax,
        source="IBGE municipal boundary (Malhas API v3);ALOS PALSAR RTC DEM (ASF DAAC, JAXA/METI)",
        crs_label="SIRGAS 2000 / UTM 23S (EPSG:31983)",
    )
    saved = carto.save_figure(fig, PROJECT_DIR / "outputs" / "maps" / "test_aoi_map")
    print("Mapa salvo:", *saved, sep="\n  ")

    # --- 4. Tabela de resumo (todo número citado sai de uma tabela) ------------
    out_tab = PROJECT_DIR / "outputs" / "tables" / "phase0_aoi_summary.csv"
    pd.DataFrame([stats]).to_csv(out_tab, index=False)
    print(f"Resumo -> {out_tab}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros", help="nome do YAML em config/")
    main(parser.parse_args().city)
