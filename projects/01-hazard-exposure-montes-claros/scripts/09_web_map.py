"""P01 — passo 9: mapa interativo (Folium) para o GitHub Pages.

Camadas (todas ligáveis):
  - Exposed residents per H3 hexagon (popup com os números da célula)
  - Kontur − Census per H3 hexagon
  - Flood-prone lowlands: HAND ≤ 3 m (polígonos simplificados)
  - Slopes ≥ 30%
  - SGB 2012 risk sectors
Fundo: OpenStreetMap com opacidade reduzida (sem chave de API).

Não inclui as geometrias das Regiões de Planejamento, do perímetro nem dos
córregos do Atlas (arquivos sem licença de redistribuição; ver DATA_SOURCES).

Saída: outputs/web/exposure_map.html (HTML autocontido; alvo < 15 MB)

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/09_web_map.py
"""

import argparse
from pathlib import Path

import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask, shapes
from shapely.geometry import shape

from geoportfolio import carto
from geoportfolio.io import load_aoi, load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]


def raster_to_polygons(path, condition, aoi_geom, simplify_m=15):
    """Polígonos das células onde `condition(arr)` é verdadeiro, dentro da AOI."""
    with rasterio.open(path) as src:
        win = rasterio.windows.from_bounds(*aoi_geom.bounds, src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win)
        tr = src.window_transform(win)
        crs = src.crs
    mask = condition(arr) & geometry_mask([aoi_geom], out_shape=arr.shape, transform=tr, invert=True)
    geoms = [shape(g) for g, v in shapes(mask.astype("uint8"), mask=mask, transform=tr) if v == 1]
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
    gdf["geometry"] = gdf.simplify(simplify_m)
    return gdf.dissolve().explode(index_parts=False).to_crs(4326)


