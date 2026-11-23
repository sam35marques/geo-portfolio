# Decisions log

Every choice of data, threshold or method is recorded here, newest first.

**Entry format**

```
## YYYY-MM-DD — Short title  [project]
- Decision:
- Alternatives considered:
- Reason:
- Consequence / sensitivity:
```

Before modelling, each project also records its **analysis frame**: question, unit of analysis, scale, validation reference.

---

## 2026-11-23 — Exact 1600×900 px figure size at 300 dpi  [all]
- Decision: hero maps are 5.33 × 3 in at 300 dpi (= exactly 1600 × 900 px). Font sizes are set small (5–11 pt) to match.
- Alternatives considered: a larger canvas (e.g. 16 × 9 in at 300 dpi = 4800 × 2700 px).
- Reason: CLAUDE.md asks for 1600 × 900 px and 300 dpi; only this size meets both. SVG is also saved for print quality.
- Consequence / sensitivity: if larger prints are needed later, change `carto.HERO_PX` only.

## 2026-11-23 — Extra package: matplotlib-scalebar  [all]
- Decision: add `matplotlib-scalebar` to `environment.yml`.
- Alternatives considered: drawing the scale bar by hand in `carto.py`.
- Reason: CLAUDE.md requires a scale bar on every static map; the package is small, maintained, and on conda-forge.

## 2026-11-23 — Extra packages: pyogrio, gdal, ipykernel  [all]
- Decision: list them explicitly in `environment.yml`.
- Reason: pyogrio is GeoPandas' fast I/O engine (GeoPackage); gdal gives the command-line tools; ipykernel registers the environment in Jupyter.

## 2026-11-23 — DEM reprojected from WGS 84 / UTM 23S to SIRGAS 2000 / UTM 23S  [P01]
- Decision: keep `data/raw/dem/alos_palsar/moc_dem.tif` untouched (EPSG:32723); clip it to the AOI and reproject to EPSG:31983 with bilinear resampling into `data/interim/shared/`.
- Alternatives considered: work in EPSG:32723; only redefine the CRS label without resampling.
- Reason: CLAUDE.md fixes EPSG:31983 as the metric CRS. WGS 84 and SIRGAS 2000 differ by < 1 m in Brazil, far below the DEM's ~30 m effective resolution, so the resampling effect is negligible. Bilinear suits a continuous variable.

## 2026-11-23 — Provisional AOI = IBGE municipal boundary  [Phase 0]
- Decision: Phase 0 test map uses the whole municipality boundary from the IBGE mesh API.
- Alternatives considered: urban census tracts 2022; IBGE urbanized areas.
- Reason: small, open, scriptable download, enough to test the pipeline. **Project 1 will replace it** with the 2022 urban census tracts or IBGE urbanized area (decision to be taken with the author). The municipal perimeter from the city hall is not used (rule 1).

## 2026-11-23 — Python environment via Miniforge (conda-forge)  [all]
- Decision: Miniforge3 + `environment.yml` (Python 3.11, conda-forge only).
- Alternatives considered: Anaconda; system Python 3.12 with pip.
- Reason: Miniforge defaults to conda-forge and has no commercial-licence restrictions; pip installs of GDAL/rasterio on Windows often break.
