"""Edificações, população dasimétrica e exposição.

Dasimetria: a população de cada setor censitário é distribuída entre as
edificações do Open Buildings que estão dentro dele, proporcionalmente à
área construída (área do polígono). Premissa: não distingue uso residencial
de não residencial — isso é uma limitação declarada.
"""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape


def read_open_buildings_csv(path, crs_out: str) -> gpd.GeoDataFrame:
    """Lê o CSV exportado do GEE (geometria GeoJSON na coluna ".geo")."""
    df = pd.read_csv(path)
    geoms = [shape(json.loads(g)) for g in df[".geo"]]
    gdf = gpd.GeoDataFrame(
        df.drop(columns=[".geo"]).rename(columns={"system:index": "ob_id"}),
        geometry=geoms, crs="EPSG:4326",
    )
    return gdf.to_crs(crs_out)


def assign_by_point(points_src: gpd.GeoDataFrame, zones: gpd.GeoDataFrame, cols: list[str]) -> pd.DataFrame:
    """Atribui a cada feição o atributo da zona que contém seu ponto representativo.

    Se o ponto cair em mais de uma zona (sobreposição), fica a primeira.
    Retorna um DataFrame com o mesmo índice de `points_src`.
    """
    pts = gpd.GeoDataFrame(geometry=points_src.geometry.representative_point(), crs=points_src.crs)
    j = gpd.sjoin(pts, zones[cols + ["geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    return j[cols]


def dasymetric_population(buildings: pd.DataFrame, tract_col: str, weight_col: str,
                          tract_pop: pd.Series) -> pd.Series:
    """População de cada edificação = pop. do setor × peso / soma dos pesos do setor.

    buildings : tabela com uma linha por edificação (colunas tract_col, weight_col)
    tract_pop : população por setor (índice = código do setor)
    """
    w = buildings[weight_col]
    w_sum = w.groupby(buildings[tract_col]).transform("sum")
    pop = buildings[tract_col].map(tract_pop).fillna(0)
    return (pop * w / w_sum).fillna(0)
