function report = rf2TgmGeneratorSmokeImpl(options)
%RF2TGMGENERATORSMOKE Headless smoke test for the TGM Generator app state.
arguments
    options.InputPath (1,1) string = ""
end

inputPath = options.InputPath;
if inputPath == ""
    inputPath = fullfile(rf2TgmProjectRoot(), "tyres", "cache", "tgm", "BFGoodrich_g-ForceR1_225-50-R16x7__c2bfff1f1528.tgm");
end

report = struct();
report.passed = false;
report.requiredFields = ["kind", "status", "odsPath", "chartReport", ...
    "materialLibrary", "behaviour", "validation", "formulaReport", ...
    "ttool", "inputModel", "projectPath", "tyres"];
report.missingFields = strings(0, 1);

state = rf2TgmGeneratorAppImpl(inputPath, "Headless", true);
for field = report.requiredFields
    if ~isfield(state, field)
        report.missingFields(end + 1, 1) = field; %#ok<AGROW>
    end
end

report.status = string(state.status);
report.kind = string(state.kind);
report.odsPath = string(state.odsPath);
report.chartCount = localGetNumber(state.chartReport, "chart_count");
report.chartSeriesCount = localGetNumber(state.chartReport, "series_count");
report.materialCount = localGetNumber(state.materialLibrary, "material_count");
report.materialPointCount = localGetNumber(state.materialLibrary, "point_count");
report.behaviourSamples = localGetNumber(state.behaviour, "sampleCount");
report.inputModelLoaded = localGetLogical(state.inputModel, "loaded");
report.inputCount = localGetNumber(state.inputModel, "input_count");
report.tyreCount = numel(state.tyres);
report.selectedTyreCount = nnz([state.tyres.selected]);
report.expectedInputSheets = ["General", "Geometry", "Construction", "Compound", ...
    "Realtime", "WLF", "ContactProps", "LoadSens", "Materials", "TBC"];
report.missingInputSheets = localMissingInputSheets(state.inputModel, report.expectedInputSheets);

model = rf2ReadTgmImpl(inputPath);
plotData = rf2TgmPlotDataImpl(model);
report.geometryRows = height(plotData.geometry);
report.rubberCrossSectionRows = height(plotData.rubberCrossSection);
report.plyRows = height(plotData.plyParams);
report.plyCrossSectionRows = height(plotData.plyCrossSection);
report.maxPlyLayers = localGetNumber(plotData.summary, "maxPlyLayers");
report.node0PlyLayers = nnz(plotData.plyParams.nodeIndex == 0);
report.plyNodeCount = localGetNumber(plotData.summary, "plyNodesWithLayers");
firstPly = plotData.plyCrossSection(1, :);
firstRubber = plotData.rubberCrossSection(plotData.rubberCrossSection.nodeIndex == firstPly.nodeIndex, :);
report.firstPlyOffsetM = firstPly.offsetM;
report.firstRubberDepthM = firstRubber.depthM(1);

report.passed = isempty(report.missingFields) ...
    && report.kind == "state" ...
    && report.status == "ready" ...
    && report.chartCount > 0 ...
    && report.chartSeriesCount > 0 ...
    && report.materialCount > 0 ...
    && report.materialPointCount > 0 ...
    && report.inputModelLoaded ...
    && report.inputCount >= 28254 ...
    && report.tyreCount >= 1 ...
    && report.selectedTyreCount == 1 ...
    && isempty(report.missingInputSheets) ...
    && report.geometryRows == 69 ...
    && report.rubberCrossSectionRows == report.geometryRows ...
    && report.plyRows == 277 ...
    && report.plyCrossSectionRows == 277 ...
    && report.maxPlyLayers == 6 ...
    && report.node0PlyLayers == 6 ...
    && report.firstPlyOffsetM > report.firstRubberDepthM;

if ~report.passed
    error("rf2TgmGeneratorSmokeImpl:Failed", "TGM Generator smoke failed: %s", jsonencode(report));
end
end

function missing = localMissingInputSheets(inputModel, expectedSheets)
missing = strings(0, 1);
if ~isstruct(inputModel) || ~isfield(inputModel, "sheet_counts")
    missing = expectedSheets(:);
    return;
end
counts = inputModel.sheet_counts;
for sheet = expectedSheets
    if ~isfield(counts, sheet)
        missing(end + 1, 1) = sheet; %#ok<AGROW>
    end
end
end

function value = localGetNumber(source, field)
if isstruct(source) && isfield(source, field)
    value = double(source.(field));
else
    value = NaN;
end
end

function value = localGetLogical(source, field)
if isstruct(source) && isfield(source, field)
    value = logical(source.(field));
else
    value = false;
end
end
