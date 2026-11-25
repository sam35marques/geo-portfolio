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

## 2026-11-25 — DEM sensitivity: same chain on ALOS RTC and FABDEM, on the GLO-30 grid  [P01]
- Decision: `12_dem_sensitivity.py` reruns slope, flow routing and HAND (streams ≥ 2 km², h = 1/2/3/5 m) on each alternative DEM, after reprojecting it to the exact GLO-30 grid (EPSG:31983, 30 m, bilinear), and samples the same buildings (confidence 0.75). GLO-30 is read from the main-run rasters, so its numbers match `exposure_summary.csv`. The stream threshold stays at 2 km² for all DEMs (not re-tuned per DEM).
- FABDEM comes from a GEE export of the hydrological domain only (`02b_fabdem_gee.js`), not from the 10°×10° Bristol zip (>1 GB).
- Alternatives considered: native ALOS 12.5 m grid (rejected: the source is ~30 m SRTM, and a different grid mixes resolution with DEM effects); re-tuning the stream threshold per DEM against the Atlas (rejected for now: would mix two sources of change).
- Reason: isolate the effect of the elevation source on the exposure count.
- Licence: FABDEM is non-commercial; its raster and derived layers stay in `data/interim/` and are not published; only aggregate rows in `outputs/tables/`.
- First result (ALOS RTC): residents in HAND ≤ 3 m rise from 25,225 (GLO-30) to 34,652; flood-prone area from 18.45 to 20.53 km²; HAND ≤ 3 m zones overlap with Jaccard 67.7%. Steep-slope residents 446 → 370. Agreement with SGB 2014 *high* class is similar (85.4% vs 82.5%). FABDEM pending (GEE export).

