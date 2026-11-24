// P01 — passo 2: exporta as edificações do Google Open Buildings v3 (polígonos)
// para a área urbana de Montes Claros. Rodar no Code Editor do Google Earth Engine:
// https://code.earthengine.google.com  (cole o script e clique em Run; depois
// clique em RUN na aba "Tasks").
//
// O arquivo vai para o seu Google Drive, pasta "geoportfolio". Baixe e salve em:
//   data/raw/buildings/open_buildings/open_buildings_v3_montes_claros.csv
//
// Decisões (ver docs/DECISIONS.md):
// - Área: retângulo que envolve o perímetro urbano (Regiões de Planejamento)
//   com 500 m de margem. O recorte exato pelo perímetro é feito depois, em Python.
// - Confiança mínima 0.65: o menor limiar da análise de sensibilidade
//   (0.65 / 0.70 / 0.75). O filtro principal (0.75) é aplicado em Python.
// - A propriedade "longitude_latitude" é removida: ela é uma segunda geometria
//   e faz o export falhar.

// Retângulo [oeste, sul, leste, norte] em graus (EPSG:4326), gerado a partir de
// config/montes_claros.yaml + Regiões de Planejamento, com buffer de 500 m.
var bbox = ee.Geometry.Rectangle([-43.9245, -16.8032, -43.7830, -16.6305]);

var buildings = ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons')
  .filterBounds(bbox)
  .filter(ee.Filter.gte('confidence', 0.65))
  // mantém só estes atributos (a geometria do polígono é mantida automaticamente)
  .select(['area_in_meters', 'confidence', 'full_plus_code']);

// Conferência rápida no Console antes de exportar
print('Edificações (confiança >= 0.65):', buildings.size());
Map.centerObject(bbox, 13);
Map.addLayer(bbox, {color: 'red'}, 'bbox', false);
Map.addLayer(buildings, {color: '0072B2'}, 'Open Buildings v3');

Export.table.toDrive({
  collection: buildings,
  description: 'open_buildings_v3_montes_claros',
  folder: 'geoportfolio',
  fileNamePrefix: 'open_buildings_v3_montes_claros',
  fileFormat: 'CSV'   // a geometria vem na coluna ".geo" (GeoJSON)
});
