# Data sources

All data used in this repository are open and citable. Raw files live in `data/raw/` (not in Git). Each entry says how to get the file again.

**Entry format**

| Field | Content |
|---|---|
| ID | short name used in `config/*.yaml` |
| Layer / project | what it is and which project uses it |
| Provider and URL | |
| Version / file | exact file name, version, granule or tile ID |
| Access date | YYYY-MM-DD |
| License | |
| Citation | as requested by the provider |
| How to download | script or manual steps |
| Local path | under `data/raw/` |
| Notes | resolution, known errors, CRS |

---

## dem_alos_palsar — ALOS PALSAR RTC DEM (12.5 m)

| Field | Content |
|---|---|
| Layer / project | Digital elevation model · P01 (slope, HAND) |
| Provider and URL | Alaska Satellite Facility (ASF DAAC), https://search.asf.alaska.edu/ |
| Version / file | `moc_dem.tif` (mosaic/clip prepared by the author). **Original granule ID(s): to confirm with the author** |
| Access date | **to confirm** (local file dated 2025-04-07) |
| License | ASF DAAC data use terms; DEM derived from SRTM (public domain). Cite as below |
| Citation | ASF DAAC (2015). ALOS PALSAR Radiometric Terrain Corrected high res. Includes material © JAXA/METI 2007. https://doi.org/10.5067/Z97HFCNKR6VA (**DOI to verify on the ASF page before publishing**) |
| How to download | ASF Vertex → ALOS PALSAR → RTC High-Res product (zip contains `*.dem.tif`) |
| Local path | `data/raw/dem/alos_palsar/moc_dem.tif` |
| Notes | GeoTIFF, UInt16, NoData 32767, LZW; 11120 × 14624 px at 12.5 m; CRS **WGS 84 / UTM 23S (EPSG:32723)**; extent ≈ 44.44–43.13°W, 15.61–17.26°S; elevation 462–1226 m (GDAL statistics). The 12.5 m DEM in RTC products is **resampled from a ~30 m source DEM (SRTM)**, so effective resolution is ~30 m. It is a surface model (includes buildings/trees). SHA256 `6E8131EE1DF8B1577502C6EDCF7D077848DE8A724B826460A76762C7E0E11DEB` |

## planning_regions — Planning Regions of Montes Claros (urban perimeter)

| Field | Content |
|---|---|
| Layer / project | Urban perimeter split into 19 Planning Regions · P01 AOI and reporting units |
| Provider and URL | Academic origin: LEITE, M. E. (2006), master's dissertation, Universidade Federal de Uberlândia (UFU). Adopted by Decreto Municipal 3393/2016 and Plano Diretor de Montes Claros, LC nº 53/2016, art. 40. File updated with Census 2010 attributes by S. Marques |
| Version / file | `Regioes_Planejamento_atualizados2.shp` (from `.rar` dated 2026-04-13) |
| Access date | 2026-11-24 (provided by the author) |
| License | No explicit licence. Used with citation; raw file **not redistributed** in this repository, only aggregates per region |
| Citation | LEITE, M. E. Geoprocessamento aplicado ao estudo do espaço urbano: o caso da cidade de Montes Claros/MG. Dissertação (Mestrado) — Universidade Federal de Uberlândia, Uberlândia, 2006; Montes Claros, Lei Complementar nº 53/2016, art. 40; Decreto nº 3393/2016 |
| How to download | Not publicly downloadable; available from the author / Unimontes research groups on request |
| Local path | `data/raw/boundaries/regioes_planejamento/` |
| Notes | EPSG:31983; 19 regions; union = 145.2 km² in 3 parts; neighbouring regions overlap by 0.027 km² (each building assigned to one region). Census 2010 fields ignored. Region name field: `Nome_Polo` (one spelling error in the source: "Distrito Induatrial") |

## ibge_census_2022 — Census tracts with population, Minas Gerais

| Field | Content |
|---|---|
| Layer / project | 2022 census tracts with aggregate attributes · P01 population (dasymetric step) |
| Provider and URL | IBGE, https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/malha_com_atributos/setores/gpkg/UF/MG/ |
| Version / file | `MG_setores_CD2022.gpkg` (server date 2024-11-13); data dictionary `dicionario_de_dados_agregados_por_setores_censitarios_20261113.xlsx` |
| Access date | 2026-11-24 |
| License | Public data from IBGE; free use with citation |
| Citation | IBGE. Censo Demográfico 2022: Agregados por setores censitários. Rio de Janeiro: IBGE |
| How to download | `projects/01-hazard-exposure-montes-claros/scripts/01_download_data.py` |
| Local path | `data/raw/population/ibge_census_2022/` |
| Notes | EPSG:4674; 51,392 tracts in MG, 885 in Montes Claros. `v0001` = total residents (dictionary). Municipality total = 414,240 |

## kontur_population — Kontur Population, Brazil (H3 r8)

