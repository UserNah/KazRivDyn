var grwlSim = ee.FeatureCollection("users/eeProject/GRWL_summaryStats");
// Goal: calculate river centerlines and widths for one Landsat SR image (LC08_L1TP_022034_20130422_20170310_01_T1)

// load in the functions
var fns = require('users/eeProject/RivWidthCloudPaper:rwc_landsat.js');
var fnsLandsat = require('users/eeProject/RivWidthCloudPaper:functions_Landsat578/functions_landsat.js');
// var map = ui.Map();
var mapLayers = Map.layers(); 
var grwlLayer = ui.Map.Layer(grwlSim, {color: 'yellow'}, 'grwlSimplified', true, 1);
Map.setOptions('satellite');
Map.style().set({cursor: 'crosshair'});
var instructionTitle = ui.Label('Проверка номер 1', {fontWeight: 'bold'});
var textStyle = {margin: '1px 15px'};
var L1 = ui.Label('Нажатие реки centerline (yellow) to calculate river width time series;', textStyle);
var L12 = ui.Label('(Optional): Adjust the period of interest before click on the map;', textStyle);
var L2 = ui.Label('Click on data point in the time series will show the corresponding satellite image;', textStyle);
var L3 = ui.Label('Right click on the animation to save as GIF.', textStyle);
var L4 = ui.Label('Depending on the number of cloud-free image available: result will appear after 1–3 min.', textStyle);
var citeTitle = ui.Label('CITE THE RIVWIDTHCLOUD ALGORITHM', {fontWeight: 'bold'});
var L5 = ui.Label('Yang, Xiao, George H. Allen, Tamlin M. Pavelsky, and Gennadii Donchyts. (2019). “RivWidthCloud: An Automated Google Earth Engine Algorithm for River Width Extraction from Remotely Sensed Imagery.” IEEE Geoscience and Remote Sensing Letters.', {margin: '1px 15px 10px 15px'}, 'https://ieeexplore.ieee.org');
var instructionPanel = ui.Panel([instructionTitle, L1, L12, L2, L3, L4], ui.Panel.Layout.flow('vertical'));
var citationPanel = ui.Panel([citeTitle, L5], ui.Panel.Layout.flow('vertical'));

var controlTitle = ui.Label('ADJUST DEFAULT PARAMETER', {fontWeight: 'bold'});
var startLabel = ui.Label('Start year:', textStyle);
var startYear = ui.Slider(1984, 2019, 1984, 1);
startYear.style().set({minWidth: '300px', margin: '1px 15px'});
var endLabel = ui.Label('End year:', textStyle);
var endYear = ui.Slider(1984, 2019, 2019, 1);
endYear.style().set({minWidth: '300px', margin: '1px 15px 10px 15px'});
// var COMPUTE = ui.Label('Click on river centerline to show widths');
// COMPUTE.style().set({fontWeight: 'bold'});
// COMPUTE.onClick(function())
var controlPanel = ui.Panel(
  [controlTitle, startLabel, startYear, endLabel, endYear], 
  ui.Panel.Layout.flow('vertical'),
  {border: '1px dashed black'});
var panel = ui.Panel(
  [instructionPanel, citationPanel, controlPanel], 
  ui.Panel.Layout.flow('vertical'), 
  {
    position: 'bottom-right', 
    width: '500px'
  });
var widgetList = panel.widgets();
ui.root.add(panel);

mapLayers.set(0, grwlLayer);

