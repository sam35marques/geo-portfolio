"""P01 — passo 10: one-pager (1 página A4) do estudo de caso.

Conteúdo pedido pelo modelo de estudo de caso: mapa, 3 números, método em
4 linhas e link. Usa as mesmas camadas e os mesmos números de 08_figures.py
(função build_context), então nada é digitado à mão.

Saídas:
  outputs/one-pager.pdf   A4 retrato, vetorial
  outputs/one-pager.png   prévia (150 dpi) para o site

Rodar da raiz do repositório (depois de 08_figures.py):
    python projects/01-hazard-exposure-montes-claros/scripts/10_one_pager.py
"""

import argparse
import textwrap
import importlib.util
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from geoportfolio import carto
from geoportfolio import dashboard as dash

SCRIPTS = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPTS.parent
OUT = PROJECT_DIR / "outputs"

# 08_figures.py começa com dígito, então não dá para fazer "import 08_figures":
# carregamos o arquivo pelo caminho.
_spec = importlib.util.spec_from_file_location("figures08", SCRIPTS / "08_figures.py")
fig08 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fig08)

A4 = (8.27, 11.69)   # polegadas
INK, INK2, MUTED = dash.DASH["ink"], dash.DASH["ink2"], dash.DASH["muted"]
fmt = dash.fmt_int
URL = "https://sam35marques.github.io/geo-portfolio/projects/hazard-exposure-montes-claros.html"


def card(fig, x, y, w, h):
    """Cartão branco com borda fina (coordenadas da figura)."""
    fig.add_artist(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.008",
                                  transform=fig.transFigure, fc="white", ec=dash.DASH["line"], lw=0.8,
                                  zorder=1, mutation_aspect=A4[0] / A4[1]))


