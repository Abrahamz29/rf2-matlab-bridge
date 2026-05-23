function plotData = rf2TgmGeometryPlotDataImpl(model)
%RF2TGMGEOMETRYPLOTDATAIMPL Build plot-friendly arrays from a TGM model.
arguments
    model (1,1) struct
end

P = model.parameters;

geometryRows = P.section == "Node" & P.key == "Geometry";
geometry = localRowsToMatrix(P(geometryRows, :), 3);
plotData = struct();
plotData.geometry = table(P.nodeIndex(geometryRows), geometry(:, 1), geometry(:, 2), geometry(:, 3), ...
    'VariableNames', {'nodeIndex', 'x', 'y', 'z'});

treadRows = P.section == "Node" & P.key == "TreadDepth";
plotData.treadDepth = table(P.nodeIndex(treadRows), localRowsToColumn(P(treadRows, :)), ...
    'VariableNames', {'nodeIndex', 'treadDepthM'});
plotData.rubberCrossSection = localBuildRubberCrossSection(plotData.geometry, plotData.treadDepth);

plyRows = P.section == "Node" & P.key == "PlyParams";
ply = localRowsToMatrix(P(plyRows, :), 3);
plyNodeIndex = P.nodeIndex(plyRows);
plyIndex = localLayerIndexByNode(plyNodeIndex);
plotData.plyParams = table(plyNodeIndex, plyIndex, ply(:, 1), ply(:, 2), ply(:, 3), ...
    'VariableNames', {'nodeIndex', 'plyIndex', 'angleDeg', 'thicknessM', 'connectFlag'});
plotData.plyCrossSection = localBuildPlyCrossSection(plotData.geometry, plotData.plyParams, plotData.rubberCrossSection);

materialRows = P.section == "Node" & ismember(P.key, ["BulkMaterial", "TreadMaterial", "PlyMaterial"]);
material = localRowsToMatrix(P(materialRows, :), 7);
plotData.materials = table(P.nodeIndex(materialRows), P.key(materialRows), ...
    material(:, 1), material(:, 2), material(:, 3), material(:, 4), material(:, 5), material(:, 6), material(:, 7), ...
    'VariableNames', {'nodeIndex', 'kind', 'temperatureK', 'densityKgM3', 'youngsModulusPa', ...
    'poissonRatio', 'compressionMultiplier', 'specificHeatJKgK', 'conductivityWMK'});

plotData.summary = model.summary;
plotData.summary.maxPlyLayers = localMaxOrZero(plyIndex);
plotData.summary.plyNodesWithLayers = numel(unique(plyNodeIndex(~isnan(plyNodeIndex))));
plotData.summary.plyLayerDistribution = localLayerDistribution(plyNodeIndex);
plotData.summary.plyCrossSectionRows = height(plotData.plyCrossSection);
plotData.summary.rubberCrossSectionRows = height(plotData.rubberCrossSection);
end

function matrix = localRowsToMatrix(rows, width)
matrix = nan(height(rows), width);
for index = 1:height(rows)
    value = rows.value{index};
    if isnumeric(value)
        count = min(numel(value), width);
        matrix(index, 1:count) = value(1:count);
    end
end
end

function column = localRowsToColumn(rows)
column = nan(height(rows), 1);
for index = 1:height(rows)
    value = rows.value{index};
    if isnumeric(value) && isscalar(value)
        column(index) = value;
    end
end
end

function layerIndex = localLayerIndexByNode(nodeIndex)
layerIndex = zeros(numel(nodeIndex), 1);
nodes = unique(nodeIndex(~isnan(nodeIndex)));
for node = reshape(nodes, 1, [])
    rows = find(nodeIndex == node);
    layerIndex(rows) = (1:numel(rows)).';
end
end

function value = localMaxOrZero(values)
if isempty(values)
    value = 0;
else
    value = max(values);
end
end

function distribution = localLayerDistribution(nodeIndex)
distribution = struct();
nodes = unique(nodeIndex(~isnan(nodeIndex)));
for node = reshape(nodes, 1, [])
    count = nnz(nodeIndex == node);
    field = "layers" + string(count);
    if ~isfield(distribution, field)
        distribution.(field) = 0;
    end
    distribution.(field) = distribution.(field) + 1;
end
end

function rubberTable = localBuildRubberCrossSection(geometry, treadDepth)
if isempty(geometry)
    rubberTable = table([], [], [], [], [], [], ...
        'VariableNames', {'nodeIndex', 'surfaceX', 'surfaceY', 'innerX', 'innerY', 'depthM'});
    return;
end

geometry = sortrows(geometry, "nodeIndex");
points = [geometry.x, geometry.y];
center = mean(points, 1, "omitnan");
normal = localInwardNormals(points, center);
depth = localDepthByNode(geometry.nodeIndex, treadDepth);
inner = points + normal .* [depth, depth];