def main(city: str) -> None:
    cfg = load_config(city)
    th = cfg["thresholds"]
    I = cfg["paths"]["interim_p01"]
    h_main, acc_main, s_thr = th["hand_m_main"], th["stream_threshold_km2_main"], th["slope_pct_legal"]
    aoi = load_aoi(cfg)
    poly = aoi.geometry.iloc[0]

    hexes = gpd.read_file(PROJECT_DIR / "outputs" / "exposure_h3_r8.gpkg").to_crs(4326)
    for c in ["pop_census", "pop_kontur", "pop_exposed_any", "pop_exposed_flood", "pop_exposed_slope", "diff_kontur_minus_census"]:
        hexes[c] = hexes[c].round(0).astype(int)
    hexes["share_exposed_pct"] = (100 * hexes.share_exposed_any).round(1)

    c = hexes.geometry.union_all().centroid
    m = folium.Map(location=[c.y, c.x], zoom_start=12, tiles=None, control_scale=True)
    # fundo OpenStreetMap (sem chave de API), com opacidade reduzida para ficar discreto
    attrib = ('© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · '
              "Data: IBGE Census 2022 · Google Open Buildings v3 · Copernicus GLO-30 · "
              "Kontur Population (CC BY 4.0) · SGB/CPRM 2012 · Map: Samuel Marques")
    folium.TileLayer("OpenStreetMap", attr=attrib, name="Basemap", opacity=0.45, control=False).add_to(m)

    # --- Exposed residents --------------------------------------------------------
    bins = [0, 1, 51, 201, 501, 1001, 1e9]
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_hex
    cols = ["#ececec"] + [to_hex(x) for x in plt.get_cmap(carto.EXPOSURE)(np.linspace(0.15, 0.95, 5))]

    def color_exposed(v):
        return cols[int(np.searchsorted(bins, v, side="right") - 1)]

    fields = ["h3", "pop_exposed_any", "share_exposed_pct", "pop_exposed_flood", "pop_exposed_slope",
              "pop_census", "pop_kontur", "buildings"]
    aliases = ["H3 cell", "Exposed residents (any hazard)", "Share of residents exposed (%)",
               f"…in flood-prone lowlands (HAND ≤ {h_main} m)", f"…on slopes ≥ {s_thr}%",
               "Residents (Census 2022, dasymetric)", "Kontur Population 2023", "Buildings (confidence ≥ 0.75)"]
    folium.GeoJson(
        hexes[fields + ["geometry"]], name="Exposed residents per hexagon",
        style_function=lambda f: {"fillColor": color_exposed(f["properties"]["pop_exposed_any"]),
                                  "color": "white", "weight": 0.6, "fillOpacity": 0.8},
        highlight_function=lambda f: {"weight": 2, "color": "#222222"},
        tooltip=folium.GeoJsonTooltip(fields=fields, aliases=aliases, localize=True),
    ).add_to(m)

    # --- Kontur − Census ----------------------------------------------------------
    div = cm.LinearColormap([to_hex(x) for x in plt.get_cmap(carto.DIVERGING)(np.linspace(0.1, 0.9, 5))],
                            vmin=-2000, vmax=2000, caption="Kontur − Census (residents per hexagon)")
    folium.GeoJson(
        hexes[["h3", "pop_kontur", "pop_census", "diff_kontur_minus_census", "geometry"]],
        name="Kontur − Census per hexagon", show=False,
        style_function=lambda f: {"fillColor": div(np.clip(f["properties"]["diff_kontur_minus_census"], -2000, 2000)),
                                  "color": "white", "weight": 0.6, "fillOpacity": 0.8},
        tooltip=folium.GeoJsonTooltip(fields=["h3", "pop_kontur", "pop_census", "diff_kontur_minus_census"],
                                      aliases=["H3 cell", "Kontur 2023", "Census 2022 (dasymetric)", "Kontur − Census"],
                                      localize=True),
    ).add_to(m)

    # --- HAND e declividade ----------------------------------------------------------
    hand = raster_to_polygons(I / f"hand_glo30_acc{acc_main:g}km2.tif", lambda a: a <= h_main, poly)
    folium.GeoJson(hand, name=f"Flood-prone lowlands (HAND ≤ {h_main} m)", show=False,
                   style_function=lambda f: {"fillColor": carto.OKABE_ITO["blue"], "color": carto.OKABE_ITO["blue"],
                                             "weight": 0.3, "fillOpacity": 0.45}).add_to(m)
    steep = raster_to_polygons(I / "slope_pct_glo30.tif", lambda a: a >= s_thr, poly, simplify_m=10)
    folium.GeoJson(steep, name=f"Slopes ≥ {s_thr}%", show=False,
                   style_function=lambda f: {"fillColor": carto.OKABE_ITO["vermillion"], "color": carto.OKABE_ITO["vermillion"],
                                             "weight": 0.3, "fillOpacity": 0.55}).add_to(m)

    # --- SGB 2012 --------------------------------------------------------------------
    zip_path = cfg["paths"]["sgb_risk_zip"].as_posix()
    sect = gpd.read_file(f"zip://{zip_path}!Shape/MG_MC_SR_CPRM_atualizado.shp").to_crs(4326)
    sect = sect[["NUM_SETOR", "LOCAL", "TIPOLOGIA", "GRAU_RISCO", "geometry"]]
    folium.GeoJson(sect, name="SGB 2012 risk sectors",
                   style_function=lambda f: {"fillColor": "none", "color": carto.OKABE_ITO["vermillion"], "weight": 2},
                   tooltip=folium.GeoJsonTooltip(fields=["NUM_SETOR", "LOCAL", "TIPOLOGIA", "GRAU_RISCO"],
                                                 aliases=["Sector", "Place", "Process", "Risk level"])).add_to(m)

    # --- legenda e créditos ----------------------------------------------------------
    # Legenda e controles compactos: o mapa é embutido num quadro (iframe) no site,
    # então nada pode cobrir boa parte dele. A legenda é recolhível (<details>) e
    # a lista de camadas fica fechada num ícone (abre ao passar o mouse ou tocar).
    # Legenda horizontal (uma faixa de cores com rótulos embaixo), no canto inferior
    # direito, que fica livre porque a cidade está à esquerda do centro.
    labels = ["0", "1–50", "51–200", "201–500", "501–1k", ">1k"]
    items = "".join(f'<div style="text-align:center;width:42px;white-space:nowrap"><div style="background:{c};height:9px;'
                    f'border:1px solid #ccc"></div>{l}</div>' for c, l in zip(cols, labels))
    legend = (f'<details open class="p01-legend" style="position:fixed;bottom:30px;right:10px;z-index:9999;'
              f'background:rgba(255,255,255,.92);padding:4px 7px;font:10px sans-serif;line-height:1.3;'
              f'border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.3)">'
              f'<summary style="cursor:pointer;font-weight:bold;font-size:11px">Exposed residents per hexagon'
              f'</summary><div style="display:flex;gap:1px;margin-top:3px">{items}</div>'
              f'<div style="margin-top:3px;color:#666">HAND: terrain susceptibility, not a flood model</div>'
              f'</details>')
    m.get_root().html.add_child(folium.Element(legend))
    title = ('<div class="p01-title" style="position:fixed;top:10px;left:50px;z-index:9999;'
             'background:rgba(255,255,255,.92);padding:4px 8px;font:12px sans-serif;border-radius:4px;'
             'box-shadow:0 1px 4px rgba(0,0,0,.3)"><b>Hazard exposure in Montes Claros</b> · H3 r8</div>')
    m.get_root().html.add_child(folium.Element(title))
    m.get_root().html.add_child(folium.Element(
        "<style>.leaflet-control-attribution{font-size:9px}"
        ".leaflet-control-layers-expanded{font-size:11px}"
        # quadro estreito (celular): título some e a legenda começa recolhida pelo script abaixo
        "@media (max-width:600px){.p01-title{display:none}}</style>"
        "<script>if (window.innerWidth < 600) {document.addEventListener('DOMContentLoaded', function () {"
        "var d = document.querySelector('.p01-legend'); if (d) d.removeAttribute('open');});}</script>"))
    folium.LayerControl(collapsed=True).add_to(m)
    # enquadra a cidade inteira no quadro, qualquer que seja o tamanho
    b = hexes.total_bounds
    m.fit_bounds([[b[1], b[0]], [b[3], b[2]]], padding=(10, 10))

    out = PROJECT_DIR / "outputs" / "web" / "exposure_map.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save(out)
    print(f"-> {out} ({out.stat().st_size / 1e6:.1f} MB) | HAND polígonos: {len(hand)} | declividade: {len(steep)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
