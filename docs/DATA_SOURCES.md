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
