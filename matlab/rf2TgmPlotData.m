function plotData = rf2TgmPlotData(model)
%RF2TGMPLOTDATA Build plot-friendly arrays from an rf2ReadTgm model.
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

plyRows = P.section == "Node" & P.key == "PlyParams";
ply = localRowsToMatrix(P(plyRows, :), 3);
plyNodeIndex = P.nodeIndex(plyRows);
plyIndex = localLayerIndexByNode(plyNodeIndex);
plotData.plyParams = table(plyNodeIndex, plyIndex, ply(:, 1), ply(:, 2), ply(:, 3), ...
    'VariableNames', {'nodeIndex', 'plyIndex', 'angleDeg', 'thicknessM', 'connectFlag'});

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
