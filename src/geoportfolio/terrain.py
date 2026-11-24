"""Terreno: mosaico e reprojeção do MDE, declividade, fluxo e HAND.

Fluxo típico (ver projects/01-.../scripts/03_terrain.py):
    dem = mosaic_reproject(tiles, bounds, "EPSG:31983", 30)
    slope = slope_percent(dem_array, 30)
    fdir, acc, dem_cond = flow_routing(dem_path)
    streams = acc_km2 >= limiar
    hand = compute_hand(...)

HAND (Height Above Nearest Drainage): para cada célula, a diferença de
altitude entre ela e a célula de drenagem para onde a água dela escoa.
Valores baixos = terreno próximo do nível do córrego = suscetível a inundação.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import reproject


def mosaic_reproject(
    tiles: list[Path],
    bounds: tuple[float, float, float, float],
    dst_crs: str,
    resolution: float,
    out_path: Path,
) -> Path:
    """Junta os tiles do MDE e reprojeta para uma grade regular no CRS métrico.

    Parâmetros
    ----------
    tiles      : arquivos GeoTIFF de origem (mesmo CRS entre si).
    bounds     : (xmin, ymin, xmax, ymax) da grade de saída, em `dst_crs`.
    dst_crs    : CRS de saída (ex.: "EPSG:31983").
    resolution : tamanho do pixel de saída em metros.
    out_path   : GeoTIFF (COG) de saída, float32, NoData = NaN.

    A grade é alinhada a múltiplos de `resolution`, para que todos os
    rasters derivados (declividade, HAND...) fiquem exatamente sobrepostos.
    """
    xmin, ymin, xmax, ymax = bounds
    # alinha os limites à grade
    xmin = np.floor(xmin / resolution) * resolution
    ymin = np.floor(ymin / resolution) * resolution
    xmax = np.ceil(xmax / resolution) * resolution
    ymax = np.ceil(ymax / resolution) * resolution
    width = int(round((xmax - xmin) / resolution))
    height = int(round((ymax - ymin) / resolution))
    dst_transform = from_origin(xmin, ymax, resolution, resolution)

    srcs = [rasterio.open(t) for t in tiles]
    try:
        mosaic, src_transform = merge(srcs)  # junta os tiles na grade original
        src_crs = srcs[0].crs
        src_nodata = srcs[0].nodata
    finally:
        for s in srcs:
            s.close()

    dst = np.full((height, width), np.nan, dtype="float32")
    reproject(
        source=mosaic[0].astype("float32"),
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=src_nodata,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,  # variável contínua (altitude)
    )
    write_raster(dst, out_path, dst_transform, dst_crs)
    return out_path


def write_raster(arr: np.ndarray, path: Path, transform, crs, nodata=np.nan) -> Path:
    """Grava uma matriz 2D como Cloud-Optimized GeoTIFF (COG), compressão DEFLATE."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dtype = arr.dtype if arr.dtype != np.float64 else np.float32
    profile = dict(
        driver="COG", height=arr.shape[0], width=arr.shape[1], count=1,
        dtype=dtype, crs=crs, transform=transform, nodata=nodata, compress="DEFLATE",
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(dtype), 1)
    return path


def slope_percent(elev: np.ndarray, cellsize: float) -> np.ndarray:
    """Declividade em porcentagem pelo método de Horn (3×3), o mesmo do GDAL/QGIS.

    declividade (%) = 100 × sqrt((dz/dx)² + (dz/dy)²)
    As bordas e as células vizinhas de NoData ficam como NaN.
    """
    z = np.pad(elev.astype("float64"), 1, mode="constant", constant_values=np.nan)
    # vizinhos: a b c / d e f / g h i
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cellsize)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cellsize)
    return (100 * np.hypot(dzdx, dzdy)).astype("float32")


def flow_routing(dem_path: Path):
    """Condiciona o MDE e calcula direção (D8) e acumulação de fluxo com pysheds.

    Etapas de condicionamento (padrão em hidrologia com MDE):
    1. fill_pits: remove depressões de 1 célula (ruído);
    2. fill_depressions: preenche depressões maiores, para a água não "ficar presa";
    3. resolve_flats: dá um leve gradiente às áreas planas criadas no passo 2.

    Retorna (grid, dem_condicionado, fdir, acc), todos objetos do pysheds.
    `acc` = número de células a montante (multiplique pela área da célula
    para obter a área de contribuição).
    """
    # Compatibilidade: o pysheds 0.5 chama np.in1d, removida no NumPy >= 2.4.
    # np.isin faz a mesma operação; criamos o apelido só se ele não existir.
    if not hasattr(np, "in1d"):
        np.in1d = lambda ar1, ar2, **kw: np.isin(np.ravel(ar1), ar2, **kw)

    from pysheds.grid import Grid  # import local: só quem usa fluxo precisa do pysheds

    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))
    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)
    fdir = grid.flowdir(inflated)          # D8, codificação ESRI (1,2,4,...,128)
    acc = grid.accumulation(fdir)
    return grid, inflated, fdir, acc


def compute_hand(grid, dem, fdir, streams: np.ndarray):
    """HAND: altura de cada célula acima da célula de drenagem para onde escoa.

    `streams` é uma máscara booleana (True = célula de drenagem).
    Usa o MDE condicionado, coerente com as direções de fluxo.
    """
    from pysheds.sview import Raster

    # o pysheds exige um objeto Raster com a mesma georreferência da grade
    mask = Raster(np.asarray(streams, dtype=bool), viewfinder=fdir.viewfinder)
    return grid.compute_hand(fdir, dem, mask)
