// P01 — passo 2b: exporta o FABDEM V1-2 (MDE de terreno nu, 1 arco-segundo ≈ 30 m)
// para o domínio hidrológico de Montes Claros. Usado SÓ na sensibilidade ao MDE
// (scripts/12_dem_sensitivity.py). Rodar no Code Editor do Google Earth Engine:
// https://code.earthengine.google.com  (cole o script, clique em Run e depois em
// RUN na aba "Tasks").
//
// O arquivo vai para o seu Google Drive, pasta "geoportfolio". Baixe e salve em:
//   data/raw/dem/fabdem/fabdem_v1-2_montes_claros.tif
//
// Fonte: Hawker et al. (2022), FABDEM V1-2, Universidade de Bristol, publicado
// no catálogo comunitário do GEE (projects/sat-io/open-datasets/FABDEM).
// Licença NÃO comercial (CC BY-NC-SA 4.0): o raster e camadas derivadas dele
// não são publicados no repositório; só tabelas agregadas (ver DATA_SOURCES.md).
//
// Área: retângulo que envolve o domínio do GLO-30 (perímetro urbano + 25 km,
// em EPSG:31983), com ~1,5 km de margem. Gerado a partir de
// data/interim/p01/dem_glo30_31983_30m.tif.

var region = ee.Geometry.Rectangle([-44.17, -17.04, -43.53, -16.39]);

var fabdem = ee.ImageCollection('projects/sat-io/open-datasets/FABDEM')
  .filterBounds(region)
  .mosaic()
  .rename('elevation')
  .toFloat();

// Conferência rápida no Console antes de exportar
print('Altitude (min/max) no recorte:',
      fabdem.reduceRegion({reducer: ee.Reducer.minMax(), geometry: region, scale: 90, maxPixels: 1e9}));
Map.centerObject(region, 10);
Map.addLayer(fabdem.clip(region), {min: 500, max: 1100}, 'FABDEM');
Map.addLayer(region, {color: 'red'}, 'export region', false);

Export.image.toDrive({
  image: fabdem.clip(region),
  description: 'fabdem_v1-2_montes_claros',
  folder: 'geoportfolio',
  fileNamePrefix: 'fabdem_v1-2_montes_claros',
  region: region,
  // grade nativa do FABDEM: 1 arco-segundo em WGS 84 (sem reamostrar aqui;
  // a reprojeção para EPSG:31983 a 30 m é feita em Python, igual ao GLO-30)
  crs: 'EPSG:4326',
  crsTransform: [1 / 3600, 0, -180, 0, -1 / 3600, 90],
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});
