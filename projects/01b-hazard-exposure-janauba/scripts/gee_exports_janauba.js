// Project 01 · Janaúba — exports do Google Earth Engine (2 arquivos, uma execução).
// Mesmo procedimento de Montes Claros (02_open_buildings_gee.js e 02b_fabdem_gee.js),
// com as áreas de Janaúba. Rodar no Code Editor: https://code.earthengine.google.com
// (cole o script, clique em Run e depois em RUN nas DUAS tarefas da aba "Tasks").
//
// Os arquivos vão para o Google Drive, pasta "geoportfolio". Baixe e salve em:
//   data/raw/buildings/open_buildings/open_buildings_v3_janauba.csv
//   data/raw/dem/fabdem/janauba/fabdem_v1-2_janauba.tif
//
// Áreas (geradas a partir de config/janauba.yaml):
// - Open Buildings: área urbana (setores urbanos do Censo 2022 no distrito-sede) + 500 m.
// - FABDEM: domínio hidrológico (área urbana + 25 km, em EPSG:31983) com ~2 km de margem.
// Decisões (ver docs/DECISIONS.md): confiança mínima 0.65 (menor limiar da sensibilidade);
// a propriedade "longitude_latitude" fica de fora porque quebra o export.
// FABDEM: licença não comercial (CC BY-NC-SA 4.0); o raster não é publicado.

// ---------------------------------------------------------------------------
// 1. Google Open Buildings v3 (polígonos)
// ---------------------------------------------------------------------------
var bboxBuildings = ee.Geometry.Rectangle([-43.3485, -15.8786, -43.2570, -15.7671]);

var buildings = ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons')
  .filterBounds(bboxBuildings)
  .filter(ee.Filter.gte('confidence', 0.65))
  .select(['area_in_meters', 'confidence', 'full_plus_code']);

print('Edificações (confiança >= 0.65):', buildings.size());
Map.centerObject(bboxBuildings, 13);
Map.addLayer(buildings, {color: '0072B2'}, 'Open Buildings v3');

Export.table.toDrive({
  collection: buildings,
  description: 'open_buildings_v3_janauba',
  folder: 'geoportfolio',
  fileNamePrefix: 'open_buildings_v3_janauba',
  fileFormat: 'CSV'   // a geometria vem na coluna ".geo" (GeoJSON)
});

// ---------------------------------------------------------------------------
// 2. FABDEM V1-2 (terreno nu), só para a sensibilidade ao MDE
// ---------------------------------------------------------------------------
var regionDem = ee.Geometry.Rectangle([-43.60, -16.12, -43.01, -15.53]);

var fabdem = ee.ImageCollection('projects/sat-io/open-datasets/FABDEM')
  .filterBounds(regionDem)
  .mosaic()
  .rename('elevation')
  .toFloat();

print('FABDEM, altitude (min/max) no recorte:',
      fabdem.reduceRegion({reducer: ee.Reducer.minMax(), geometry: regionDem, scale: 90, maxPixels: 1e9}));
Map.addLayer(fabdem.clip(regionDem), {min: 450, max: 1000}, 'FABDEM', false);

Export.image.toDrive({
  image: fabdem.clip(regionDem),
  description: 'fabdem_v1-2_janauba',
  folder: 'geoportfolio',
  fileNamePrefix: 'fabdem_v1-2_janauba',
  region: regionDem,
  crs: 'EPSG:4326',
  crsTransform: [1 / 3600, 0, -180, 0, -1 / 3600, 90],   // grade nativa (1 arco-segundo)
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});
