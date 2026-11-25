"""P01 — passo 11: copia as saídas publicáveis para o site Quarto.

O GitHub Actions renderiza só a pasta site/, então as figuras, o mapa web e o
one-pager precisam estar dentro dela. Só PNG, HTML e PDF já publicados no
repositório (nenhuma geometria restrita, nenhum dado bruto).

Rodar da raiz do repositório (depois de 08, 09 e 10):
    python projects/01-hazard-exposure-montes-claros/scripts/11_site_assets.py
"""

import argparse
import shutil
from pathlib import Path

from geoportfolio.io import load_config

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO = PROJECT_DIR.parents[1]

FILES = [
    "outputs/maps/hero_exposure_h3.png",
    "outputs/maps/location_{city}.png",
    "outputs/figures/hand_flood_prone.png",
    "outputs/figures/slope_steep.png",
    "outputs/figures/hand_vs_sgb.png",          # só existe para cidades com carta do SGB
    "outputs/figures/kontur_vs_census.png",
    "outputs/web/exposure_map.html",
    "outputs/one-pager.pdf",
]


def main(city: str) -> None:
    cfg = load_config(city)
    out = cfg["paths"]["outputs_p01"]                      # pasta outputs/ da cidade
    dest = REPO / "site" / "projects" / cfg["project"]["site_slug"]
    dest.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        src = out.parent / rel.format(city=city)
        if not src.exists():
            print("skipped (not produced for this city):", src.name)
            continue
        shutil.copy2(src, dest / src.name)
        print("copied:", src.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", default="montes_claros")
    main(parser.parse_args().city)