rubberTable = table(geometry.nodeIndex, points(:, 1), points(:, 2), inner(:, 1), inner(:, 2), depth, ...
    'VariableNames', {'nodeIndex', 'surfaceX', 'surfaceY', 'innerX', 'innerY', 'depthM'});
end

function depth = localDepthByNode(nodeIndex, treadDepth)
depth = zeros(numel(nodeIndex), 1);
if isempty(treadDepth)
    return;
end

[matched, location] = ismember(nodeIndex, treadDepth.nodeIndex);
depth(matched) = treadDepth.treadDepthM(location(matched));
depth(isnan(depth) | depth < 0) = 0;
end

function layerTable = localBuildPlyCrossSection(geometry, plyParams, rubberCrossSection)
if isempty(geometry) || isempty(plyParams)
    layerTable = table([], [], [], [], [], [], [], [], [], [], [], [], ...
        'VariableNames', {'nodeIndex', 'plyIndex', 'segmentIndex', 'x', 'y', ...
        'innerX', 'innerY', 'outerX', 'outerY', 'angleDeg', 'thicknessM', 'offsetM'});
    return;
end

geometry = sortrows(geometry, "nodeIndex");
plyParams = sortrows(plyParams, ["nodeIndex", "plyIndex"]);
points = [geometry.x, geometry.y];
center = mean(points, 1, "omitnan");
normal = localInwardNormals(points, center);
baseOffset = localRubberDepthByNode(geometry.nodeIndex, rubberCrossSection);

rows = {};
for nodeRow = 1:height(geometry)
    node = geometry.nodeIndex(nodeRow);
    layerRows = find(plyParams.nodeIndex == node);
    cumulativeThickness = baseOffset(nodeRow);
    for rowIndex = reshape(layerRows, 1, [])
        thickness = plyParams.thicknessM(rowIndex);
        if isnan(thickness)
            thickness = 0;
        end
        innerOffset = cumulativeThickness;
        outerOffset = cumulativeThickness + thickness;
        offset = innerOffset + 0.5 * thickness;
        xy = points(nodeRow, :) + normal(nodeRow, :) * offset;
        innerXy = points(nodeRow, :) + normal(nodeRow, :) * innerOffset;
        outerXy = points(nodeRow, :) + normal(nodeRow, :) * outerOffset;
        rows(end + 1, :) = {node, plyParams.plyIndex(rowIndex), NaN, xy(1), xy(2), ...
            innerXy(1), innerXy(2), outerXy(1), outerXy(2), ...
            plyParams.angleDeg(rowIndex), thickness, offset}; %#ok<AGROW>
        cumulativeThickness = outerOffset;
    end
end

if isempty(rows)
    layerTable = table([], [], [], [], [], [], [], [], [], [], [], [], ...
        'VariableNames', {'nodeIndex', 'plyIndex', 'segmentIndex', 'x', 'y', ...
        'innerX', 'innerY', 'outerX', 'outerY', 'angleDeg', 'thicknessM', 'offsetM'});
else
    layerTable = cell2table(rows, ...
        'VariableNames', {'nodeIndex', 'plyIndex', 'segmentIndex', 'x', 'y', ...
        'innerX', 'innerY', 'outerX', 'outerY', 'angleDeg', 'thicknessM', 'offsetM'});
    layerTable.segmentIndex = localLayerSegmentIndex(layerTable.nodeIndex, layerTable.plyIndex);
end
end

function depth = localRubberDepthByNode(nodeIndex, rubberCrossSection)
depth = zeros(numel(nodeIndex), 1);
if isempty(rubberCrossSection)
    return;
end

[matched, location] = ismember(nodeIndex, rubberCrossSection.nodeIndex);
depth(matched) = rubberCrossSection.depthM(location(matched));
depth(isnan(depth) | depth < 0) = 0;
end

function segmentIndex = localLayerSegmentIndex(nodeIndex, plyIndex)
segmentIndex = nan(numel(nodeIndex), 1);
layers = unique(plyIndex(~isnan(plyIndex)));
for layer = reshape(layers, 1, [])
    rows = find(plyIndex == layer);
    [~, order] = sort(nodeIndex(rows));
    layerRows = rows(order);
    segment = 1;
    previousNode = NaN;
    for row = reshape(layerRows, 1, [])
        node = nodeIndex(row);
        if ~isnan(previousNode) && node > previousNode + 1
            segment = segment + 1;
        end
        segmentIndex(row) = segment;
        previousNode = node;
    end
end
end

function normal = localInwardNormals(points, center)
normal = nan(size(points));
count = size(points, 1);
for index = 1:count
    prevIndex = max(index - 1, 1);
    nextIndex = min(index + 1, count);
    tangent = points(nextIndex, :) - points(prevIndex, :);
    if norm(tangent) == 0
        tangent = [1, 0];
    end
    candidate = [tangent(2), -tangent(1)];
    candidate = candidate ./ max(norm(candidate), eps);
    toCenter = center - points(index, :);
    if dot(candidate, toCenter) < 0
        candidate = -candidate;
    end
    normal(index, :) = candidate;
end
end
