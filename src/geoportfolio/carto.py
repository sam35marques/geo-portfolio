"""Estilo cartográfico único do portfólio ("livro didático moderno").

Todo mapa estático passa por aqui, para que os projetos tenham a mesma cara:
- mapa principal 1600×900 px (16:9), PNG com 300 dpi + SVG;
- figuras secundárias 1200×800 px;
- título, subtítulo, legenda, escala, norte, fonte e CRS no rodapé;
- textos em inglês; paletas seguras para daltônicos.

Uso típico:
    fig, ax, side = new_map("Title", "Subtitle")
    gdf.plot(ax=ax, ...)
    add_legend(side, handles, "Legend title")
    finish_map(fig, ax, source="IBGE (2022)", crs_label="SIRGAS 2000 / UTM 23S (EPSG:31983)")
    save_figure(fig, out_dir / "hero_map")
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib_scalebar.scalebar import ScaleBar

# --- Tamanhos-padrão (pixels) e resolução ------------------------------------
DPI = 300
HERO_PX = (1600, 900)
SECONDARY_PX = (1200, 800)

# --- Paleta -------------------------------------------------------------------
# Okabe-Ito: paleta categórica distinguível por pessoas com daltonismo.
OKABE_ITO = {
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "black": "#000000",
}
# Cores neutras do layout
INK = "#222222"        # texto principal
MUTED = "#6b6b6b"      # texto secundário (rodapé, notas)
LINE = "#bdbdbd"       # linhas finas, molduras
PAPER = "#ffffff"      # fundo
AOI_EDGE = "#1a1a1a"   # contorno da área de estudo

# Hipsometria com luminosidade crescente (baixo = escuro, alto = claro),
# legível em escala de cinza e para daltônicos.
HYPSO = LinearSegmentedColormap.from_list(
    "hypso", ["#3b5f4a", "#6f8f5a", "#a9ae73", "#d3c695", "#efe6cf"]
)
# Sequencial padrão para magnitudes (população, exposição): "cividis" é
# perceptualmente uniforme e projetado para daltonismo.
SEQUENTIAL = "cividis"


def apply_style() -> None:
    """Aplica fontes, cores e espessuras padrão ao matplotlib."""
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            # primeira fonte disponível na máquina é usada
            "font.sans-serif": ["Source Sans 3", "Segoe UI", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 6,
            "text.color": INK,
            "axes.edgecolor": LINE,
            "axes.labelcolor": INK,
            "figure.facecolor": PAPER,
            "axes.facecolor": PAPER,
            "savefig.facecolor": PAPER,
            "svg.fonttype": "none",  # texto editável no SVG
        }
    )


def new_map(title: str, subtitle: str = "", size_px: tuple[int, int] = HERO_PX):
    """Cria a figura com o layout padrão: título no topo, mapa à esquerda,
    painel lateral (legenda e notas) à direita e espaço para o rodapé.

    Retorna (fig, ax_map, ax_side).
    """
    apply_style()
    w, h = size_px
    fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI)

    fig.text(0.03, 0.95, title, fontsize=11, fontweight="bold", va="top", color=INK)
    if subtitle:
        fig.text(0.03, 0.885, subtitle, fontsize=7, va="top", color=MUTED)

    ax_map = fig.add_axes([0.03, 0.09, 0.62, 0.76])
    ax_side = fig.add_axes([0.68, 0.09, 0.29, 0.76])
    for ax in (ax_map, ax_side):
        ax.set_xticks([])
        ax.set_yticks([])
    ax_side.axis("off")
    for spine in ax_map.spines.values():
        spine.set_color(LINE)
        spine.set_linewidth(0.4)
    return fig, ax_map, ax_side


def add_north_arrow(ax, xy: tuple[float, float] = (0.95, 0.93)) -> None:
    """Desenha uma seta de norte simples (coordenadas relativas ao eixo).

    Válida quando o norte da grade aponta para cima (caso do UTM, com
    desvio pequeno — convergência meridiana — desprezível nesta escala).
    """
    x, y = xy
    ax.annotate(
        "N", xy=(x, y), xytext=(x, y - 0.09), xycoords="axes fraction",
        ha="center", va="center", fontsize=7, fontweight="bold", color=INK,
        arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.8, mutation_scale=7),
    )


def add_scalebar(ax) -> None:
    """Barra de escala em metros/quilômetros. Exige eixo em CRS métrico."""
    ax.add_artist(
        ScaleBar(1, units="m", location="lower left", length_fraction=0.22,
                 box_alpha=0.75, color=INK, font_properties={"size": 5.5},
                 scale_loc="top", border_pad=0.6)
    )


def add_footer(fig, source: str, crs_label: str, note: str = "") -> None:
    """Rodapé com fonte dos dados, CRS e autoria."""
    # duas linhas, alinhadas à esquerda, para não sobrepor textos longos
    line1 = f"Data: {source}"
    line2 = f"CRS: {crs_label}  ·  Map: Samuel Marques"
    if note:
        line2 = f"{note}  ·  " + line2
    fig.text(0.03, 0.045, line1, fontsize=5, color=MUTED, va="center")
    fig.text(0.03, 0.020, line2, fontsize=5, color=MUTED, va="center")


def add_legend(ax_side, handles, title: str, loc: str = "upper left") -> None:
    """Legenda no painel lateral, sem moldura."""
    leg = ax_side.legend(handles=handles, title=title, loc=loc, frameon=False,
                         fontsize=6, title_fontsize=6.5, alignment="left")
    leg.get_title().set_fontweight("bold")


def add_colorbar(fig, ax_side, mappable, label: str,
                 rect: tuple[float, float, float, float] = (0.70, 0.55, 0.18, 0.025)) -> None:
    """Barra de cores horizontal dentro da área do painel lateral."""
    cax = fig.add_axes(list(rect))
    cb = fig.colorbar(mappable, cax=cax, orientation="horizontal")
    cb.set_label(label, fontsize=6)
    cb.ax.tick_params(labelsize=5, length=2, width=0.4)
    cb.outline.set_linewidth(0.3)


def finish_map(fig, ax, source: str, crs_label: str, note: str = "",
               north: bool = True, scalebar: bool = True) -> None:
    """Acrescenta norte, escala e rodapé ao mapa."""
    ax.set_aspect("equal")
    # remove rótulos de eixo que algumas bibliotecas (xarray/rioxarray) inserem
    ax.set_xlabel("")
    ax.set_ylabel("")
    if north:
        add_north_arrow(ax)
    if scalebar:
        add_scalebar(ax)
    add_footer(fig, source, crs_label, note)


def save_figure(fig, stem: str | Path, formats: tuple[str, ...] = ("png", "svg")) -> list[Path]:
    """Salva em PNG (300 dpi) e SVG com o mesmo nome-base. Retorna os caminhos."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    for fmt in formats:
        p = stem.with_suffix(f".{fmt}")
        fig.savefig(p, dpi=DPI)   # sem bbox_inches="tight": mantém exatamente 1600×900
        paths.append(p)
    return paths


def hillshade(elev: np.ndarray, cellsize: float, azimuth: float = 315,
              altitude: float = 45, z_factor: float = 1.0) -> np.ndarray:
    """Sombreamento de relevo (0–1) a partir de uma matriz de altitudes.

    Matriz em orientação de imagem (linha 0 = norte). Luz padrão vinda de
    noroeste (azimute 315°, altura 45°). Usado só como fundo visual; não
    entra em nenhum cálculo de perigo.
    """
    # np.gradient devolve (d/dlinha, d/dcoluna). Como as linhas crescem para o
    # sul, d/dnorte = -d/dlinha.
    d_row, d_col = np.gradient(elev * z_factor, cellsize)
    dz_dx = d_col          # leste
    dz_dy = -d_row         # norte
    slope = np.arctan(np.hypot(dz_dx, dz_dy))
    # direção para onde a encosta está voltada, em radianos a partir do norte (horário)
    aspect = np.arctan2(-dz_dx, -dz_dy)
    az = np.radians(azimuth)
    alt = np.radians(altitude)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(shade, 0, 1)
