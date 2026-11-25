"""Painel (dashboard) 16:9 para o mapa principal dos projetos.

Estrutura inspirada em pranchas-painel: coluna de indicadores à esquerda,
mapa ao centro, cartões à direita e rodapé com fontes. Sem marcas
institucionais nem elementos de interface falsos (busca, menus, abas).

A figura é desenhada em 16 × 9 polegadas e salva a 100 dpi = 1600 × 900 px;
o PNG recebe a marcação de 300 dpi (mesmos pixels) e o SVG é vetorial.

Uso típico:
    D = Dashboard("HAZARD EXPOSURE · MONTES CLAROS", "Project 01 ...", "CENSUS 2022 · H3")
    y = D.title(0.03, 0.89, "Who lives in\\nhazard-prone areas", "subtitle")
    D.kpi_big(0.03, y, "25,827", "Residents exposed", "CENSUS 2022")
    ax = D.fig.add_axes([0.225, 0.10, 0.49, 0.81])   # mapa
    D.card(0.735, 0.55, 0.24, 0.36, "Legend")
    D.save("outputs/maps/hero")
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle, Wedge
from matplotlib.patches import Polygon as MplPolygon

from geoportfolio.carto import DPI, OKABE_ITO, wrap

DASH = {
    "bg": "#F2F3F7",      # fundo do painel
    "card": "#FFFFFF",
    "line": "#E3E6EE",
    "ink": "#1E2140",     # texto principal
    "ink2": "#5B607A",    # texto secundário
    "muted": "#9A9FB5",   # notas
    "shadow": "#3A3F6F",
}
FONT = "Segoe UI"
FONT_LIGHT = "Segoe UI Light"
# ladrilhos de ícone: (fundo claro, cor do ícone), cores Okabe-Ito
TILES = {
    "blue": ("#E3EEF8", OKABE_ITO["blue"]),
    "orange": ("#FCEFD9", OKABE_ITO["orange"]),
    "purple": ("#F6E6F0", OKABE_ITO["purple"]),
    "green": ("#DEF3EC", OKABE_ITO["green"]),
    "vermillion": ("#FBE4D9", OKABE_ITO["vermillion"]),
}
W, H = 16, 9   # polegadas


def fmt_int(n) -> str:
    """Inteiro com separador de milhar em inglês (25,827)."""
    return f"{int(round(n)):,}"


def _lines_height(n_lines: int, size: float, spacing: float) -> float:
    """Altura de n linhas de texto em fração da altura da figura."""
    return n_lines * size * spacing / 72 / H


class Dashboard:
    """Painel 16:9. Todas as posições em coordenadas da figura (0–1)."""

    def __init__(self, header_left: str, header_sub: str, header_right: str, header_right_sub: str = ""):
        plt.rcParams.update({"font.family": "sans-serif",
                             "font.sans-serif": [FONT, "Open Sans", "DejaVu Sans"],
                             "text.color": DASH["ink"], "svg.fonttype": "none"})
        self.fig = f = plt.figure(figsize=(W, H), facecolor=DASH["bg"])
        # faixa superior
        f.add_artist(Rectangle((0, 0.93), 1, 0.07, transform=f.transFigure, fc=DASH["card"], ec="none", zorder=0))
        f.add_artist(plt.Line2D([0, 1], [0.93, 0.93], color=DASH["line"], lw=1))
        f.text(0.03, 0.973, header_left, fontsize=12.5, weight="bold", color=DASH["ink"], va="center")
        f.text(0.03, 0.948, header_sub, fontsize=9, color=DASH["ink2"], va="center")
        f.text(0.975, 0.973, header_right, fontsize=9, weight="bold", color=DASH["ink2"], va="center", ha="right")
        if header_right_sub:
            f.text(0.975, 0.948, header_right_sub, fontsize=8.5, color=DASH["muted"], va="center", ha="right")

    # --- blocos de texto e cartões ---------------------------------------------
    def card(self, x, y, w, h, title=None, r=0.012):
        """Cartão branco com sombra suave. Devolve o y livre abaixo do título."""
        f = self.fig
        for k, a in [(0.005, 0.03), (0.003, 0.04), (0.0012, 0.05)]:
            f.add_artist(FancyBboxPatch((x + 0.0006, y - k), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                        transform=f.transFigure, fc=DASH["shadow"], ec="none", alpha=a,
                                        zorder=1, mutation_aspect=W / H))
        f.add_artist(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                    transform=f.transFigure, fc=DASH["card"], ec="none", zorder=2,
                                    mutation_aspect=W / H))
        if title:
            f.text(x + 0.014, y + h - 0.022, title, fontsize=10.5, weight="semibold", color=DASH["ink"],
                   va="top", zorder=3)
            return y + h - 0.058
        return y + h - 0.02

    def text(self, x, y, w, text, size=9.5, color=None, weight="normal", spacing=1.45):
        """Parágrafo com quebra automática na largura w. Devolve o y livre abaixo."""
        # 0,9: folga, porque a largura real dos caracteres varia com a fonte
        t = wrap(text, 0.9 * w * W * DPI, size)
        self.fig.text(x, y, t, fontsize=size, color=color or DASH["ink2"], va="top", weight=weight,
                      linespacing=spacing, zorder=3)
        return y - _lines_height(t.count("\n") + 1, size, spacing) - 0.01

    def title(self, x, y, text, sub=None, size=25, width=0.185):
        f = self.fig
        f.text(x, y, text, fontsize=size, color=DASH["ink"], va="top", weight="semibold", linespacing=1.1)
        y -= _lines_height(text.count("\n") + 1, size, 1.18) + 0.014
        if sub:
            y = self.text(x, y, width, sub, size=10, spacing=1.4)
        return y - 0.012

    def kpi_big(self, x, y, value, label, source=None):
        """Número-destaque com rótulo e fonte. Devolve o y livre abaixo."""
        f = self.fig
        f.text(x, y, label, fontsize=10.5, weight="semibold", color=DASH["ink"], va="top")
        if source:
            f.text(x, y - 0.026, source, fontsize=8, weight="bold", color=DASH["muted"], va="top")
        f.text(x - 0.003, y - 0.042, value, fontsize=46, color=DASH["ink"], va="top", family=FONT_LIGHT)
        return y - 0.145

    def icon(self, x, y, kind, color="blue", s=0.05):
        """Ladrilho quadrado arredondado com um ícone simples em branco."""
        bg, fg = TILES[color]
        ax = self.fig.add_axes([x, y, s * H / W, s])
        ax.set_zorder(6); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.26", fc=fg, ec="none"))
        c, lw = "white", 1.8
        if kind == "drop":        # gota: inundação
            t = np.linspace(0.25 * np.pi, 1.75 * np.pi, 50)
            pts = np.c_[0.5 + 0.18 * np.sin(t), 0.42 + 0.18 * np.cos(t)]
            ax.add_patch(MplPolygon(np.r_[pts, [[0.5, 0.80]]], closed=True, fc="none", ec=c, lw=lw))
        elif kind == "slope":     # encosta
            ax.add_patch(MplPolygon([[0.2, 0.28], [0.8, 0.28], [0.8, 0.74]], closed=True, fc="none", ec=c,
                                    lw=lw, joinstyle="round"))
        elif kind == "sector":    # polígono mapeado em campo
            ax.add_patch(MplPolygon([[0.25, 0.3], [0.45, 0.24], [0.76, 0.38], [0.7, 0.72], [0.36, 0.76],
                                     [0.22, 0.55]], closed=True, fc="none", ec=c, lw=lw, ls=(0, (2.5, 1.5))))
        elif kind == "people":    # pessoas
            for cx in (0.37, 0.63):
                ax.add_patch(Circle((cx, 0.62), 0.09, fc=c, ec="none"))
                ax.add_patch(Wedge((cx, 0.28), 0.16, 0, 180, fc=c, ec="none"))
        elif kind == "hex":       # hexágono H3
            ang = np.radians(np.arange(6) * 60 + 30)
            ax.add_patch(MplPolygon(np.c_[0.5 + 0.27 * np.cos(ang), 0.5 + 0.27 * np.sin(ang)], closed=True,
                                    fc="none", ec=c, lw=lw))
        return ax

    def kpi_row(self, x, y, kind, color, label, value, note=None):
        """Linha de indicador: ícone + rótulo + valor (+ nota curta)."""
        self.icon(x, y - 0.025, kind, color, s=0.05)
        tx = x + 0.05 * H / W + 0.01
        self.fig.text(tx, y + 0.012, label, fontsize=9.5, color=DASH["ink2"], va="center")
        v = self.fig.text(tx, y - 0.012, value, fontsize=13.5, weight="bold", color=DASH["ink"], va="center")
        if note:
            r = self.fig.canvas.get_renderer()
            bb = v.get_window_extent(r).transformed(self.fig.transFigure.inverted())
            self.fig.text(bb.x1 + 0.006, y - 0.012, note, fontsize=8.5, color=DASH["muted"], va="center")

    def ring(self, x, y, pct, value, label, color=None, r=0.042, width=0.12):
        """Anel de proporção (porcentagem no centro) com valor e rótulo ao lado."""
        color = color or OKABE_ITO["vermillion"]
        ax = self.fig.add_axes([x, y - r, 2 * r * H / W, 2 * r])
        ax.set_zorder(6); ax.set_xlim(-1.1, 1.1); ax.set_ylim(-1.1, 1.1); ax.set_aspect("equal"); ax.axis("off")
        ax.add_patch(Wedge((0, 0), 1, 0, 360, width=0.15, fc="#E5E7F0", ec="none"))
        ax.add_patch(Wedge((0, 0), 1, 90 - 360 * pct, 90, width=0.15, fc=color, ec="none"))
        ax.text(0, 0, f"{100 * pct:.1f}%", ha="center", va="center", fontsize=12, color=DASH["ink"])
        tx = x + 2 * r * H / W + 0.012
        self.fig.text(tx, y + 0.006, value, fontsize=13, weight="bold", va="bottom")
        self.text(tx, y - 0.004, width, label, size=9, spacing=1.35)

    def footer(self, left, right=""):
        self.fig.text(0.03, 0.03, wrap(left, 0.80 * W * DPI, 8), fontsize=8, color=DASH["muted"], va="center",
                      linespacing=1.4)
        if right:
            self.fig.text(0.975, 0.03, right, fontsize=8, color=DASH["ink2"], va="center", ha="right", weight="bold")

    def save(self, stem, png_dpi_tag: int = 300):
        """Salva PNG (1600 × 900 px, marcado com 300 dpi) e SVG."""
        from PIL import Image

        stem = Path(stem)
        stem.parent.mkdir(parents=True, exist_ok=True)
        png, svg = stem.with_suffix(".png"), stem.with_suffix(".svg")
        self.fig.savefig(png, dpi=100, facecolor=DASH["bg"])
        self.fig.savefig(svg, facecolor=DASH["bg"])
        # mesmos pixels; só a marcação de resolução muda (para impressão)
        with Image.open(png) as im:
            im.load()
            im.save(png, dpi=(png_dpi_tag, png_dpi_tag))
        return [png, svg]


# --- base comum dos mapas da cidade --------------------------------------------
REGION_LINE = "#4A4F72"   # limites das Regiões de Planejamento (bem visíveis)
STREAM = "#2b7bba"


def city_base(ax, aoi, regions, streams, extent, labels=False, label_size=7.5, fill="white"):
    """Fundo comum: sombra suave, perímetro preenchido, córregos, limites das regiões.

    As camadas temáticas devem usar zorder entre 2 e 3 (acima do preenchimento,
    abaixo dos limites). Devolve os limites visíveis (x0, x1) do mapa.
    """
    import matplotlib.patheffects as pe

    x0, y0, x1, y1 = extent
    poly = aoi.geometry.iloc[0]
    soft_shadow(ax, poly, extent)
    aoi.plot(ax=ax, color=fill, edgecolor="none", zorder=1)
    if streams is not None and len(streams):
        streams.plot(ax=ax, color=STREAM, linewidth=0.9, zorder=4)
    regions.boundary.plot(ax=ax, color=REGION_LINE, linewidth=1.0, zorder=5)
    aoi.boundary.plot(ax=ax, color=DASH["ink"], linewidth=1.6, zorder=6)
    if labels:
        halo = [pe.withStroke(linewidth=2.6, foreground="white")]
        for _, r in regions.iterrows():
            p = r.geometry.representative_point()
            name = r["region"].replace("Induatrial", "Industrial")   # grafia corrigida só no rótulo
            # regiões pequenas (centro) ganham rótulo menor, para não sobrepor
            size = label_size if r.geometry.area > 3e6 else label_size - 1.6
            ax.text(p.x, p.y, name.replace(" ", "\n", 1) if len(name) > 13 else name,
                    ha="center", va="center", fontsize=size, color=DASH["ink"], weight="semibold",
                    linespacing=1.0, zorder=7, path_effects=halo)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.apply_aspect()
    ax.axis("off")
    return ax.get_xlim()


def locator(fig, rect, countries, states, state_code, lonlat, label):
    """Localizador: América do Sul (contexto), Brasil com estados, estado destacado e ponto.

    rect = [x, y, w, h] em coordenadas da figura. Coordenadas geográficas
    (EPSG:4326), com proporção corrigida pela latitude — suficiente para um
    mapa de localização.
    """
    ax = fig.add_axes(rect)
    ax.set_zorder(8)
    sa = countries[countries["CONTINENT"] == "South America"]
    sa.plot(ax=ax, color="#E3E6EE", edgecolor="white", linewidth=0.4)
    states.plot(ax=ax, color="#D3D7E6", edgecolor="white", linewidth=0.4)
    states[states["codarea"].astype(str) == str(state_code)].plot(ax=ax, color="#9AA3C7", edgecolor="white",
                                                                  linewidth=0.4)
    ax.scatter([lonlat[0]], [lonlat[1]], s=26, color=OKABE_ITO["vermillion"], edgecolors="white",
               linewidths=1.0, zorder=5)
    ax.set_xlim(-82, -33)
    ax.set_ylim(-56, 13)
    ax.set_aspect(1 / np.cos(np.radians(15)))
    ax.axis("off")
    ax.text(lonlat[0] + 2, lonlat[1], label, fontsize=7.5, color=DASH["ink"], va="center", weight="semibold",
            path_effects=[__import__("matplotlib.patheffects", fromlist=["withStroke"]).withStroke(
                linewidth=2.2, foreground="white")])
    return ax


# --- elementos de mapa (coordenadas do mapa, em metros) ------------------------
def soft_shadow(ax, geom, extent, res=25, offset=(120, -260), sigma=8, alpha=0.22):
    """Sombra suave deslocada sob um polígono (efeito de "cartão" do perímetro)."""
    from matplotlib.colors import to_rgb
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from scipy import ndimage
    from shapely import affinity

    x0, y0, x1, y1 = extent
    nx, ny = int((x1 - x0) / res), int((y1 - y0) / res)
    tr = from_origin(x0, y1, res, res)
    m = rasterize([(affinity.translate(geom, *offset), 1)], out_shape=(ny, nx), transform=tr, fill=0)
    m = ndimage.gaussian_filter(m.astype(float), sigma)
    rgba = np.zeros((ny, nx, 4))
    rgba[..., :3] = to_rgb(DASH["shadow"])
    rgba[..., 3] = m * alpha
    ax.imshow(rgba, extent=(x0, x1, y0, y1), zorder=0, interpolation="bilinear")


def scalebar(ax, x, y, km=2):
    c = DASH["ink2"]
    ax.plot([x, x + km * 1000], [y, y], color=c, lw=2.2, solid_capstyle="butt", zorder=50)
    for xx in (x, x + km * 1000):
        ax.plot([xx, xx], [y - 90, y + 90], color=c, lw=1, zorder=50)
    ax.text(x + km * 500, y + 170, f"{km} km", ha="center", va="bottom", fontsize=9, color=c, zorder=50)


def north(ax, x, y, h=800):
    c = DASH["ink2"]
    ax.add_patch(MplPolygon([[x, y + h / 2], [x - h * 0.18, y - h / 2], [x, y - h * 0.25]], closed=True,
                            fc=c, ec="none", zorder=50))
    ax.add_patch(MplPolygon([[x, y + h / 2], [x + h * 0.18, y - h / 2], [x, y - h * 0.25]], closed=True,
                            fc="white", ec=c, lw=0.7, zorder=50))
    ax.text(x, y + h / 2 + 120, "N", ha="center", va="bottom", fontsize=10, weight="bold", color=c, zorder=50)


def callout(ax, x, y, name, value, color, dx=0, dy=1200, w=3600, h=900):
    """Balão: ponto no lugar, haste e cartão branco com nome e valor (coordenadas do mapa)."""
    bx, by = x + dx, y + dy
    ax.plot([x, bx], [y, by], color="white", lw=3, zorder=40, solid_capstyle="round")
    ax.plot([x, bx], [y, by], color=DASH["ink2"], lw=0.9, zorder=41)
    ax.scatter([x], [y], s=60, color=color, edgecolors="white", linewidths=1.6, zorder=42)
    ax.add_patch(FancyBboxPatch((bx - w / 2 + 50, by - h / 2 - 70), w, h,
                                boxstyle="round,pad=0,rounding_size=160", fc=DASH["shadow"], ec="none",
                                alpha=0.15, zorder=42))
    ax.add_patch(FancyBboxPatch((bx - w / 2, by - h / 2), w, h, boxstyle="round,pad=0,rounding_size=160",
                                fc="white", ec="#D9DCEA", lw=0.7, zorder=43))
    ax.add_patch(FancyBboxPatch((bx - w / 2 + 150, by - h / 2 + 160), h - 320, h - 320,
                                boxstyle="round,pad=0,rounding_size=100", fc=color, ec="none", zorder=44))
    tx = bx - w / 2 + h + 10
    ax.text(tx, by + 40, name, fontsize=9, color=DASH["ink2"], va="bottom", ha="left", zorder=45)
    ax.text(tx, by - 30, value, fontsize=11.5, weight="bold", color=DASH["ink"], va="top", ha="left", zorder=45)
