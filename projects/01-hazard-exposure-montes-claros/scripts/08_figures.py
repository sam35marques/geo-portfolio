"""P01 — passo 8: mapa principal (hero) e figuras secundárias.

Todo número escrito nas figuras é lido das tabelas em outputs/tables/
(regra do projeto: nada de valores digitados à mão).

Saídas:
  outputs/maps/hero_exposure_h3.png/.svg       painel: população exposta em H3 r8 (1600×900)
  outputs/figures/slope_hand.png/.svg          declividade e HAND (1200×800)
  outputs/figures/hand_vs_sgb.png/.svg         concordância HAND × carta SGB 2014
  outputs/figures/kontur_vs_census.png/.svg    dispersão + mapa de diferenças

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/08_figures.py
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from rasterio.features import geometry_mask, rasterize

from geoportfolio import carto
from geoportfolio import dashboard as dash
from geoportfolio.io import load_aoi, load_config, load_planning_regions

PROJECT_DIR = Path(__file__).resolve().parents[1]
TABLES = PROJECT_DIR / "outputs" / "tables"
MAPS = PROJECT_DIR / "outputs" / "maps"
FIGS = PROJECT_DIR / "outputs" / "figures"
CRS_LABEL = "SIRGAS 2000 / UTM 23S (EPSG:31983)"


def read_window(path, bounds, mask_geom=None):
    """Lê um recorte do raster; células fora de `mask_geom` viram NaN."""
    with rasterio.open(path) as src:
        win = rasterio.windows.from_bounds(*bounds, src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win).astype("float32")
        tr = src.window_transform(win)
    if mask_geom is not None:
        inside = geometry_mask([mask_geom], out_shape=arr.shape, transform=tr, invert=True)
        arr[~inside] = np.nan
    extent = (tr.c, tr.c + tr.a * arr.shape[1], tr.f + tr.e * arr.shape[0], tr.f)
    return arr, tr, extent


def base_layers(ax, hill, extent, regions, streams, aoi, region_lines=True):
    """Fundo comum: relevo sombreado, regiões, córregos e perímetro."""
    ax.imshow(hill, cmap="gray", extent=extent, alpha=0.30, vmin=0, vmax=1, interpolation="bilinear")
    if region_lines:
        regions.boundary.plot(ax=ax, color=carto.LINE, linewidth=0.25, zorder=3)
    streams.plot(ax=ax, color=carto.WATER, linewidth=0.45, zorder=4)
    aoi.boundary.plot(ax=ax, color=carto.AOI_EDGE, linewidth=0.6, zorder=5)


def fmt(n):
    return f"{int(round(n)):,}"


def main(city: str) -> None:
    cfg = load_config(city)
    th = cfg["thresholds"]
    I = cfg["paths"]["interim_p01"]
    conf = th["open_buildings_confidence_main"]
    h_main, acc_main, s_thr = th["hand_m_main"], th["stream_threshold_km2_main"], th["slope_pct_legal"]

    aoi = load_aoi(cfg)
    poly = aoi.geometry.iloc[0]
    regions = load_planning_regions(cfg)
    streams = gpd.read_file(cfg["paths"]["atlas_streams"]).to_crs(aoi.crs).clip(aoi.buffer(1500))
    bounds = tuple(aoi.buffer(700).total_bounds)
    dem, _, extent = read_window(I / "dem_glo30_31983_30m.tif", bounds)
    hill = carto.hillshade(dem, cfg["terrain"]["resolution_m"])

    # --- números das tabelas -----------------------------------------------------------
    ex = pd.read_csv(TABLES / "exposure_summary.csv")
    ex = ex[ex.confidence_min == conf]
    row = lambda hz, par=None: ex[(ex.hazard == hz) & ((ex.parameter == par) if par else True)].iloc[0]
    r_all = row("all buildings in perimeter")
    r_any = row("any hazard")
    r_flood = row("flood-prone (HAND)", f"HAND <= {h_main} m; streams >= {acc_main:g} km2")
    r_slope = row("slope")
    r_sgb12 = row("SGB 2012 risk sector")
    r_ref = row("reference: SGB 2014 inundation")
    sens = pd.read_csv(TABLES / "sensitivity_hand.csv")
    kv = pd.read_csv(TABLES / "kontur_vs_census_summary.csv").iloc[0]
    hv = pd.read_csv(TABLES / "hand_vs_sgb2014.csv")
    hv = hv[(hv.stream_threshold_km2 == acc_main) & (hv.hand_m == h_main)].iloc[0]

    src_main = ("IBGE Census 2022 · Open Buildings v3 · Copernicus GLO-30 · SGB/CPRM · "
                "Atlas Hidrográfico de Montes Claros · Planning Regions (Leite 2006)")

    # ================= 1. HERO (painel 16:9) ================================================
    hexes = gpd.read_file(PROJECT_DIR / "outputs" / "exposure_h3_r8.gpkg").to_crs(aoi.crs)
    bins = [0, 50, 200, 500, 1000, np.inf]
    labels = ["1–50", "51–200", "201–500", "501–1,000", "> 1,000"]
    colors = plt.get_cmap(carto.EXPOSURE)(np.linspace(0.15, 0.95, len(labels)))
    hexes["cls"] = pd.cut(hexes.pop_exposed_any, bins=bins, labels=False, include_lowest=False)

    # regiões com mais residentes expostos (tabela) e posição dos balões:
    # centro ponderado pela população exposta dos hexágonos de cada região
    reg = pd.read_csv(TABLES / "exposure_by_region.csv").sort_values("pop_any", ascending=False)
    display_name = {"Distrito Induatrial": "Distrito Industrial"}   # grafia corrigida só no rótulo
    cent = gpd.GeoDataFrame(hexes[["pop_exposed_any"]], geometry=hexes.centroid, crs=hexes.crs)
    cent = gpd.sjoin(cent, regions, how="inner", predicate="within")
    top = []
    for _, r in reg.head(3).iterrows():
        c = cent[(cent.region == r.region) & (cent.pop_exposed_any > 0)]
        wts = c.pop_exposed_any
        top.append((display_name.get(r.region, r.region), r.pop_any,
                    float((c.geometry.x * wts).sum() / wts.sum()), float((c.geometry.y * wts).sum() / wts.sum())))

    share_flood = 100 * r_flood.population / r_any.population
    sens_min, sens_max = sens.population.min(), sens.population.max()

    D = dash.Dashboard("Hazard exposure · Montes Claros, Brazil",
                       "Project 01 · open, reproducible geospatial portfolio",
                       "CENSUS 2022 · H3 RESOLUTION 8", "Samuel Marques · 2026")

    # --- coluna esquerda: título, número-destaque, indicadores ----------------------------
    y = D.title(0.03, 0.895, "Who lives in\nhazard-prone areas",
                "Residents of the urban perimeter in buildings on steep slopes, "
                "flood-prone lowlands or mapped risk sectors.")
    y = D.kpi_big(0.03, y, dash.fmt_int(r_any.population), "Residents exposed", "CENSUS 2022 · OPEN BUILDINGS")
    D.kpi_row(0.03, y, "drop", "blue", f"Flood-prone lowlands (HAND ≤ {h_main} m)", dash.fmt_int(r_flood.population))
    D.kpi_row(0.03, y - 0.085, "slope", "orange", f"Slopes ≥ {s_thr}%", dash.fmt_int(r_slope.population))
    D.kpi_row(0.03, y - 0.170, "sector", "purple", "SGB 2012 risk sectors", dash.fmt_int(r_sgb12.population))
    D.ring(0.03, y - 0.285, r_any.population_pct / 100, dash.fmt_int(r_all.population),
           "residents in the urban perimeter (Census 2022); the ring shows the share exposed")
    D.kpi_row(0.03, y - 0.41, "hex", "green", "Kontur Population vs Census, per hexagon",
              f"r = {kv.pearson_r:.2f}", note=f"total {100 * (kv.total_ratio_kontur_over_census - 1):+.0f}%")

    # --- mapa central ---------------------------------------------------------------------
    ax = D.fig.add_axes([0.225, 0.075, 0.49, 0.835])
    ax.axis("off")
    ax.set_aspect("equal", adjustable="datalim")
    x0, y0, x1, y1 = aoi.buffer(900).total_bounds
    dash.soft_shadow(ax, poly, (x0, y0, x1, y1))
    aoi.plot(ax=ax, color="white", edgecolor="none", zorder=1)
    hexes[hexes.cls.isna()].plot(ax=ax, color="white", edgecolor="#E4E6F1", linewidth=0.6, zorder=2)
    for k, c in enumerate(colors):
        sub = hexes[hexes.cls == k]
        if len(sub):
            sub.plot(ax=ax, color=c, edgecolor="white", linewidth=0.6, zorder=3)
    regions.boundary.plot(ax=ax, color="#C9CDDC", linewidth=0.5, zorder=4)
    streams.clip(aoi.buffer(300)).plot(ax=ax, color=carto.WATER, linewidth=0.9, zorder=5)
    aoi.boundary.plot(ax=ax, color=dash.DASH["ink2"], linewidth=1.0, zorder=6)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.apply_aspect()
    vx0, vx1 = ax.get_xlim()   # limites visíveis depois de ajustar a proporção
    xmid = (x0 + x1) / 2
    for name, val, cx, cy in top:
        dx = (vx0 + 2700) - cx if cx < xmid else (vx1 - 2700) - cx   # balão na margem, fora da mancha urbana
        dash.callout(ax, cx, cy, name, f"{dash.fmt_int(val)} exposed", colors[-1], dx=dx, dy=500, w=5000)
    dash.north(ax, vx1 - 1300, y1 - 1200)
    dash.scalebar(ax, vx1 - 2600, y0 + 700)

    # --- coluna direita: legenda, por que importa, método ------------------------------------
    cx0, cw = 0.735, 0.24
    yy = D.card(cx0, 0.645, cw, 0.265, "Exposed residents per hexagon")
    for c, l in zip(colors[::-1], labels[::-1]):
        D.fig.add_artist(plt.Rectangle((cx0 + 0.016, yy - 0.016), 0.022, 0.024, transform=D.fig.transFigure,
                                       fc=c, ec="white", zorder=3))
        D.fig.text(cx0 + 0.046, yy - 0.004, l, fontsize=9.5, color=dash.DASH["ink"], va="center", zorder=3)
        yy -= 0.034
    D.fig.add_artist(plt.Rectangle((cx0 + 0.016, yy - 0.016), 0.022, 0.024, transform=D.fig.transFigure,
                                   fc="white", ec="#C9CDDC", zorder=3))
    D.fig.text(cx0 + 0.046, yy - 0.004, "none", fontsize=9.5, color=dash.DASH["ink"], va="center", zorder=3)
    lx = cx0 + 0.13
    ly = 0.645 + 0.265 - 0.058
    for color, lw, lab in [(carto.WATER, 1.6, "streams"), ("#C9CDDC", 1.2, "planning regions"),
                           (dash.DASH["ink2"], 1.6, "urban perimeter")]:
        D.fig.add_artist(plt.Line2D([lx, lx + 0.02], [ly - 0.004, ly - 0.004], transform=D.fig.transFigure,
                                    color=color, lw=lw, zorder=3))
        D.fig.text(lx + 0.026, ly - 0.004, lab, fontsize=9, color=dash.DASH["ink2"], va="center", zorder=3)
        ly -= 0.034
    D.fig.text(lx, ly - 0.006, "H3 resolution 8\n≈ 0.7 km² per hexagon", fontsize=8.5,
               color=dash.DASH["muted"], va="top", linespacing=1.35, zorder=3)

    yy = D.card(cx0, 0.375, cw, 0.24, "Why it matters")
    D.text(cx0 + 0.014, yy, cw - 0.028,
           f"{share_flood:.0f}% of exposed residents live in flood-prone lowlands along the stream "
           f"valleys. Exposure concentrates in {top[0][0]}, {top[1][0]} and {top[2][0]}: "
           "first candidates for drainage works, early warning and land-use control.", size=9.5)

    yy = D.card(cx0, 0.075, cw, 0.27, "Method")
    yy = D.text(cx0 + 0.014, yy, cw - 0.028,
                "Census 2022 residents spread over Google Open Buildings footprints (dasymetric). "
                f"Hazards: slope ≥ {s_thr}% and HAND ≤ {h_main} m from Copernicus GLO-30 (30 m); "
                "SGB/CPRM 2012 risk sectors. Planning Regions: Decree 3,393/2016. "
                "SIRGAS 2000 / UTM 23S.", size=9, spacing=1.45)
    D.text(cx0 + 0.014, yy, cw - 0.028,
           f"Flood-prone = terrain susceptibility, not a flood model. "
           f"Range across thresholds: {dash.fmt_int(sens_min)}–{dash.fmt_int(sens_max)}.",
           size=8.5, color=dash.DASH["muted"], spacing=1.4)

    D.footer("Data: IBGE Census 2022 · Google Open Buildings v3 · Copernicus GLO-30 · SGB/CPRM 2012 · "
             "Atlas Hidrográfico de Montes Claros (2026) · Planning Regions (Leite 2006; LC 53/2016)",
             "github.com/sam35marques/geo-portfolio")
    print("hero:", *D.save(MAPS / "hero_exposure_h3"))
    plt.close(D.fig)

    # ================= 2. SLOPE + HAND ===================================================
    slope, _, ext2 = read_window(I / "slope_pct_glo30.tif", bounds, poly)
    hand, _, _ = read_window(I / f"hand_glo30_acc{acc_main:g}km2.tif", bounds, poly)
    fig, (a1, a2) = carto.new_panels("Terrain hazards: steep slopes and flood-prone lowlands",
                                     f"Copernicus GLO-30 (30 m), urban perimeter of Montes Claros · HAND relative to streams draining ≥ {acc_main:g} km²")
    sb = th["slope_classes_embrapa_pct"] + [np.inf]
    slab = ["0–3 flat", "3–8 gentle", "8–20 moderate", "20–45 strong", "45–75 steep", "> 75 very steep"]
    scol = plt.get_cmap("YlOrBr")(np.linspace(0.08, 0.95, len(slab)))
    for a in (a1, a2):
        a.imshow(hill, cmap="gray", extent=extent, alpha=0.30, vmin=0, vmax=1)
    a1.imshow(slope, cmap=ListedColormap(scol), norm=BoundaryNorm(sb[:-1] + [1e9], len(slab)), extent=ext2, interpolation="nearest")
    hb = [0, 1, 2, 3, 5]
    hcol = plt.get_cmap("Blues_r")(np.linspace(0.1, 0.75, 4))
    hm = np.where(hand <= 5, hand, np.nan)
    a2.imshow(hm, cmap=ListedColormap(hcol), norm=BoundaryNorm(hb, 4), extent=ext2, interpolation="nearest")
    for a in (a1, a2):
        aoi.boundary.plot(ax=a, color=carto.AOI_EDGE, linewidth=0.5)
        a.set_xlim(bounds[0], bounds[2]); a.set_ylim(bounds[1], bounds[3]); a.set_aspect("equal")
    carto.panel_label(a1, "a) Slope (%), EMBRAPA classes")
    carto.panel_label(a2, "b) HAND (m)")
    carto.add_legend(a1, [Patch(color=c, label=l) for c, l in zip(scol, slab)], "Slope (%)", loc="lower right", fontsize=4.5, frame=True)
    carto.add_legend(a2, [Patch(color=c, label=l) for c, l in zip(hcol, ["0–1", "1–2", "2–3", "3–5"])] +
                     [Line2D([], [], color=carto.WATER, lw=0.6, label="streams (Atlas)")], "HAND (m)", loc="lower right", fontsize=4.5, frame=True)
    streams.plot(ax=a2, color=carto.WATER, linewidth=0.35)
    carto.tidy_map_axes(a1); carto.tidy_map_axes(a2)
    carto.add_north_arrow(a1); carto.add_scalebar(a1)
    carto.add_footer(fig, "Copernicus GLO-30 DEM (ESA); Atlas Hidrográfico de Montes Claros (2026)", CRS_LABEL)
    print("slope_hand:", *carto.save_figure(fig, FIGS / "slope_hand"))
    plt.close(fig)

    # ================= 3. HAND x SGB 2014 =================================================
    with rasterio.open(I / f"hand_glo30_acc{acc_main:g}km2.tif") as src:
        win = rasterio.windows.from_bounds(*bounds, src.transform).round_offsets().round_lengths()
        tr = src.window_transform(win)
    sgb = gpd.read_file(cfg["paths"]["sgb_inundation_2014"]).to_crs(aoi.crs)
    sgb_hm = rasterize(((g, 1) for g, c in zip(sgb.geometry, sgb.CLASSE) if c[0] in "AM"),
                       out_shape=hand.shape, transform=tr, fill=0).astype(bool)
    inside = np.isfinite(hand)
    h3m = (hand <= h_main) & inside
    cat = np.full(hand.shape, np.nan)
    cat[h3m & ~sgb_hm] = 0
    cat[~h3m & sgb_hm & inside] = 1
    cat[h3m & sgb_hm] = 2
    ccol = [carto.OKABE_ITO["orange"], carto.OKABE_ITO["sky_blue"], carto.OKABE_ITO["green"]]
    fig, ax, side = carto.new_map(f"Flood-prone lowlands: HAND ≤ {h_main} m vs the official SGB 2014 susceptibility chart",
                                  "Agreement check, not validation: both use height above drainage (SGB from a 2.5 m terrain model, HAND from a 30 m surface model)",
                                  size_px=carto.SECONDARY_PX)
    ax.imshow(hill, cmap="gray", extent=extent, alpha=0.30, vmin=0, vmax=1)
    ax.imshow(cat, cmap=ListedColormap(ccol), vmin=-0.5, vmax=2.5, extent=ext2, interpolation="nearest")
    zip_path = cfg["paths"]["sgb_risk_zip"].as_posix()
    sect = gpd.read_file(f"zip://{zip_path}!Shape/MG_MC_SR_CPRM_atualizado.shp").to_crs(aoi.crs)
    sect.boundary.plot(ax=ax, color=carto.OKABE_ITO["vermillion"], linewidth=0.8)
    aoi.boundary.plot(ax=ax, color=carto.AOI_EDGE, linewidth=0.5)
    ax.set_xlim(bounds[0], bounds[2]); ax.set_ylim(bounds[1], bounds[3])
    leg = carto.add_legend(side, [Patch(color=ccol[0], label=f"HAND ≤ {h_main} m only"),
                                  Patch(color=ccol[1], label="SGB 2014 high + medium only"),
                                  Patch(color=ccol[2], label="both"),
                                  Line2D([], [], color=carto.OKABE_ITO["vermillion"], lw=0.9, label="SGB 2012 risk sectors")],
                           "Inside the urban perimeter", fontsize=4.8, bbox_to_anchor=(0, 1))
    carto.add_text_block(side, [
        (f"HAND ≤ {h_main} m covers {hv.sgb_high_capture_pct:.0f}% of SGB 'high' and "
         f"{hv.sgb_high_medium_capture_pct:.0f}% of 'high + medium'.", 5, "normal"),
        (f"Only {hv.hand_in_sgb_high_medium_pct:.0f}% of the HAND area is SGB 'high + medium': "
         "the 30 m HAND is broader.", 5, "normal"),
        (f"Residents: {fmt(r_ref.population)} in SGB high + medium zones vs "
         f"{fmt(r_flood.population)} in HAND ≤ {h_main} m.", 5, "normal"),
    ], y=carto.below(side, leg), gap=0.5)
    carto.finish_map(fig, ax, source="SGB/CPRM 2014 susceptibility chart and 2012 risk sectors; Copernicus GLO-30", crs_label=CRS_LABEL)
    print("hand_vs_sgb:", *carto.save_figure(fig, FIGS / "hand_vs_sgb"))
    plt.close(fig)

    # ================= 4. KONTUR x CENSUS ================================================
    fig, (a1, a2) = carto.new_panels("Kontur Population vs Census 2022 on H3 resolution 8",
                                     f"{int(kv.cells)} hexagons with centre in the urban perimeter · Census 2022 spread over Open Buildings footprints (dasymetric)")
    # o gráfico de dispersão precisa de margem para os números dos eixos
    p = a1.get_position()
    a1.set_position([p.x0 + 0.07, p.y0 + 0.06, p.width - 0.07, p.height - 0.06])
    for sp in a1.spines.values():
        sp.set_color(carto.MUTED)
    x, y = hexes.pop_census, hexes.pop_kontur
    lim = max(x.max(), y.max()) * 1.05
    a1.scatter(x, y, s=4, color=carto.OKABE_ITO["blue"], alpha=0.7, linewidths=0)
    a1.plot([0, lim], [0, lim], color=carto.MUTED, lw=0.6, ls="--")
    a1.set_xlim(0, lim); a1.set_ylim(0, lim); a1.set_aspect("equal")
    a1.set_xticks(np.arange(0, lim, 2000)); a1.set_yticks(np.arange(0, lim, 2000))
    a1.tick_params(labelsize=4.5, length=2, width=0.3)
    a1.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a1.set_xlabel("Census 2022, dasymetric (residents per hexagon)", fontsize=5)
    a1.set_ylabel("Kontur Population 2023-11-01", fontsize=5)
    a1.text(0.04, 0.96, f"r = {kv.pearson_r:.2f}\ntotal ratio Kontur / Census = {kv.total_ratio_kontur_over_census:.2f}\n"
                        f"median |difference| = {fmt(kv.median_abs_diff_per_cell)} per hexagon",
            transform=a1.transAxes, va="top", fontsize=5, linespacing=1.4)
    carto.panel_label(a1, "a)")
    a1.texts[-1].set_position((0.92, 0.06))
    db = [-np.inf, -1000, -250, 250, 1000, np.inf]
    dlab = ["< −1,000", "−1,000 to −250", "±250", "250 to 1,000", "> 1,000"]
    dcol = plt.get_cmap(carto.DIVERGING)(np.linspace(0.1, 0.9, 5))
    hexes["dcls"] = pd.cut(hexes.diff_kontur_minus_census, bins=db, labels=False)
    a2.imshow(hill, cmap="gray", extent=extent, alpha=0.30, vmin=0, vmax=1)
    for k, c in enumerate(dcol):
        hexes[hexes.dcls == k].plot(ax=a2, color=c, edgecolor="white", linewidth=0.25)
    aoi.boundary.plot(ax=a2, color=carto.AOI_EDGE, linewidth=0.5)
    a2.set_xlim(bounds[0], bounds[2]); a2.set_ylim(bounds[1], bounds[3]); a2.set_aspect("equal")
    carto.panel_label(a2, "b) Kontur − Census")
    carto.add_legend(a2, [Patch(color=c, label=l) for c, l in zip(dcol, dlab)], "Residents per hexagon", loc="lower right", fontsize=4.5, frame=True)
    carto.tidy_map_axes(a2)
    carto.add_scalebar(a2)
    carto.add_footer(fig, "Kontur Population Brazil 2023-11-01 (HDX, CC BY 4.0); IBGE Census 2022; Google Open Buildings v3", CRS_LABEL)
    print("kontur_vs_census:", *carto.save_figure(fig, FIGS / "kontur_vs_census"))
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