| Field | Content |
|---|---|
| Layer / project | Population on 400 m H3 hexagons · P01 comparison with Census |
| Provider and URL | Kontur via HDX, https://data.humdata.org/dataset/kontur-population-brazil |
| Version / file | `kontur_population_BR_20231101.gpkg.gz` (release 2023-11-01) |
| Access date | 2026-11-24 |
| License | CC BY 4.0 |
| Citation | Kontur (2023). Kontur Population: Global Population Density for 400m H3 Hexagons. Brazil subset, release 2023-11-01 |
| How to download | `01_download_data.py` |
| Local path | `data/raw/population/kontur/` |

## sgb_susceptibility_2014 — SGB/CPRM susceptibility chart (mass movement and inundation)

| Field | Content |
|---|---|
| Layer / project | Official susceptibility zones · P01 agreement check for HAND and slope |
| Provider and URL | SGB/CPRM, RIGEO https://rigeo.sgb.gov.br/handle/doc/14942 |
| Version / file | `sig_montesclaros_mg_suscetibilidade_2014.zip` (GIS vectors, 294 MB); `CS-MontesClaros.pdf` (map with legend). Layers used: `Suscetibilidade/Inundacao_A`, `Movimento_de_Massa_A` (extracted to `suscetibilidade_2014/`) |
| Access date | 2026-11-24 |
| License | Public SGB product; free use with citation |
| Citation | CPRM – Serviço Geológico do Brasil. Carta de suscetibilidade a movimentos gravitacionais de massa e inundação: município de Montes Claros – MG. Rio de Janeiro, 2014. 1 mapa, escala 1:220.000 |
| How to download | `01_download_data.py` |
| Local path | `data/raw/hazard/sgb_cprm/` |
| Notes | EPSG:31983. Built from a 2.5 m airborne radar DTM (BRADAR), modelling validated by field work 2012–2014. Inundation classes by height above drainage: Alta ≤ 1.5 m, Média 1.5–3 m, Baixa > 3 m (legend). Municipal sheet 1:220,000 for the whole municipality (zoning described as "basic level"; technical note refers to 1:25,000 mapping). Same principle as HAND → used as agreement check, not independent validation |

## sgb_risk_2012 — SGB/CPRM high and very high risk sectors, Montes Claros

| Field | Content |
|---|---|
| Layer / project | Field-mapped risk sectors · P01 qualitative check |
| Provider and URL | SGB/CPRM, RIGEO https://rigeo.sgb.gov.br/handle/doc/19146 |
| Version / file | `sig_montesclaros_mg_risco_2012.zip` (vectors); `produtos_montesclaros_mg_risco.zip` (report and sheets) |
| Access date | 2026-11-24 |
| License | Public SGB product; free use with citation |
| Citation | MOREIRA, G.; MORAES, J. Ação emergencial para delimitação de áreas em alto e muito alto risco a enchentes e movimentos de massa: município de Montes Claros, MG. Salvador: CPRM, 2012 |
| How to download | `01_download_data.py` |
| Notes | Only **4 sectors** (all "Alto"), 0.605 km²: 3 landslide, 1 flood (Vila Itatiaia – Santa Rafaela). Two shapefiles: original (no CRS) and `_atualizado` (EPSG:4326) with the same 4 sectors; the `_atualizado` file is used. Too few for a quantitative validation |

## dem_glo30 — Copernicus DEM GLO-30

| Field | Content |
|---|---|
| Layer / project | Main DEM · P01 slope and HAND |
| Provider and URL | ESA / Copernicus, AWS Open Data: https://copernicus-dem-30m.s3.amazonaws.com |
| Version / file | Tiles `Copernicus_DSM_COG_10_{S17,S18}_00_{W044,W045}_00_DEM.tif` |
| Access date | 2026-11-24 |
| License | Copernicus DEM licence (free use with attribution) |
| Citation | © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA; all rights reserved |
| How to download | `01_download_data.py` |
| Notes | EPSG:4326, 1 arc-second, float32, surface model (DSM). Tiles cover 45–43°W, 18–16°S |

## ibge_municipality — Municipal boundary, Montes Claros

| Field | Content |
|---|---|
| Layer / project | Administrative boundary · AOI (Phase 0), all projects |
| Provider and URL | IBGE, API de Malhas Territoriais v3: https://servicodados.ibge.gov.br/api/docs/malhas?versao=3 |
| Version / file | `municipio_3143302.geojson` (municipality code 3143302, quality "maxima"; current mesh served by the API) |
| Access date | 2026-11-23 (mesh year served by the API: to confirm in Project 1) |
| License | Public data from IBGE; free use with citation |
| Citation | IBGE — Instituto Brasileiro de Geografia e Estatística. Malha Municipal. Rio de Janeiro: IBGE |
| How to download | automatic: `geoportfolio.io.load_municipality()` (URL in `config/montes_claros.yaml`) |
| Local path | `data/raw/boundaries/ibge/municipio_3143302.geojson` |
| Notes | GeoJSON, SIRGAS 2000 geographic (EPSG:4674) |