## 2026-11-25 — All figures as dashboards; location board; clipped streams; visible regions  [P01, all projects]
- Decision: every P01 figure uses the same 16:9 dashboard (`dashboard.py`): location, hero, steep slopes, flood-prone lowlands (HAND), HAND vs SGB, Kontur vs Census. Slope and HAND are now separate boards.
- Location for non-Brazilian readers: a first board (South America → Brazil/Minas Gerais → municipality → urban perimeter with the 19 named Planning Regions) and a small locator (South America, Brazil states, Minas Gerais, point) in the corner of every city map. Context layers: Natural Earth countries (public domain) and IBGE state boundaries.
- Streams: the Atlas streams are clipped to the urban perimeter in a derived layer (`data/interim/p01/atlas_streams_urban.gpkg`, written by `08_figures.py`); the raw file is unchanged (rule 4).
- Planning Region boundaries drawn in a dark line (#4A4F72, 1 pt) on all city maps; names on the location, slope and HAND boards (smaller font for regions < 3 km²).
- Text claims on the boards come from tables; an unsupported phrase about canalized streams was removed.

## 2026-11-25 — Hero map as a 16:9 dashboard  [P01, all projects]
- Decision: the hero map becomes a dashboard panel (`src/geoportfolio/dashboard.py`): headline number and indicator rows on the left, map in the centre with callouts for the three Planning Regions with most exposed residents, cards on the right (legend, "Why it matters", method), sources in the footer.
- Reference: layout of the author's SIU panel template (indicator column, centre map, cards, callouts, soft shadow under the perimeter). **Not** reused: the municipal brand, footer and tabs — a public personal portfolio must not look like an official City Hall product (CLAUDE.md: no logos, no municipal material). Kept from the portfolio: H3 r8 cells (Kontur standard), Okabe-Ito / YlOrRd colours, English text and number format.
- Format: drawn at 16 × 9 in, saved at 100 dpi = 1600 × 900 px with a 300 dpi tag (same pixels), plus SVG. Font: Segoe UI (Inter not installed).
- Callout positions = exposure-weighted centre of each region's hexagons; region names from the table `exposure_by_region.csv` (one source spelling error fixed only in the label: "Distrito Induatrial").

## 2026-11-25 — Maps: classes, palettes and what the web map may contain  [P01]
- Hero map: exposed residents per H3 r8 hexagon in fixed, readable classes (1–50, 51–200, 201–500, 501–1,000, > 1,000; 100 of 178 cells have exposure, max 1,975), sequential YlOrRd; differences Kontur − Census in a diverging PuOr palette (±250 neutral class). Both colour-blind safe.
- Web map (Folium): contains only aggregates and derived/public layers (H3 hexagons, HAND ≤ 3 m and slope ≥ 30% polygons, SGB 2012 sectors). It does **not** embed the Planning Regions, the urban perimeter or the Atlas streams, because geometries inside an HTML file are effectively redistributed and those files have no redistribution licence. Static maps show them as images, with citation.
- Basemap: OpenStreetMap tiles at reduced opacity (CartoDB tiles now require an API key in this Folium version).

## 2026-11-24 — Exposure rule = building representative point  [P01]
- Decision: a building (and its dasymetric population) is exposed when its representative point falls in a hazard cell (30 m rasters) or polygon (SGB sectors). "Any hazard" = slope ≥ 30% or HAND ≤ 3 m (streams ≥ 2 km²) or SGB 2012 sector.
- Alternatives considered: any footprint overlap (more conservative, inflates large sheds and edges); fraction of footprint area (more precise, harder to explain, fractional building counts).
- Reason: each building counted once; simple to explain and reproduce; for small houses on a 30 m grid the rules differ little.

## 2026-11-24 — Dasymetric population: weights, assignment and export-extent correction  [P01]
- Decision: each building gets the 2022 population of its census tract (v0001) in proportion to its footprint area (`area_in_meters`); building → tract and building → Planning Region by the polygon's representative point; done separately for confidence ≥ 0.65, 0.70, 0.75 (main 0.75).
- Correction: the GEE export covers only a rectangle around the perimeter (+500 m). Tracts extending beyond it would push their whole population onto the few exported buildings (11 rural tracts sent 780 people into the perimeter before the fix; one tract with 32% of its area covered sent 308 of 431 residents). Fix: tract population × fraction of tract area inside the export rectangle (assumes uniform density in the uncovered part). Effect: population in the perimeter 392,764 → 392,218 (−0.14%).
- Alternative not taken: re-export buildings for the full extent of every tract that touches the perimeter (exact, but a new GEE run for a 0.14% effect).
- Limitation to state: no distinction between residential and non-residential buildings; the population of a tract is spread over all its buildings, including sheds, shops and industry.

## 2026-11-24 — Stream initiation threshold = 2 km² (sensitivity 1 and 3 km²)  [P01]
- Decision: drainage cells = flow accumulation ≥ 2 km² (main); HAND is also computed with 1 and 3 km².
- Evidence (`stream_threshold_vs_atlas.csv`, inside the perimeter, 60 m tolerance): at 2 km² the derived network length matches the Atlas network (ratio 0.98), F1 is at its plateau (64.4%; 64.9% at 3 km²), and 96% of canalized reaches are recovered. Natural-reach recall stays at 50–70% for every threshold → positional mismatch (30 m surface model vs streams rectified on 30 cm imagery), not missing network.
- Alternatives considered: 3 km² (similar F1, sparser network); burning the Atlas streams into the DEM (better alignment in the city, but adds a burn-depth parameter and breaks reuse in cities without such a dataset).
- Consequence: the Atlas streams were used to **choose** the threshold, so they are not used afterwards to validate the drainage network. External check of HAND = SGB 2014 chart (agreement, not validation).
- First results (`hand_vs_sgb2014.csv`, `sgb2012_sectors_check.csv`), to carry into Limitations: HAND ≤ 3 m captures 85% of SGB "Alta" and 75% of "Alta+Média", but is broader (only 32% of HAND ≤ 3 m lies in SGB Alta+Média; 60% in any SGB class) — expected from a 30 m surface model vs a 2.5 m terrain model. Disagreement where SGB maps zones the HAND misses is concentrated in **headwaters of streams draining < 2 km²**: the only SGB 2012 flood sector (Vila Itatiaia – Santa Rafaela, Córrego Bicano headwater; max contributing area 2.26 km²) has 7.5% of its cells at HAND ≤ 3 m with the 2 km² network, 21% with 1 km², 0% with 3 km². Exposure along small headwater streams is therefore likely underestimated.

## 2026-11-24 — Close gaps in the union of Planning Regions (5 m)  [P01]
- Decision: the urban perimeter is the union of the 19 regions followed by a 5 m morphological closing (buffer +5 m, then −5 m). Parameter `aoi.gap_closing_m`.
- Reason: the raw union has 101 interior slivers between neighbouring regions (0.012 km², largest 4,074 m²) and 2 tiny detached parts; buildings in them would be dropped. 1–2 m closing leaves 3 holes; 5 m removes all and adds only 0.018 km² (0.01% of 145.2 km²).

## 2026-11-24 — Hydrological domain = urban perimeter + 25 km; pysheds with NumPy shim  [P01]
- Decision: flow routing on GLO-30 reprojected to EPSG:31983 at 30 m (bilinear) over the AOI bounding box + 25 km (2,138 × 2,269 cells); conditioning = fill pits → fill depressions → resolve flats; D8 flow directions (pysheds).
- Reason: the buffer includes the upstream areas of the urban streams so drainage is not cut at the city edge.
- Technical note: pysheds 0.5 calls `np.in1d`, removed in NumPy 2.4; `terrain.flow_routing` aliases it to the equivalent `np.isin` instead of downgrading NumPy for the whole environment.

## 2026-11-24 — Slope by Horn's method  [P01]
- Decision: slope (%) from the 30 m GLO-30 grid with Horn's 3×3 method (same as GDAL/QGIS).
- Note for Limitations: a 30 m surface model smooths short steep slopes, so the area ≥ 30% (2.22% of the perimeter, see `terrain_summary_glo30.csv`) is likely an underestimate.

## 2026-11-24 — P01 reference layers: SGB 2014 susceptibility chart + SGB 2012 sectors  [P01]
- Decision: (1) compare HAND ≤ h and slope ≥ 30% with the SGB/CPRM 2014 susceptibility chart (inundation and mass movement classes) as **agreement with an official susceptibility product**, not as independent validation; (2) use the four 2012 risk sectors as a **qualitative check** (does the flood sector fall in HAND ≤ 3 m; do the landslide sectors fall on slopes ≥ 30%).
- Alternatives considered: only the 2012 sectors (one flood polygon, too few for any metric); flood event records (S2iD), independent but point/text data of uncertain location.
- Why not "validation": the chart's inundation classes are defined by height above the drainage — Alta ≤ 1.5 m, Média 1.5–3 m, Baixa > 3 m (map legend) — i.e. the same principle as HAND. Differences that make the comparison informative: the chart uses a 2.5 m airborne radar DTM (BRADAR, bare earth) plus geomorphology, soils and field checks (2012–2014), while P01 uses a free 30 m DSM. The comparison measures how well the free-data workflow reproduces the official product.
- Note: the main h = 3 m was fixed (decision above) **before** reading the chart legend; it happens to match the chart's Alta+Média break.
- Inside the urban perimeter the chart maps 15.8 km² of inundation susceptibility (Alta 1.4, Média 6.4, Baixa 8.0 km²).

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