def main(city: str) -> None:
    cfg, ctx, N, sa, mun = fig08.build_context(city)
    plt.rcParams["font.family"] = dash.FONT   # também para o rótulo do localizador
    fig = plt.figure(figsize=A4, facecolor=dash.DASH["bg"])
    F = dash.FONT

    # --- cabeçalho -------------------------------------------------------------
    fig.text(0.06, 0.962, "PROJECT 01 · HAZARD EXPOSURE · MONTES CLAROS, MINAS GERAIS, BRAZIL",
             fontsize=7.5, color=INK2, weight="bold", family=F)
    fig.text(0.06, 0.940, "Who lives in hazard-prone areas?", fontsize=21, color=INK, family=F, va="top",
             weight="semibold")
    share = N["any"].population_pct
    fig.text(0.06, 0.902, textwrap.fill(
        f"About {fmt(round(N['any'].population, -2))} residents ({share:.1f}% of the urban population) live in "
        f"buildings on flood-prone low ground, on slopes ≥ {N['s']}% or in mapped risk sectors.", 92),
        fontsize=10, color=INK2, family=F, va="top", linespacing=1.4)

    # --- mapa ------------------------------------------------------------------
    card(fig, 0.04, 0.395, 0.92, 0.465)
    hexes = ctx["hexes"]
    bins = [0, 50, 200, 500, 1000, np.inf]
    labels = ["1–50", "51–200", "201–500", "501–1,000", "> 1,000"]
    colors = plt.get_cmap(carto.EXPOSURE)(np.linspace(0.15, 0.95, len(labels)))
    hexes["cls"] = pd.cut(hexes.pop_exposed_any, bins=bins, labels=False)
    ax = fig.add_axes([0.05, 0.405, 0.66, 0.445])
    ax.set_zorder(2)   # acima do cartão branco
    vx0, vx1 = dash.city_base(ax, ctx["aoi"], ctx["regions"], ctx["streams"], ctx["extent"])
    hexes[hexes.cls.isna()].plot(ax=ax, color="white", edgecolor="#E4E6F1", linewidth=0.4, zorder=2)
    for k, c in enumerate(colors):
        sub = hexes[hexes.cls == k]
        if len(sub):
            sub.plot(ax=ax, color=c, edgecolor="white", linewidth=0.4, zorder=3)
    x0, y0, x1, y1 = ctx["extent"]
    dash.north(ax, vx1 - 1100, y1 - 1100, h=700)
    dash.scalebar(ax, vx1 - 2600, y0 + 600)
    dash.locator(fig, [0.715, 0.70, 0.19, 0.14], ctx["countries"], ctx["states"], ctx["state_code"],
                 ctx["lonlat"], "Montes Claros")

    # legenda à direita do mapa
    fig.text(0.735, 0.665, "Exposed residents\nper H3 hexagon (r8)", fontsize=8.5, color=INK, weight="semibold",
             family=F, va="top", linespacing=1.3)
    y = 0.618
    for c, lab in list(zip(colors, labels))[::-1] + [("white", "none")]:
        fig.add_artist(plt.Rectangle((0.738, y - 0.006), 0.026, 0.013, transform=fig.transFigure, fc=c,
                                     ec="#C9CDDC" if isinstance(c, str) else "white", lw=0.6, zorder=3))
        fig.text(0.772, y, lab, fontsize=8, color=INK, va="center", family=F, zorder=3)
        y -= 0.021
    y -= 0.008
    for c, lab, lw in [(dash.STREAM, "streams", 1.0), (dash.REGION_LINE, "planning regions", 1.0),
                       (INK, "urban perimeter", 1.6)]:
        fig.add_artist(plt.Line2D([0.738, 0.764], [y, y], transform=fig.transFigure, color=c, lw=lw, zorder=3))
        fig.text(0.772, y, lab, fontsize=8, color=INK, va="center", family=F, zorder=3)
        y -= 0.021
    fig.text(0.738, y - 0.004, "≈ 0.7 km² per hexagon\nSIRGAS 2000 / UTM 23S", fontsize=7, color=MUTED,
             family=F, va="top", linespacing=1.35)

    # --- três números ----------------------------------------------------------
    flood_share = 100 * N["flood"].population / N["any"].population
    kpis = [
        (fmt(N["any"].population), "residents exposed",
         f"{share:.1f}% of {fmt(N['all'].population)} in the urban perimeter"),
        (f"{flood_share:.0f}%", "of them on flood-prone low ground",
         f"HAND ≤ {N['h']} m above the nearest stream"),
        (f"{N['hv'].sgb_high_capture_pct:.0f}%", "of SGB 'high' inundation zones",
         "covered by the HAND zone (agreement, not validation)"),
    ]
    for i, (val, lab, note) in enumerate(kpis):
        x = 0.04 + i * 0.31
        card(fig, x, 0.245, 0.30, 0.13)
        fig.text(x + 0.02, 0.355, val, fontsize=24, color=INK, family=dash.FONT_LIGHT, va="top")
        fig.text(x + 0.02, 0.310, lab, fontsize=8.8, color=INK, weight="semibold", family=F, va="top")
        fig.text(x + 0.02, 0.290, textwrap.fill(note, 44), fontsize=7.3, color=INK2, family=F, va="top",
                 linespacing=1.3)

    # --- método e limites ------------------------------------------------------
    card(fig, 0.04, 0.075, 0.92, 0.152)
    fig.text(0.06, 0.212, "Method", fontsize=10, color=INK, weight="semibold", family=F, va="top")
    steps = [
        "1. Copernicus GLO-30 (30 m): slope (Horn) and HAND, with streams from a 2 km² contributing area.",
        "2. Census 2022 residents spread over Google Open Buildings v3 footprints (dasymetric, by area).",
        "3. A building is exposed when its point falls in a hazard zone; totals by region and H3 r8 cell.",
        f"4. Checked against SGB/CPRM 2014 susceptibility and Kontur Population (r = {N['kv'].pearson_r:.2f}).",
    ]
    fig.text(0.06, 0.190, "\n".join(steps), fontsize=8.2, color=INK2, family=F, va="top", linespacing=1.55)
    s = N["sens"]
    fig.text(0.06, 0.120, textwrap.fill(
        f"Limits: HAND is a terrain index, not a flood model. Residents on flood-prone ground range from "
        f"{fmt(s.population.min())} to {fmt(s.population.max())} across HAND 1–5 m and streams 1–3 km². "
        "Exposure, not risk: no vulnerability component.", 120),
        fontsize=7.5, color=MUTED, family=F, va="top", linespacing=1.4)

    # --- rodapé ----------------------------------------------------------------
    fig.text(0.06, 0.050, "Full case study, code and data sources:", fontsize=8, color=INK2, family=F)
    fig.text(0.06, 0.033, URL, fontsize=8.5, color=carto.OKABE_ITO["blue"], family=F, weight="semibold",
             url=URL)
    fig.text(0.06, 0.014, "Samuel Marques · 2026 · Text and figures CC BY 4.0 · Code MIT · Data: IBGE, Google "
             "Open Buildings, Copernicus, SGB/CPRM, Kontur, Atlas Hidrográfico de Montes Claros",
             fontsize=6.3, color=MUTED, family=F)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "one-pager.pdf", facecolor=dash.DASH["bg"])
    fig.savefig(OUT / "one-pager.png", dpi=150, facecolor=dash.DASH["bg"])
    plt.close(fig)
    print("one-pager:", OUT / "one-pager.pdf", OUT / "one-pager.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
