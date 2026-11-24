"""Leitura da configuração da cidade e dos dados.

Ideia central: nenhum caminho ou parâmetro fica "fixo" no código.
Tudo vem de config/<cidade>.yaml, carregado por load_config().
"""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

import geopandas as gpd
import yaml


def repo_root() -> Path:
    """Devolve a pasta raiz do repositório (onde está o environment.yml).

    Sobe a partir deste arquivo até achar o environment.yml. Assim os
    caminhos funcionam igual em notebooks, scripts ou no terminal.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "environment.yml").exists():
            return parent
    raise FileNotFoundError("Raiz do repositório não encontrada (environment.yml ausente).")


def load_config(city: str = "montes_claros") -> dict:
    """Carrega config/<city>.yaml e converte os caminhos em Path absolutos.

    Parâmetros
    ----------
    city : nome do arquivo YAML sem extensão (ex.: "montes_claros").

    Retorna
    -------
    dict com a configuração; cfg["paths"][...] já são objetos Path.
    """
    root = repo_root()
    cfg_file = root / "config" / f"{city}.yaml"
    with open(cfg_file, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["paths"] = {k: root / v for k, v in cfg["paths"].items()}
    cfg["paths"]["root"] = root
    return cfg


def download_file(url: str, dest: Path, overwrite: bool = False) -> Path:
    """Baixa um arquivo para `dest`, se ele ainda não existir.

    Arquivos em data/raw/ são imutáveis: por padrão, nunca sobrescreve.
    """
    dest = Path(dest)
    if dest.exists() and not overwrite:
        print(f"Já existe, não baixado de novo: {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {url}\n  -> {dest}")
    # User-Agent genérico: alguns servidores recusam o padrão do Python
    req = urllib.request.Request(url, headers={"User-Agent": "geoportfolio/0.1"})
    # grava primeiro num arquivo ".part" e só renomeia no fim: se a conexão
    # cair, não fica um arquivo incompleto com o nome definitivo em data/raw
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)  # copia em blocos de 1 MB
    part.replace(dest)
    return dest


def load_municipality(cfg: dict, to_crs: str | None = None) -> gpd.GeoDataFrame:
    """Lê o limite municipal do IBGE (baixa se necessário) e reprojeta.

    Parâmetros
    ----------
    cfg    : configuração devolvida por load_config().
    to_crs : CRS de saída; padrão = CRS métrico da cidade (cfg["crs"]["metric"]).
    """
    path = download_file(cfg["sources"]["municipality_url"], cfg["paths"]["municipality"])
    gdf = gpd.read_file(path)
    # A API de malhas do IBGE entrega em SIRGAS 2000 geográfico (EPSG:4674);
    # se o arquivo vier sem CRS declarado, assumimos esse valor.
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4674")
    return gdf.to_crs(to_crs or cfg["crs"]["metric"])


def load_planning_regions(cfg: dict, to_crs: str | None = None) -> gpd.GeoDataFrame:
    """Lê as Regiões de Planejamento e mantém só o nome e a geometria.

    Os demais campos do arquivo (dados do Censo 2010) são descartados de
    propósito: a população vem do Censo 2022.
    """
    name_field = cfg["aoi"]["region_name_field"]
    rp = gpd.read_file(cfg["paths"]["planning_regions"])
    rp = rp[[name_field, "geometry"]].rename(columns={name_field: "region"})
    return rp.to_crs(to_crs or cfg["crs"]["metric"])


def load_aoi(cfg: dict, to_crs: str | None = None) -> gpd.GeoDataFrame:
    """Devolve a área de estudo (AOI) conforme cfg["aoi"], com buffer opcional.

    Sempre retorna um único polígono (dissolvido), no CRS métrico salvo indicação.
    """
    source = cfg["aoi"]["source"]
    if source == "ibge_municipality":
        aoi = load_municipality(cfg, to_crs=cfg["crs"]["metric"])
    elif source == "planning_regions":
        rp = load_planning_regions(cfg)
        # união de todas as regiões = perímetro urbano.
        # A união deixa frestas entre regiões vizinhas (101 buracos, 0,012 km²).
        # Um "fechamento" (buffer +d e depois -d) elimina as frestas sem mexer
        # no contorno externo de forma relevante (d em config: aoi.gap_closing_m).
        d = cfg["aoi"].get("gap_closing_m", 0) or 0
        geom = rp.union_all()
        if d:
            geom = geom.buffer(d).buffer(-d)
        aoi = gpd.GeoDataFrame({"name": ["urban perimeter"]}, geometry=[geom], crs=rp.crs)
    else:
        raise NotImplementedError(f"Fonte de AOI ainda não implementada: {source}")

    buffer_m = cfg["aoi"].get("buffer_m", 0) or 0
    if buffer_m:
        # o buffer é feito no CRS métrico, para que a distância seja em metros
        aoi = aoi.copy()
        aoi["geometry"] = aoi.buffer(buffer_m)
    return aoi.to_crs(to_crs) if to_crs else aoi
