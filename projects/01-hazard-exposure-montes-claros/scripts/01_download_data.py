"""P01 — passo 1: baixa os dados abertos para data/raw/.

Lê a lista de arquivos de config/<cidade>.yaml (sources.downloads e os tiles
do Copernicus GLO-30). Arquivos que já existem não são baixados de novo
(data/raw é imutável). Ao final grava um log com tamanho e SHA256 de cada
arquivo em data/raw/download_log_<cidade>.csv, para documentar a versão usada.

As edificações (Open Buildings) NÃO entram aqui: vêm do export do GEE
(ver 02_open_buildings_gee.js).

Rodar da raiz do repositório:
    python projects/01-hazard-exposure-montes-claros/scripts/01_download_data.py
"""

import argparse
import hashlib
from datetime import date

import pandas as pd

from geoportfolio.io import download_file, load_config


def sha256(path, block=1 << 20) -> str:
    """Hash SHA256 do arquivo (identifica exatamente a versão baixada)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(block):
            h.update(chunk)
    return h.hexdigest()


def main(city: str) -> None:
    cfg = load_config(city)
    root = cfg["paths"]["root"]
    src = cfg["sources"]

    # lista (nome, url, destino)
    jobs = [(name, d["url"], root / d["dest"]) for name, d in src["downloads"].items()]
    for tile in src["glo30_tiles"]:
        # padrão do nome: Copernicus_DSM_COG_10_S17_00_W044_00_DEM
        stem = f"Copernicus_DSM_COG_10_{tile}_00_DEM"
        jobs.append((f"glo30_{tile}", f"{src['glo30_base_url']}/{stem}/{stem}.tif",
                     root / src["glo30_dir"] / f"{stem}.tif"))

    log = []
    for name, url, dest in jobs:
        download_file(url, dest)
        log.append({
            "id": name,
            "file": dest.relative_to(root).as_posix(),
            "url": url,
            "size_bytes": dest.stat().st_size,
            "sha256": sha256(dest),
            "logged_on": date.today().isoformat(),
        })

    out = root / "data" / "raw" / f"download_log_{city}.csv"
    df = pd.DataFrame(log)
    # mantém registros anteriores (ex.: data do primeiro download) e acrescenta novos
    if out.exists():
        old = pd.read_csv(out)
        df = pd.concat([old, df[~df["file"].isin(old["file"])]], ignore_index=True)
    df.to_csv(out, index=False)
    print(f"\nLog -> {out}")
    print(df[["id", "size_bytes"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
