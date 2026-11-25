"""P01 — passo 11: copia as saídas publicáveis para o site Quarto.

O GitHub Actions renderiza só a pasta site/, então as figuras, o mapa web e o
one-pager precisam estar dentro dela. Só PNG, HTML e PDF já publicados no
repositório (nenhuma geometria restrita, nenhum dado bruto).

Rodar da raiz do repositório (depois de 08, 09 e 10):
    python projects/01-hazard-exposure-montes-claros/scripts/11_site_assets.py
"""

import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO = PROJECT_DIR.parents[1]
DEST = REPO / "site" / "projects" / "hazard-exposure-montes-claros"

FILES = [
    "outputs/maps/hero_exposure_h3.png",
    "outputs/maps/location_montes_claros.png",
    "outputs/figures/hand_flood_prone.png",
    "outputs/figures/slope_steep.png",
    "outputs/figures/hand_vs_sgb.png",
    "outputs/figures/kontur_vs_census.png",
    "outputs/web/exposure_map.html",
    "outputs/one-pager.pdf",
]


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        src = PROJECT_DIR / rel
        shutil.copy2(src, DEST / src.name)
        print("copied:", src.name)


if __name__ == "__main__":
    main()
