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
# Sequencial padrão para magnitudes (população): "cividis" é
# perceptualmente uniforme e projetado para daltonismo.
SEQUENTIAL = "cividis"
# Exposição a perigo: sequencial quente, luminosidade monotônica (legível
# para daltônicos e em escala de cinza).
EXPOSURE = "YlOrRd"
# Divergente (diferenças, ex.: Kontur − Censo), segura para daltônicos.
DIVERGING = "PuOr"
# Água e drenagem
WATER = "#2b7bba"
NO_DATA_FILL = "#ececec"   # células sem exposição / sem dado


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


def _line_height(fontsize: float, fig_h_px: float, spacing: float = 1.35) -> float:
    """Altura de uma linha de texto em fração da altura da figura."""
    return fontsize * DPI / 72 * spacing / fig_h_px


def wrap(text: str, width_px: float, fontsize: float) -> str:
    """Quebra o texto em linhas que cabem em `width_px` (estimativa pela fonte)."""
    import textwrap

    avg_char_px = fontsize * DPI / 72 * 0.46   # largura média de um caractere
    return textwrap.fill(text, width=max(int(width_px / avg_char_px), 10))


def _header(fig, title: str, subtitle: str, w: int, h: int, title_fs: float, sub_fs: float) -> float:
    """Desenha título e subtítulo (quebrando linhas) e devolve o topo livre (fração)."""
    y = 0.955
    t = wrap(title, 0.94 * w, title_fs)
    fig.text(0.03, y, t, fontsize=title_fs, fontweight="bold", va="top", color=INK)
    y -= _line_height(title_fs, h, 1.25) * (t.count("\n") + 1)
    if subtitle:
        y -= 0.008
        s = wrap(subtitle, 0.94 * w, sub_fs)
        fig.text(0.03, y, s, fontsize=sub_fs, va="top", color=MUTED, linespacing=1.3)
        y -= _line_height(sub_fs, h, 1.3) * (s.count("\n") + 1)
    return y - 0.02


def new_map(title: str, subtitle: str = "", size_px: tuple[int, int] = HERO_PX):
    """Cria a figura com o layout padrão: título no topo, mapa à esquerda,
    painel lateral (legenda e notas) à direita e espaço para o rodapé.

    Retorna (fig, ax_map, ax_side).
    """
    apply_style()
    w, h = size_px
    fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI)
    big = w >= HERO_PX[0]
    top = _header(fig, title, subtitle, w, h, 11 if big else 8, 7 if big else 5.5)

    bottom = 0.13   # espaço para até 3 linhas de rodapé
    ax_map = fig.add_axes([0.03, bottom, 0.62, top - bottom])
    ax_side = fig.add_axes([0.68, bottom, 0.29, top - bottom])
    for ax in (ax_map, ax_side):
        ax.set_xticks([])
        ax.set_yticks([])
    ax_side.axis("off")
    for spine in ax_map.spines.values():
        spine.set_color(LINE)
        spine.set_linewidth(0.4)
    return fig, ax_map, ax_side


def new_panels(title: str, subtitle: str = "", size_px: tuple[int, int] = SECONDARY_PX,
               ncols: int = 2, gap: float = 0.04):
    """Figura com `ncols` painéis lado a lado, título no topo e espaço para rodapé.

    Retorna (fig, [axes]). Os eixos vêm sem marcas; para mapas, chame
    finish_map(fig, ax, ...) em um dos painéis (o rodapé é da figura toda).
    """
    apply_style()
    w, h = size_px
    fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI)
    top = _header(fig, title, subtitle, w, h, 8, 5.5)
    left, right, bottom = 0.03, 0.97, 0.14
    width = (right - left - gap * (ncols - 1)) / ncols
    axes = []
    for i in range(ncols):
        ax = fig.add_axes([left + i * (width + gap), bottom, width, top - bottom])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(LINE)
            spine.set_linewidth(0.4)
        axes.append(ax)
    return fig, axes


def tidy_map_axes(ax) -> None:
    """Remove rótulos de eixo que o GeoPandas/xarray inserem ao plotar camadas."""
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])


def panel_label(ax, text: str) -> None:
    """Rótulo curto no canto superior esquerdo de um painel (ex.: "a) Slope")."""
    ax.text(0.02, 0.98, text, transform=ax.transAxes, ha="left", va="top", fontsize=6,
            fontweight="bold", color=INK,
            bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.8, pad=1.5))


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
    # linhas alinhadas à esquerda, empilhadas de baixo para cima; a linha de
    # fontes é quebrada automaticamente se não couber na largura
    w_px, h_px = fig.get_size_inches() * DPI
    fs = 5 if w_px >= HERO_PX[0] else 4.2
    line2 = f"CRS: {crs_label}  ·  Map: Samuel Marques"
    if note:
        line2 = f"{note}  ·  " + line2
    line1 = wrap(f"Data: {source}", 0.94 * w_px, fs)
    lh = _line_height(fs, h_px, 1.3)
    fig.text(0.03, 0.018, line2, fontsize=fs, color=MUTED, va="bottom")
    fig.text(0.03, 0.018 + lh, line1, fontsize=fs, color=MUTED, va="bottom", linespacing=1.3)


def add_text_block(ax, items, y: float = 1.0, gap: float = 0.4) -> float:
    """Bloco de textos empilhados num eixo (ex.: números-chave no painel lateral).

    items : lista de (texto, tamanho_da_fonte, peso), ex.: ("25,827 people", 10, "bold").
            Texto vazio = espaço extra.
    y     : posição inicial (fração do eixo, de cima para baixo).
    Quebra cada texto na largura do eixo. Retorna o y livre abaixo do bloco.
    """
    fig = ax.figure
    bbox = ax.get_position()
    w_px = bbox.width * fig.get_size_inches()[0] * DPI
    h_px = bbox.height * fig.get_size_inches()[1] * DPI
    for item in items:
        text, size, weight = item[:3]
        color = item[3] if len(item) > 3 else INK   # 4º elemento opcional: cor
        if not text:
            y -= _line_height(size, h_px) * gap * 2
            continue
        t = wrap(text, w_px, size)
        ax.text(0.0, y, t, fontsize=size, fontweight=weight, color=color, va="top",
                transform=ax.transAxes, linespacing=1.3)
        y -= _line_height(size, h_px, 1.3) * (t.count("\n") + 1) + _line_height(size, h_px) * gap
    return y


def add_legend(ax_side, handles, title: str, loc: str = "upper left",
               fontsize: float = 6, bbox_to_anchor=None, ncol: int = 1, frame: bool = False) -> None:
    """Legenda (no painel lateral, sem moldura; ou dentro de um mapa, com frame=True,
    que desenha um fundo branco semitransparente para não se misturar ao mapa)."""
    leg = ax_side.legend(handles=handles, title=title, loc=loc, frameon=frame,
                         fontsize=fontsize, title_fontsize=fontsize + 0.5, alignment="left",
                         bbox_to_anchor=bbox_to_anchor, ncol=ncol, columnspacing=1.2,
                         handlelength=1.6, labelspacing=0.45,
                         borderaxespad=0.4 if frame else 0)
    if frame:
        leg.get_frame().set(facecolor=PAPER, edgecolor="none", alpha=0.85)
    leg.get_title().set_fontweight("bold")
    return leg


def below(ax, artist, pad: float = 0.04) -> float:
    """Posição (fração do eixo) logo abaixo de um elemento já desenhado (ex.: legenda)."""
    fig = ax.figure
    bb = artist.get_window_extent(fig.canvas.get_renderer())
    return bb.transformed(ax.transAxes.inverted()).y0 - pad


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
