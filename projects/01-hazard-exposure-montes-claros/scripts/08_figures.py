"""P01 — passo 8: pranchas-painel (16:9) do projeto.

Todas as figuras seguem o mesmo painel (geoportfolio.dashboard): indicadores
à esquerda, mapa ao centro, cartões à direita. Todo número escrito vem das
tabelas em outputs/tables/ (nada digitado à mão).

Saídas (1600 × 900 px, PNG marcado com 300 dpi + SVG):
  outputs/maps/location_montes_claros   onde fica a área de estudo
  outputs/maps/hero_exposure_h3         residentes expostos por hexágono H3 r8
  outputs/figures/slope_steep           declividade e encostas ≥ 30%
  outputs/figures/hand_flood_prone      HAND e baixadas suscetíveis a inundação
  outputs/figures/hand_vs_sgb           concordância HAND × carta SGB 2014
  outputs/figures/kontur_vs_census      Kontur Population × Censo 2022
Também grava:
  data/interim/p01/atlas_streams_urban.gpkg   córregos recortados pelo perímetro
  outputs/tables/study_area_summary.csv       números da prancha de localização

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/08_figures.py
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from rasterio.features import geometry_mask, rasterize

from geoportfolio import carto
from geoportfolio import dashboard as dash
from geoportfolio.io import load_aoi, load_config, load_municipality, load_planning_regions

PROJECT_DIR = Path(__file__).resolve().parents[1]
TABLES = PROJECT_DIR / "outputs" / "tables"
MAPS = PROJECT_DIR / "outputs" / "maps"
FIGS = PROJECT_DIR / "outputs" / "figures"

MAP_RECT = [0.225, 0.075, 0.49, 0.835]     # área do mapa central
LOC_RECT = [0.226, 0.715, 0.085, 0.19]     # localizador (canto superior esquerdo do mapa)
CARD_X, CARD_W = 0.735, 0.24
INK, INK2, MUTED = dash.DASH["ink"], dash.DASH["ink2"], dash.DASH["muted"]
OKABE = carto.OKABE_ITO
fmt = dash.fmt_int
SRC_BASE = ("Copernicus GLO-30 · Atlas Hidrográfico de Montes Claros (2026) · "
            "Planning Regions (Leite 2006; Decree 3,393/2016)")
REPO = "github.com/sam35marques/geo-portfolio"


# =============================================================================
# preparação
# =============================================================================
def prepare_streams(cfg, aoi):
    """Córregos do Atlas recortados pelo perímetro urbano (camada derivada em data/interim).

    O arquivo original em data/raw não é alterado.
    """
    s = gpd.read_file(cfg["paths"]["atlas_streams"]).to_crs(aoi.crs)
    s = s.clip(aoi)[["NORIOCOMP", "TIPO_CURSO", "geometry"]]
    s = s[~s.is_empty]
    out = cfg["paths"]["atlas_streams_urban"]
    out.parent.mkdir(parents=True, exist_ok=True)
    s.to_file(out, layer="streams", driver="GPKG")
    return s


def study_area_table(cfg, aoi, regions):
    """Números da prancha de localização -> outputs/tables/study_area_summary.csv."""
    mun = load_municipality(cfg)
    das = pd.read_csv(TABLES / "dasymetric_summary.csv")
    das = das[das.confidence_min == cfg["thresholds"]["open_buildings_confidence_main"]].iloc[0]
    c = aoi.to_crs(4326).geometry.iloc[0].centroid
    t = pd.DataFrame([{
        "municipality": cfg["city"]["name"], "state": cfg["city"]["state_name"],
        "municipality_area_km2": round(mun.area.sum() / 1e6, 1),
        "municipality_population_2022": int(das.population_municipality_census),
        "urban_perimeter_area_km2": round(aoi.area.sum() / 1e6, 1),
        "planning_regions": int(len(regions)),
        "population_in_perimeter_dasymetric": int(das.population_in_perimeter),
        "share_population_in_perimeter_pct": round(100 * das.population_in_perimeter / das.population_municipality_census, 1),
        "perimeter_centroid_lat": round(c.y, 3), "perimeter_centroid_lon": round(c.x, 3),
    }])
    t.to_csv(TABLES / "study_area_summary.csv", index=False)
    return t.iloc[0], mun


def read_masked(path, extent, geom):
    """Recorte do raster na extensão do mapa; fora do perímetro = NaN."""
    with rasterio.open(path) as src:
        win = rasterio.windows.from_bounds(*extent, src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win).astype("float32")
        tr = src.window_transform(win)
    arr[~geometry_mask([geom], out_shape=arr.shape, transform=tr, invert=True)] = np.nan
    ext = (tr.c, tr.c + tr.a * arr.shape[1], tr.f + tr.e * arr.shape[0], tr.f)
    return arr, tr, ext


# =============================================================================
# blocos comuns
# =============================================================================
def new_board(title_left):
    return dash.Dashboard(title_left, "Project 01 · open, reproducible geospatial portfolio",
                          "MONTES CLAROS · MINAS GERAIS · BRAZIL", "Samuel Marques · 2026")


def city_map(D, ctx, labels=False):
    """Mapa central da cidade com base comum, localizador, norte e escala."""
    ax = D.fig.add_axes(MAP_RECT)
    vx0, vx1 = dash.city_base(ax, ctx["aoi"], ctx["regions"], ctx["streams"], ctx["extent"], labels=labels)
    x0, y0, x1, y1 = ctx["extent"]
    dash.locator(D.fig, LOC_RECT, ctx["countries"], ctx["states"], ctx["state_code"], ctx["lonlat"],
                 "Montes Claros")
    dash.north(ax, vx1 - 1300, y1 - 1200)
    dash.scalebar(ax, vx1 - 2600, y0 + 700)
    return ax, vx0, vx1


def legend_swatches(D, x, y, items, size=9.5, step=0.034, box=(0.022, 0.024)):
    """Amostras de cor (ou linhas) num cartão. items = [(cor, rótulo, "box" | "line")]."""
    for color, label, kind in items:
        if kind == "line":
            D.fig.add_artist(plt.Line2D([x, x + box[0]], [y - 0.004, y - 0.004], transform=D.fig.transFigure,
                                        color=color, lw=1.8, zorder=3))
        else:
            is_white = isinstance(color, str) and color.lower() in ("white", "#ffffff")
            ec = "#C9CDDC" if is_white else "white"   # borda visível só para amostra branca
            D.fig.add_artist(plt.Rectangle((x, y - 0.016), *box, transform=D.fig.transFigure, fc=color, ec=ec,
                                           zorder=3))
        D.fig.text(x + box[0] + 0.008, y - 0.004, label, fontsize=size, color=INK, va="center", zorder=3)
        y -= step
    return y


def base_items():
    return [(dash.STREAM, "streams (Atlas Hidrográfico)", "line"),
            (dash.REGION_LINE, "planning regions", "line"),
            (INK, "urban perimeter", "line")]


# =============================================================================
# pranchas
# =============================================================================
def board_location(ctx, sa, mun):
    D = new_board("Study area · Montes Claros, Brazil")
    y = D.title(0.03, 0.895, "Where is\nMontes Claros?",
                f"Project 01 studies the urban perimeter of {sa.municipality}, in the north of "
                f"{sa.state} state, south-eastern Brazil.")
    y = D.kpi_big(0.03, y, fmt(sa.municipality_population_2022), "Residents of the municipality", "CENSUS 2022")
    D.kpi_row(0.03, y, "sector", "purple", "Municipality area", f"{fmt(sa.municipality_area_km2)} km²")
    D.kpi_row(0.03, y - 0.085, "hex", "blue", "Urban perimeter (study area)", f"{sa.urban_perimeter_area_km2:.0f} km²")
    D.kpi_row(0.03, y - 0.170, "people", "green", "Planning Regions", f"{sa.planning_regions}")
    D.ring(0.03, y - 0.285, sa.share_population_in_perimeter_pct / 100, fmt(sa.population_in_perimeter_dasymetric),
           "residents inside the urban perimeter; the ring shows their share of the municipality",
           color=OKABE["blue"])

    # (a) América do Sul / Brasil / Minas Gerais
    a1 = D.fig.add_axes([0.225, 0.47, 0.21, 0.44])
    sam = ctx["countries"][ctx["countries"]["CONTINENT"] == "South America"]
    sam.plot(ax=a1, color="#E3E6EE", edgecolor="white", linewidth=0.5)
    ctx["states"].plot(ax=a1, color="#D3D7E6", edgecolor="white", linewidth=0.5)
    mg = ctx["states"][ctx["states"]["codarea"].astype(str) == str(ctx["state_code"])]
    mg.plot(ax=a1, color="#9AA3C7", edgecolor="white", linewidth=0.5)
    a1.scatter(*ctx["lonlat"], s=40, color=OKABE["vermillion"], edgecolors="white", linewidths=1.2, zorder=5)
    a1.set_xlim(-82, -33); a1.set_ylim(-56, 13); a1.set_aspect(1 / np.cos(np.radians(15))); a1.axis("off")
    halo = [pe.withStroke(linewidth=2.4, foreground="white")]
    a1.text(-53, -8, "BRAZIL", fontsize=10, weight="bold", color=INK2, ha="center", path_effects=halo)
    mgc = mg.geometry.iloc[0].representative_point()
    a1.text(mgc.x + 3.5, mgc.y - 2.5, sa.state, fontsize=8.5, color=INK, ha="left", path_effects=halo)
    a1.text(-36.5, -30, "Atlantic\nOcean", fontsize=8, style="italic", color=MUTED, ha="center")
    a1.text(-77, -30, "Pacific\nOcean", fontsize=8, style="italic", color=MUTED, ha="center")
    a1.text(0.02, 0.99, "a) South America", transform=a1.transAxes, fontsize=9.5, weight="semibold", va="top")

    # (b) município com o perímetro urbano
    a2 = D.fig.add_axes([0.225, 0.075, 0.21, 0.37])
    mun_m = mun.to_crs(ctx["aoi"].crs)
    mun_m.plot(ax=a2, color="#E9EBF4", edgecolor=INK2, linewidth=0.9)
    ctx["aoi"].plot(ax=a2, color="#9AA3C7", edgecolor=INK, linewidth=0.8)
    a2.set_aspect("equal"); a2.axis("off")
    a2.text(0.02, 0.99, "b) Municipality and urban perimeter", transform=a2.transAxes, fontsize=9.5,
            weight="semibold", va="top")
    mx0, my0, mx1, my1 = mun_m.total_bounds
    dash.scalebar(a2, mx1 - 10000, my0 + 2000, km=10)

    # (c) perímetro com as Regiões de Planejamento nomeadas
    a3 = D.fig.add_axes([0.445, 0.075, 0.27, 0.835])
    vx0, vx1 = dash.city_base(a3, ctx["aoi"], ctx["regions"], ctx["streams"], ctx["extent"], labels=True,
                              fill="#F7F8FC")
    x0, y0, x1, y1 = ctx["extent"]
    a3.text(0.02, 0.99, f"c) Urban perimeter: {sa.planning_regions} Planning Regions", transform=a3.transAxes,
            fontsize=9.5, weight="semibold", va="top")
    dash.north(a3, vx1 - 900, y0 + 2600)
    dash.scalebar(a3, vx1 - 2600, y0 + 700)

    yy = D.card(CARD_X, 0.585, CARD_W, 0.325, "Legend")
    legend_swatches(D, CARD_X + 0.016, yy, [
        ("#D3D7E6", "Brazil (states)", "box"), ("#9AA3C7", f"{sa.state} / urban perimeter", "box"),
        (OKABE["vermillion"], "Montes Claros", "box"), ("#E9EBF4", "municipality", "box")] + base_items(),
        size=9, step=0.031)
    yy = D.card(CARD_X, 0.31, CARD_W, 0.25, "About the study area")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"The urban perimeter covers {sa.urban_perimeter_area_km2:.0f} km² of a {fmt(sa.municipality_area_km2)} km² "
           f"municipality and holds {sa.share_population_in_perimeter_pct:.0f}% of its residents. "
           f"It is divided into {sa.planning_regions} Planning Regions, the units used here to report results. "
           f"Centre: {abs(sa.perimeter_centroid_lat):.2f}° S, {abs(sa.perimeter_centroid_lon):.2f}° W.", size=9.5)
    yy = D.card(CARD_X, 0.075, CARD_W, 0.21, "Data")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           "Natural Earth (countries) · IBGE state and municipal boundaries · IBGE Census 2022 · "
           "Planning Regions: Leite (2006), Decree 3,393/2016, Master Plan LC 53/2016. "
           "Maps b–c: SIRGAS 2000 / UTM 23S.", size=9, spacing=1.45)
    D.footer("Data: Natural Earth · IBGE · " + SRC_BASE, REPO)
    print("location:", *D.save(MAPS / "location_montes_claros"))
    plt.close(D.fig)


def board_hero(ctx, N):
    hexes = ctx["hexes"]
    bins = [0, 50, 200, 500, 1000, np.inf]
    labels = ["1–50", "51–200", "201–500", "501–1,000", "> 1,000"]
    colors = plt.get_cmap(carto.EXPOSURE)(np.linspace(0.15, 0.95, len(labels)))
    hexes["cls"] = pd.cut(hexes.pop_exposed_any, bins=bins, labels=False, include_lowest=False)

    # 3 regiões com mais residentes expostos; balão no centro ponderado pela exposição
    reg = pd.read_csv(TABLES / "exposure_by_region.csv").sort_values("pop_any", ascending=False)
    cent = gpd.GeoDataFrame(hexes[["pop_exposed_any"]], geometry=hexes.centroid, crs=hexes.crs)
    cent = gpd.sjoin(cent, ctx["regions"], how="inner", predicate="within")
    top = []
    for _, r in reg.head(3).iterrows():
        c = cent[(cent.region == r.region) & (cent.pop_exposed_any > 0)]
        w = c.pop_exposed_any
        top.append((r.region.replace("Induatrial", "Industrial"), r.pop_any,
                    float((c.geometry.x * w).sum() / w.sum()), float((c.geometry.y * w).sum() / w.sum())))

    D = new_board("Hazard exposure · Montes Claros, Brazil")
    y = D.title(0.03, 0.895, "Who lives in\nhazard-prone areas",
                "Residents of the urban perimeter in buildings on steep slopes, "
                "flood-prone lowlands or mapped risk sectors.")
    y = D.kpi_big(0.03, y, fmt(N["any"].population), "Residents exposed", "CENSUS 2022 · OPEN BUILDINGS")
    D.kpi_row(0.03, y, "drop", "blue", f"Flood-prone lowlands (HAND ≤ {N['h']} m)", fmt(N["flood"].population))
    D.kpi_row(0.03, y - 0.085, "slope", "orange", f"Slopes ≥ {N['s']}%", fmt(N["slope"].population))
    D.kpi_row(0.03, y - 0.170, "sector", "purple", "SGB 2012 risk sectors", fmt(N["sgb12"].population))
    D.ring(0.03, y - 0.285, N["any"].population_pct / 100, fmt(N["all"].population),
           "residents in the urban perimeter (Census 2022); the ring shows the share exposed")
    D.kpi_row(0.03, y - 0.41, "hex", "green", "Kontur Population vs Census, per hexagon",
              f"r = {N['kv'].pearson_r:.2f}", note=f"total {100 * (N['kv'].total_ratio_kontur_over_census - 1):+.0f}%")

    ax, vx0, vx1 = city_map(D, ctx)
    hexes[hexes.cls.isna()].plot(ax=ax, color="white", edgecolor="#E4E6F1", linewidth=0.6, zorder=2)
    for k, c in enumerate(colors):
        sub = hexes[hexes.cls == k]
        if len(sub):
            sub.plot(ax=ax, color=c, edgecolor="white", linewidth=0.6, zorder=3)
    x0, y0, x1, y1 = ctx["extent"]
    xmid = (x0 + x1) / 2
    for name, val, cx, cy in top:
        dx = (vx0 + 2700) - cx if cx < xmid else (vx1 - 2700) - cx
        dash.callout(ax, cx, cy, name, f"{fmt(val)} exposed", colors[-1], dx=dx, dy=500, w=5000)

    yy = D.card(CARD_X, 0.585, CARD_W, 0.325, "Exposed residents per hexagon")
    legend_swatches(D, CARD_X + 0.016, yy, [(c, l, "box") for c, l in zip(colors[::-1], labels[::-1])]
                    + [("white", "none", "box")], step=0.031)
    legend_swatches(D, CARD_X + 0.115, yy, [(dash.STREAM, "streams", "line"),
                                            (dash.REGION_LINE, "planning regions", "line"),
                                            (INK, "urban perimeter", "line")], size=9, step=0.031)
    D.fig.text(CARD_X + 0.115, yy - 0.105, "H3 resolution 8\n≈ 0.7 km² per hexagon", fontsize=8.5, color=MUTED,
               va="top", linespacing=1.35, zorder=3)
    yy = D.card(CARD_X, 0.335, CARD_W, 0.225, "Why it matters")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"{100 * N['flood'].population / N['any'].population:.0f}% of exposed residents live in flood-prone "
           f"lowlands along the stream valleys. Exposure concentrates in {top[0][0]}, {top[1][0]} and "
           f"{top[2][0]}: first candidates for drainage works, early warning and land-use control.", size=9.5)
    yy = D.card(CARD_X, 0.075, CARD_W, 0.235, "Method")
    yy = D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
                "Census 2022 residents spread over Google Open Buildings footprints (dasymetric). "
                f"Hazards: slope ≥ {N['s']}% and HAND ≤ {N['h']} m (Copernicus GLO-30, 30 m); "
                "SGB/CPRM 2012 sectors. SIRGAS 2000 / UTM 23S.", size=9, spacing=1.45)
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"Flood-prone = terrain susceptibility, not a flood model. Range across thresholds: "
           f"{fmt(N['sens'].population.min())}–{fmt(N['sens'].population.max())}.", size=8.5, color=MUTED, spacing=1.4)
    D.footer("Data: IBGE Census 2022 · Google Open Buildings v3 · SGB/CPRM 2012 · " + SRC_BASE, REPO)
    print("hero:", *D.save(MAPS / "hero_exposure_h3"))
    plt.close(D.fig)


def board_slope(ctx, N, cfg):
    I = cfg["paths"]["interim_p01"]
    ts = N["terrain"]
    s = N["s"]
    slope, _, ext = read_masked(I / "slope_pct_glo30.tif", ctx["extent"], ctx["poly"])
    sb = cfg["thresholds"]["slope_classes_embrapa_pct"] + [1e9]
    slab = ["0–3 flat", "3–8 gentle", "8–20 moderate", "20–45 strong", "45–75 steep", "> 75 very steep"]
    scol = plt.get_cmap("YlOrBr")(np.linspace(0.06, 0.95, len(slab)))

    D = new_board("Steep slopes · Montes Claros, Brazil")
    y = D.title(0.03, 0.895, "Steep slopes", "Terrain slope inside the urban perimeter, from a 30 m elevation model.")
    y = D.kpi_big(0.03, y, f"{ts[f'area_slope_ge_{s}pct_in_aoi_km2']:.1f} km²", f"Area with slope ≥ {s}%",
                  "COPERNICUS GLO-30")
    D.kpi_row(0.03, y, "people", "orange", f"Residents on slopes ≥ {s}%", fmt(N["slope"].population))
    D.kpi_row(0.03, y - 0.085, "hex", "purple", f"Buildings on slopes ≥ {s}%", fmt(N["slope"].buildings))
    D.kpi_row(0.03, y - 0.170, "slope", "blue", "Median slope in the perimeter", f"{ts.slope_median_pct_in_aoi:.1f}%")
    D.ring(0.03, y - 0.285, ts[f"area_slope_ge_{s}pct_in_aoi_pct"] / 100,
           f"{ts[f'area_slope_ge_{s}pct_in_aoi_pct']:.1f}%", f"of the perimeter area has slope ≥ {s}%",
           color=OKABE["orange"])

    ax, vx0, vx1 = city_map(D, ctx, labels=True)
    ax.imshow(slope, cmap=ListedColormap(scol), norm=BoundaryNorm(sb, len(slab)), extent=ext,
              interpolation="nearest", zorder=2)

    yy = D.card(CARD_X, 0.585, CARD_W, 0.325, "Slope (%) · EMBRAPA classes")
    legend_swatches(D, CARD_X + 0.016, yy, [(c, l, "box") for c, l in zip(scol[::-1], slab[::-1])], step=0.029)
    legend_swatches(D, CARD_X + 0.016, yy - 0.185, base_items(), size=8.5, step=0.024)
    yy = D.card(CARD_X, 0.335, CARD_W, 0.225, "Why it matters")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"Brazilian federal law 6,766/1979 restricts urban subdivision on slopes of {s}% or more. "
           f"Steep land is concentrated on the western ridge; only {fmt(N['slope'].population)} residents "
           "live on it, but the 30 m model hides short, steep cuts inside the city.", size=9.5)
    yy = D.card(CARD_X, 0.075, CARD_W, 0.235, "Method")
    yy = D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
                "Slope from Copernicus GLO-30 (30 m surface model) with Horn's 3×3 method, reprojected to "
                f"SIRGAS 2000 / UTM 23S. Exposure: building representative point on a cell ≥ {s}%.", size=9,
                spacing=1.45)
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           "A 30 m model smooths short slopes: the steep area is likely underestimated.", size=8.5, color=MUTED,
           spacing=1.4)
    D.footer("Data: IBGE Census 2022 · Google Open Buildings v3 · " + SRC_BASE, REPO)
    print("slope:", *D.save(FIGS / "slope_steep"))
    plt.close(D.fig)


def board_hand(ctx, N, cfg):
    I = cfg["paths"]["interim_p01"]
    h, acc = N["h"], N["acc"]
    hand, _, ext = read_masked(I / f"hand_glo30_acc{acc:g}km2.tif", ctx["extent"], ctx["poly"])
    hb = [0, 1, 2, 3, 5]
    hlab = ["0–1 m", "1–2 m", "2–3 m", "3–5 m"]
    hcol = plt.get_cmap("Blues_r")(np.linspace(0.1, 0.72, 4))
    ha = N["hand_area"]

    D = new_board("Flood-prone lowlands · Montes Claros, Brazil")
    y = D.title(0.03, 0.895, "Flood-prone\nlowlands",
                "Height above the nearest drainage (HAND): land a few metres above a stream is "
                "susceptible to flooding.")
    y = D.kpi_big(0.03, y, f"{ha.area_km2:.1f} km²", f"Area with HAND ≤ {h} m", "COPERNICUS GLO-30")
    D.kpi_row(0.03, y, "people", "blue", f"Residents with HAND ≤ {h} m", fmt(N["flood"].population))
    D.kpi_row(0.03, y - 0.085, "hex", "purple", f"Buildings with HAND ≤ {h} m", fmt(N["flood"].buildings))
    D.kpi_row(0.03, y - 0.170, "drop", "green", "Residents, range for HAND 1–5 m",
              f"{fmt(N['sens'].population.min())}–{fmt(N['sens'].population.max())}")
    D.ring(0.03, y - 0.285, ha.area_pct_of_perimeter / 100, f"{ha.area_pct_of_perimeter:.1f}%",
           f"of the perimeter area has HAND ≤ {h} m", color=OKABE["blue"])

    ax, vx0, vx1 = city_map(D, ctx, labels=True)
    hm = np.where(hand <= 5, hand, np.nan)
    ax.imshow(hm, cmap=ListedColormap(hcol), norm=BoundaryNorm(hb, 4), extent=ext, interpolation="nearest",
              zorder=2)

    yy = D.card(CARD_X, 0.585, CARD_W, 0.325, "HAND (m above drainage)")
    legend_swatches(D, CARD_X + 0.016, yy, [(c, l, "box") for c, l in zip(hcol, hlab)], step=0.031)
    D.fig.text(CARD_X + 0.016, yy - 0.135, f"main threshold: HAND ≤ {h} m\nstreams: drainage ≥ {acc:g} km²",
               fontsize=8.5, color=MUTED, va="top", linespacing=1.35, zorder=3)
    legend_swatches(D, CARD_X + 0.016, yy - 0.185, base_items(), size=8.5, step=0.024)
    yy = D.card(CARD_X, 0.335, CARD_W, 0.225, "Why it matters")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"Flood-prone lowlands hold {fmt(N['flood'].population)} residents, almost all of the exposure found in "
           "this study. They follow the stream valleys that cross the city.", size=9.5)
    yy = D.card(CARD_X, 0.075, CARD_W, 0.235, "Method")
    yy = D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
                f"Copernicus GLO-30 conditioned (fill pits, depressions, flats), D8 flow, streams where drainage "
                f"area ≥ {acc:g} km² (checked against the Atlas streams), HAND with pysheds. "
                f"Threshold h = {h} m fixed before validation.", size=9, spacing=1.45)
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"Terrain susceptibility, not a modelled flood extent. Headwaters < {acc:g} km² are missed.",
           size=8.5, color=MUTED, spacing=1.4)
    D.footer("Data: IBGE Census 2022 · Google Open Buildings v3 · " + SRC_BASE, REPO)
    print("hand:", *D.save(FIGS / "hand_flood_prone"))
    plt.close(D.fig)


def board_hand_vs_sgb(ctx, N, cfg):
    I = cfg["paths"]["interim_p01"]
    h, acc, hv = N["h"], N["acc"], N["hv"]
    hand, tr, ext = read_masked(I / f"hand_glo30_acc{acc:g}km2.tif", ctx["extent"], ctx["poly"])
    sgb = gpd.read_file(cfg["paths"]["sgb_inundation_2014"]).to_crs(ctx["aoi"].crs)
    sgb_hm = rasterize(((g, 1) for g, c in zip(sgb.geometry, sgb.CLASSE) if c[0] in "AM"),
                       out_shape=hand.shape, transform=tr, fill=0).astype(bool)
    inside = np.isfinite(hand)
    h3m = (hand <= h) & inside
    cat = np.full(hand.shape, np.nan)
    cat[h3m & ~sgb_hm] = 0
    cat[~h3m & sgb_hm & inside] = 1
    cat[h3m & sgb_hm] = 2
    ccol = [OKABE["orange"], OKABE["sky_blue"], OKABE["green"]]

    D = new_board("Agreement check · Montes Claros, Brazil")
    y = D.title(0.03, 0.895, "HAND vs the\nofficial chart",
                f"Flood-prone lowlands (HAND ≤ {h} m) compared with the SGB 2014 susceptibility chart. "
                "Agreement check, not validation.")
    y = D.kpi_big(0.03, y, f"{hv.sgb_high_capture_pct:.0f}%", "of SGB 'high' zones captured", "SGB/CPRM 2014")
    D.kpi_row(0.03, y, "drop", "green", "of SGB 'high + medium' captured", f"{hv.sgb_high_medium_capture_pct:.0f}%")
    D.kpi_row(0.03, y - 0.085, "hex", "orange", "of HAND area inside SGB 'high + medium'",
              f"{hv.hand_in_sgb_high_medium_pct:.0f}%")
    D.kpi_row(0.03, y - 0.170, "people", "blue", "Residents: SGB high + medium vs HAND",
              f"{fmt(N['ref'].population)} vs {fmt(N['flood'].population)}")

    ax, vx0, vx1 = city_map(D, ctx, labels=False)
    ax.imshow(cat, cmap=ListedColormap(ccol), vmin=-0.5, vmax=2.5, extent=ext, interpolation="nearest", zorder=2)
    zip_path = cfg["paths"]["sgb_risk_zip"].as_posix()
    sect = gpd.read_file(f"zip://{zip_path}!Shape/MG_MC_SR_CPRM_atualizado.shp").to_crs(ctx["aoi"].crs)
    sect.boundary.plot(ax=ax, color=OKABE["vermillion"], linewidth=1.8, zorder=8)

    yy = D.card(CARD_X, 0.585, CARD_W, 0.325, "Inside the urban perimeter")
    legend_swatches(D, CARD_X + 0.016, yy, [(ccol[0], f"HAND ≤ {h} m only", "box"),
                                            (ccol[1], "SGB 2014 high + medium only", "box"),
                                            (ccol[2], "both", "box"),
                                            (OKABE["vermillion"], "SGB 2012 risk sectors", "line")], step=0.033)
    legend_swatches(D, CARD_X + 0.016, yy - 0.17, base_items(), size=8.5, step=0.026)
    yy = D.card(CARD_X, 0.335, CARD_W, 0.225, "Why it matters")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           "Both layers use height above drainage, so this is agreement, not validation. "
           "The free 30 m model finds most official zones but draws them wider, and misses small headwaters.",
           size=9.5)
    yy = D.card(CARD_X, 0.075, CARD_W, 0.235, "Method")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"HAND ≤ {h} m (GLO-30, drainage ≥ {acc:g} km²) vs SGB/CPRM 2014 inundation classes "
           "'high' (≤ 1.5 m) and 'medium' (1.5–3 m), built from a 2.5 m terrain model and field checks. "
           "30 m cells inside the perimeter.", size=9, spacing=1.45)
    D.footer("Data: SGB/CPRM 2014 susceptibility chart and 2012 risk sectors · " + SRC_BASE, REPO)
    print("hand_vs_sgb:", *D.save(FIGS / "hand_vs_sgb"))
    plt.close(D.fig)


def board_kontur(ctx, N):
    hexes, kv = ctx["hexes"], N["kv"]
    db = [-np.inf, -1000, -250, 250, 1000, np.inf]
    dlab = ["< −1,000", "−1,000 to −250", "−250 to 250", "250 to 1,000", "> 1,000"]
    dcol = plt.get_cmap(carto.DIVERGING)(np.linspace(0.1, 0.9, 5))
    hexes["dcls"] = pd.cut(hexes.diff_kontur_minus_census, bins=db, labels=False)

    D = new_board("Kontur Population check · Montes Claros, Brazil")
    y = D.title(0.03, 0.895, "Kontur Population\nvs Census 2022",
                "Population per H3 hexagon (resolution 8): Kontur 2023 release against the 2022 Census "
                "spread over buildings.")
    y = D.kpi_big(0.03, y, f"r = {kv.pearson_r:.2f}", "Correlation per hexagon", "KONTUR · IBGE")
    D.kpi_row(0.03, y, "people", "purple", "Census 2022 (dasymetric)", fmt(kv.pop_census_dasymetric))
    D.kpi_row(0.03, y - 0.085, "hex", "green", "Kontur Population 2023-11-01", fmt(kv.pop_kontur_2023),
              note=f"{100 * (kv.total_ratio_kontur_over_census - 1):+.0f}%")
    D.kpi_row(0.03, y - 0.170, "sector", "orange", "Median |difference| per hexagon",
              fmt(kv.median_abs_diff_per_cell))

    ax, vx0, vx1 = city_map(D, ctx, labels=False)
    for k, c in enumerate(dcol):
        hexes[hexes.dcls == k].plot(ax=ax, color=c, edgecolor="white", linewidth=0.6, zorder=3)

    yy = D.card(CARD_X, 0.64, CARD_W, 0.27, "Kontur − Census (residents)")
    legend_swatches(D, CARD_X + 0.016, yy, [(c, l, "box") for c, l in zip(dcol[::-1], dlab[::-1])], step=0.031)
    D.fig.text(CARD_X + 0.016, yy - 0.165, "purple = Kontur higher · orange = Kontur lower", fontsize=8.5,
               color=MUTED, va="top", zorder=3)
    # dispersão dentro de um cartão
    D.card(CARD_X, 0.30, CARD_W, 0.315, "Per hexagon")
    a = D.fig.add_axes([CARD_X + 0.045, 0.335, CARD_W - 0.065, 0.215])
    a.set_zorder(6)
    x, yv = hexes.pop_census, hexes.pop_kontur
    lim = max(x.max(), yv.max()) * 1.05
    a.scatter(x, yv, s=9, color=OKABE["blue"], alpha=0.7, linewidths=0)
    a.plot([0, lim], [0, lim], color=MUTED, lw=0.8, ls="--")
    a.set_xlim(0, lim); a.set_ylim(0, lim)
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        a.spines[sp].set_color("#C9CDDC")
    a.tick_params(labelsize=7.5, colors=INK2, length=2)
    a.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    a.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    a.set_xlabel("Census 2022 (dasymetric)", fontsize=8, color=INK2)
    a.set_ylabel("Kontur 2023", fontsize=8, color=INK2)
    yy = D.card(CARD_X, 0.075, CARD_W, 0.20, "Method")
    D.text(CARD_X + 0.014, yy, CARD_W - 0.028,
           f"{int(kv.cells)} hexagons with centre in the perimeter. Census 2022 residents spread over Google "
           "Open Buildings (confidence ≥ 0.75), summed per H3 r8 cell; Kontur Population Brazil, release "
           "2023-11-01 (CC BY 4.0).", size=8.5, spacing=1.4)
    D.footer("Data: Kontur Population (HDX, CC BY 4.0) · IBGE Census 2022 · Google Open Buildings v3 · "
             + SRC_BASE, REPO)
    print("kontur:", *D.save(FIGS / "kontur_vs_census"))
    plt.close(D.fig)


# =============================================================================
def build_context(city: str):
    """Carrega camadas (ctx) e números das tabelas (N). Reusado por 10_one_pager.py."""
    cfg = load_config(city)
    th = cfg["thresholds"]
    conf = th["open_buildings_confidence_main"]
    h, acc, s = th["hand_m_main"], th["stream_threshold_km2_main"], th["slope_pct_legal"]

    aoi = load_aoi(cfg)
    regions = load_planning_regions(cfg)
    streams = prepare_streams(cfg, aoi)
    sa, mun = study_area_table(cfg, aoi, regions)
    ctx = {
        "aoi": aoi, "poly": aoi.geometry.iloc[0], "regions": regions, "streams": streams,
        "extent": tuple(aoi.buffer(900).total_bounds),
        "countries": gpd.read_file(f"zip://{cfg['paths']['world_countries'].as_posix()}"),
        "states": gpd.read_file(cfg["paths"]["brazil_states"]),
        "state_code": cfg["city"]["state_ibge_code"],
        "lonlat": (sa.perimeter_centroid_lon, sa.perimeter_centroid_lat),
        "hexes": gpd.read_file(PROJECT_DIR / "outputs" / "exposure_h3_r8.gpkg").to_crs(aoi.crs),
    }

    ex = pd.read_csv(TABLES / "exposure_summary.csv")
    ex = ex[ex.confidence_min == conf]
    row = lambda hz, par=None: ex[(ex.hazard == hz) & ((ex.parameter == par) if par else True)].iloc[0]
    hv = pd.read_csv(TABLES / "hand_vs_sgb2014.csv")
    ha = pd.read_csv(TABLES / "hand_area_sensitivity.csv")
    N = {
        "h": h, "acc": acc, "s": s,
        "all": row("all buildings in perimeter"), "any": row("any hazard"),
        "flood": row("flood-prone (HAND)", f"HAND <= {h} m; streams >= {acc:g} km2"),
        "slope": row("slope"), "sgb12": row("SGB 2012 risk sector"),
        "ref": row("reference: SGB 2014 inundation"),
        "sens": pd.read_csv(TABLES / "sensitivity_hand.csv"),
        "kv": pd.read_csv(TABLES / "kontur_vs_census_summary.csv").iloc[0],
        "hv": hv[(hv.stream_threshold_km2 == acc) & (hv.hand_m == h)].iloc[0],
        "hand_area": ha[(ha.stream_threshold_km2 == acc) & (ha.hand_m == h)].iloc[0],
        "terrain": pd.read_csv(TABLES / "terrain_summary_glo30.csv").iloc[0],
    }
    return cfg, ctx, N, sa, mun


def main(city: str) -> None:
    cfg, ctx, N, sa, mun = build_context(city)
    board_location(ctx, sa, mun)
    board_hero(ctx, N)
    board_slope(ctx, N, cfg)
    board_hand(ctx, N, cfg)
    board_hand_vs_sgb(ctx, N, cfg)
    board_kontur(ctx, N)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
