"""Grade hexagonal H3 (v4): polígonos -> células e agregação de valores.

A Kontur Population usa H3 resolução 8 (~0,74 km² por célula), por isso
essa é a resolução padrão de agregação do portfólio.
H3 trabalha sempre em coordenadas geográficas (EPSG:4326).
"""

from __future__ import annotations

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon


def polygons_to_cells(gdf: gpd.GeoDataFrame, resolution: int = 8) -> list[str]:
    """Lista as células H3 cujo centro cai dentro dos polígonos de `gdf`.

    Observação: o H3 inclui uma célula quando o *centro* dela está dentro do
    polígono. Bordas da AOI podem ficar parcialmente descobertas; para cobrir
    toda a AOI, aplique um buffer antes (ex.: metade da aresta do hexágono).
    """
    geo = gdf.to_crs("EPSG:4326")
    cells: set[str] = set()
    for geom in geo.geometry:
        # geo_to_cells aceita qualquer objeto com __geo_interface__ (shapely)
        cells.update(h3.geo_to_cells(geom, resolution))
    return sorted(cells)


def cells_to_gdf(cells: list[str]) -> gpd.GeoDataFrame:
    """Converte uma lista de células H3 em um GeoDataFrame de hexágonos (EPSG:4326)."""
    # cell_to_boundary devolve (lat, lng); o shapely espera (x=lng, y=lat)
    polys = [Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in cells]
    return gpd.GeoDataFrame({"h3": list(cells)}, geometry=polys, crs="EPSG:4326")


def points_to_h3(gdf: gpd.GeoDataFrame, resolution: int = 8) -> pd.Series:
    """Devolve o índice H3 de cada ponto (para polígonos, usa o ponto representativo)."""
    geo = gdf.to_crs("EPSG:4326")
    # representative_point fica sempre dentro do polígono (o centroide nem sempre)
    pts = geo.geometry.representative_point()
    return pd.Series(
        [h3.latlng_to_cell(p.y, p.x, resolution) for p in pts], index=gdf.index, name="h3"
    )


def aggregate_to_h3(
    gdf: gpd.GeoDataFrame,
    value_cols: list[str] | None = None,
    resolution: int = 8,
    count_name: str = "n",
) -> gpd.GeoDataFrame:
    """Agrega feições em células H3: contagem e soma das colunas indicadas.

    Cada feição é atribuída a uma única célula, pelo seu ponto representativo.
    Isso serve para objetos pequenos (edificações). Para polígonos grandes
    (ex.: setores censitários), use uma distribuição por área, não esta função.

    Retorna um GeoDataFrame de hexágonos (EPSG:4326) com `count_name` e as somas.
    """
    value_cols = value_cols or []
    df = pd.DataFrame(gdf[value_cols]).copy()
    df["h3"] = points_to_h3(gdf, resolution)
    agg = df.groupby("h3").agg(**{count_name: ("h3", "size")}, **{c: (c, "sum") for c in value_cols})
    hexes = cells_to_gdf(agg.index.tolist())
    return hexes.merge(agg, left_on="h3", right_index=True)