Map.onClick(function(coords) {
  
  widgetList.set(5, ui.Label(''));
  
  var thisPoint = ee.Geometry.Point([coords.lon, coords.lat]);
  
  var aoi = thisPoint.buffer(2000).bounds();

  var aoiLayer = ui.Map.Layer(ee.Geometry.LinearRing(ee.List(aoi.coordinates().get(0))), {color: 'red'}, 'AOI', true, 1);
  Map.centerObject(aoi);
  mapLayers.set(1, aoiLayer);
  
  var containFilter = ee.Filter.contains({
    leftField: 'geometry', 
    rightValue: aoi});
    
  var rw = fns.rwGenSR('Jones2019', 2000, 333, 500, aoi);
  var idList = ee.List(fnsLandsat.merge_collections_std_bandnames_collection1tier1_sr()
  .filterMetadata('CLOUD_COVER', 'less_than', 15)
  .filterDate(startYear.getValue() + '-01-01', endYear.getValue() + '-12-31')
  .filterBounds(thisPoint)
  .map(function(i) {
    return(i.set({geometry: i.select('BQA').geometry()}));
  })
  .filter(containFilter)
  .sort('system:time_start', true)
  .aggregate_array('LANDSAT_ID'));
  
  // if there are more than maxNPlot images to process, only process the first maxNPlot images
  var dataSize = ee.Number(idList.length());
  var maxNPlot = 200;
  idList = ee.List(ee.Algorithms.If(dataSize.gt(maxNPlot), idList.slice(0, maxNPlot), idList));
  var nPlottedString = ee.Algorithms.If(
    dataSize.gt(maxNPlot),
    ee.String('N_image = ').cat(dataSize.format('%d')).cat('.').cat(' (only process the first ' + maxNPlot + ')'), 
    ee.String('N_image = ').cat(dataSize.format('%d')).cat('.'));
  
  var CalcWidthFromId = function(thisImageId) {
  
    var output = rw(thisImageId);
    // print(output);
    
    output = output
    .filterMetadata('endsInWater', 'equals', 0)
    .filterMetadata('endsOverEdge', 'equals', 0)
    .filterMetadata('flag_cldShadow', 'equals', 0)
    .filterMetadata('flag_cloud', 'equals', 0)
    .filterMetadata('flag_hillshadow', 'equals', 0)
    .filterMetadata('flag_snowIce', 'equals', 0);
    
    // print(output.size());
    // print(output.aggregate_array('width'));
    
    var mergedReducers = ee.Reducer.mean()
    .combine(ee.Reducer.count(), null, true)
    .combine(ee.Reducer.stdDev(), null, true);
    
    var initStats = output.reduceColumns(mergedReducers, ['width']);
    
    var outputFil = output
    .filterBounds(thisPoint.buffer(ee.Number(initStats.get('mean')).divide(2))) // only includes points within zones buffered by mean width / 2
    // .filterBounds(thisPoint.buffer(150)) // only includes points within 150 meter radius
    .map(function(f) {return(f.set('distance', f.geometry().distance(thisPoint)))})
    .sort('distance', true)
    .limit(5);
      
    var finalWidths = outputFil.reduceColumns(mergedReducers, ['width']);
    var finalOrthogonalDirection = outputFil.reduceColumns(mergedReducers, ['orthogonalDirection']);
    var finalPt = outputFil.geometry().centroid();
    var crs = ee.Feature(outputFil.first()).get('crs');
    var outputFeature = ee.Feature(finalPt, {
      width_mean: finalWidths.get('mean'),
      width_std: finalWidths.get('stdDev'),
      finalOrthogonalDirection: finalOrthogonalDirection.get('mean'),
      LANDSAT_ID: thisImageId,
      crs: crs
    });
    
    // print(outputFeature);
    
    var thisImage = fnsLandsat.id2Img(thisImageId);
  
    
    var xy = outputFeature
    .geometry()
    .transform(outputFeature.get('crs'), 1)
    .coordinates();
    
    var x = ee.Number(xy.get(0));
    var y = ee.Number(xy.get(1));
    var w = ee.Number(outputFeature.get('width_mean')).divide(2);
    var orthAngle = ee.Number(outputFeature.get('finalOrthogonalDirection'));
    var dx = orthAngle.cos().multiply(w);
    var dy = orthAngle.sin().multiply(w);
    var line = ee.Geometry.LineString([x.add(dx), y.add(dy), x.subtract(dx), y.subtract(dy)], crs, false);//.transform('EPSG:4326', 1);
     
    // Map.centerObject(line);
    // Map.addLayer(line, {color: 'green'}, 'line');
    
    var i1 = thisImage.visualize({
      bands: ['Red', 'Green', 'Blue'], 
      min: 100, 
      max: 5000, 
      gamma: 1.2});
    var i2 = ee.FeatureCollection(ee.Feature(line, {})).draw({
      color: 'red', 
      strokeWidth: 3});
    var i3 = ee.FeatureCollection(outputFeature).draw({
      color: 'white',
      pointRadius: 3
    });
    
    var img = ee.ImageCollection([i1, i2, i3]).mosaic();
    
    // Map.addLayer(img);
    
    var outputImg = img
    .copyProperties(outputFeature)
    .copyProperties(thisImage, ['system:time_start']);//.aside(print);
    
    var outputFinal = ee.Algorithms.If(
      ee.Number(initStats.get('mean')), 
      ee.Algorithms.If(outputFil.size(), outputImg, null), 
      null);
    
    return(outputFinal);
  };
  
  // print(idList.length());
  
  var widths = ee.ImageCollection(idList.map(CalcWidthFromId))
  .filterMetadata('width_mean', 'not_equals', null)
  .sort('system:time_start', true);
  
  var chart = ui.Chart.feature.byFeature({
    features: widths, 
    xProperty: 'system:time_start', 
    yProperties: 'width_mean'});
  
  chart.setOptions({
    title: '', 
    hAxis: {title: 'Date'},
    vAxis: {title: 'Width (m)'},
    series: [
    {color: 'black', visibleInLegend: false, pointSize: 3, lineWidth: 0.5}
  ]
  });
  
  chart.onClick(function(x, y) {
    var clickedImage = ee.Image(widths
    .filterMetadata('system:time_start', 'equals', x)
    .filterMetadata('width_mean', 'equals', y)
    .first());
    // print(clickedImage);
    mapLayers.set(1, ui.Map.Layer(clickedImage, {}, 'clickedImage'));
    mapLayers.set(2, aoiLayer);
  });
  
  var anim = ui.Thumbnail({
    image: widths, 
    params: {
      region: aoi, 
      framesPerSecond: 3, 
      dimensions: '300x300'
    },
    style: {
      padding: '10px 100px 10px 100px',
      backgroundColor: 'black'
    }});
  
  var tsStatsLabel = ui.Label('', {color: 'red'});
  ee.String(nPlottedString).evaluate(function(tsStats) {
    tsStatsLabel.setValue(tsStats);
  });
  
  var animPanel = ui.Panel([ui.Label('WIDTH CHANGE THROUGH TIME (GIF)', {fontWeight: 'bold'}), anim], ui.Panel.Layout.flow('vertical'));
  var chartPanel = ui.Panel([ui.Label('WIDTH TIME SERIES', {fontWeight: 'bold'}), tsStatsLabel, chart], ui.Panel.Layout.flow('vertical'));
  
  widgetList
  .set(3, animPanel)
  .set(4, chartPanel);
  
  var urlCallback = function(url) {
    // print(url);
    var dataUrl = ui.Label('Download width data (CSV)', {}, url);
    widgetList.set(5, dataUrl);
  };
  
  ee.FeatureCollection(widths
  .map(function(f) {
    var fOut = ee.Feature(null, {
      date: ee.Date(f.get('system:time_start')),
      longitude: coords.lon, 
      latitude: coords.lat
    })
    .copyProperties(f, ['width_mean', 'LANDSAT_ID']);
    return(fOut)}))
  .getDownloadURL(
    {format: 'csv', 
    selectors: ['date', 'width_mean', 'LANDSAT_ID', 'longitude', 'latitude'], 
    filename: 'width_time_series.csv', 
    callback: urlCallback});
});


