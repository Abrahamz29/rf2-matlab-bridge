function report = rf2TgmGeneratorSmoke(options)
%RF2TGMGENERATORSMOKE Headless smoke test for the TGM Generator app state.
arguments
    options.InputPath (1,1) string = ""
end

inputPath = options.InputPath;
if inputPath == ""
    inputPath = fullfile("tools", "cache", "tyres", "tgm", "BFGoodrich_g-ForceR1_225-50-R16x7__c2bfff1f1528.tgm");
end

report = struct();
report.passed = false;
report.requiredFields = ["kind", "status", "odsPath", "chartReport", ...
    "materialLibrary", "behaviour", "validation", "formulaReport", ...
    "ttool", "inputModel", "projectPath"];
report.missingFields = strings(0, 1);

state = rf2TgmGeneratorApp(inputPath, "Headless", true);
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
report.expectedInputSheets = ["General", "Geometry", "Construction", "Compound", ...
    "Realtime", "WLF", "ContactProps", "LoadSens", "Materials", "TBC"];
report.missingInputSheets = localMissingInputSheets(state.inputModel, report.expectedInputSheets);

model = rf2ReadTgm(inputPath);
plotData = rf2TgmPlotData(model);
report.geometryRows = height(plotData.geometry);
report.plyRows = height(plotData.plyParams);
report.maxPlyLayers = localGetNumber(plotData.summary, "maxPlyLayers");
report.node0PlyLayers = nnz(plotData.plyParams.nodeIndex == 0);
report.plyNodeCount = localGetNumber(plotData.summary, "plyNodesWithLayers");

report.passed = isempty(report.missingFields) ...
    && report.kind == "state" ...
    && report.status == "ready" ...
    && report.chartCount > 0 ...
    && report.chartSeriesCount > 0 ...
    && report.materialCount > 0 ...
    && report.materialPointCount > 0 ...
    && report.inputModelLoaded ...
    && report.inputCount >= 28254 ...
    && isempty(report.missingInputSheets) ...
    && report.geometryRows == 69 ...
    && report.plyRows == 277 ...
    && report.maxPlyLayers == 6 ...
    && report.node0PlyLayers == 6;

if ~report.passed
    error("rf2TgmGeneratorSmoke:Failed", "TGM Generator smoke failed: %s", jsonencode(report));
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
