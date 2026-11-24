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

## 2026-11-24 — P01 analysis frame  [P01]
- Question: how many buildings and people in the urban area of Montes Claros are on (a) slopes ≥ 30%, (b) flood-prone lowlands (HAND ≤ h) and (c) SGB/CPRM high and very high risk sectors? How well does Kontur Population match the 2022 Census there?
- Unit of analysis: the building footprint (exposure); H3 resolution 8 for aggregation, maps and the Kontur comparison.
- Scale: urban area of one medium-sized city. Terrain (flow direction, HAND) is computed over whole drainage basins around the city and clipped afterwards, so drainage is not cut at the AOI edge.
- Validation reference: SGB/CPRM 2012 field-mapped risk sectors (independent of the DEM → no circularity). The 2012 vs ~2022 date gap is a stated limitation.

## 2026-11-24 — P01 AOI = legal urban perimeter, split into Planning Regions  [P01] (revised)
- Decision: AOI = union of the 19 Montes Claros Planning Regions (Regiões de Planejamento), i.e. the urban perimeter (145.2 km², 3 parts). Results are also reported per Planning Region. Census 2010 fields in that file are ignored.
- Population: each 2022 census tract's population is spread over its own buildings (dasymetric step); only buildings inside the perimeter are counted. This handles the 28 tracts cut by the perimeter line (9,155 people) without an arbitrary area rule. Each building is assigned to one region by its representative point (regions overlap by 0.027 km²).
- Alternatives considered: (a) urban 2022 tracts of all districts (includes distant villages); (b) urban tracts of the seat district only (779 tracts, 391,608 people, 102.5 km²).
- Reason: the perimeter is the legal urban area (LC 53/2016) and the Planning Regions are the units used by local planning and research, which makes results actionable. Check: all 779 urban tracts of the seat district lie ≥ 50% inside the perimeter (102.1 of 102.5 km²), so both definitions agree; the perimeter adds sparsely built land.
- Source status: academic origin (Leite, 2006), later adopted by municipal decree 3393/2016 and the Master Plan (LC 53/2016, art. 40); widely used in Unimontes research. Not an internal municipal database. The shapefile stays in `data/raw/` (no explicit redistribution licence); only aggregates per region are published.
- Supersedes: "AOI = 2022 urban census tracts" (same day), and the roadmap note "do not use the municipal urban perimeter", after the author confirmed the file's provenance.

## 2026-11-24 — P01 main DEM = Copernicus GLO-30  [P01]
- Decision: Copernicus DEM GLO-30 is the main DEM. ALOS PALSAR RTC (12.5 m, resampled SRTM) and FABDEM (bare earth, CC BY-NC-SA) are sensitivity runs.
- Alternatives considered: ALOS RTC as main (as first planned in the roadmap); FABDEM as main.
- Reason: GLO-30 is more recent (2011–2015 acquisitions), openly licensed and states its true ~30 m resolution. ALOS RTC 12.5 m suggests detail the source DEM does not have. FABDEM's licence restricts reuse.
- Consequence / sensitivity: all three are surface or near-surface models at ~30 m; results are compared across DEMs in the sensitivity table.

## 2026-11-24 — P01 buildings via Google Earth Engine export  [P01]
- Decision: Open Buildings v3 polygons exported from GEE for the AOI only, with the `longitude_latitude` property removed (it breaks the export). Script versioned in the project.
- Alternatives considered: bulk download of the whole S2 cell CSV (no GEE account, possibly > 1 GB).
- Reason: small file, the author already uses GEE; the script keeps it reproducible.

## 2026-11-24 — P01 main HAND threshold = 3 m, fixed a priori  [P01]
- Decision: h = 3 m is the main flood-prone threshold, fixed **before** looking at the SGB validation. h ∈ {1, 2, 5} m are reported as sensitivity.
- Alternatives considered: 5 m (closer to HAND lowland classes used with 30 m DEMs in the literature); no main value.
- Reason: fixing h first avoids tuning the result to the validation reference; a middle value keeps the headline number from being an extreme.

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
