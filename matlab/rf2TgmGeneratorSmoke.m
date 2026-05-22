function report = rf2TgmGeneratorSmoke(options)
%RF2TGMGENERATORSMOKE Headless smoke test for the TGM Generator app state.
arguments
    options.InputPath (1,1) string = ""
end

report = struct();
report.passed = false;
report.requiredFields = ["kind", "status", "odsPath", "chartReport", ...
    "materialLibrary", "behaviour", "validation", "formulaReport", ...
    "ttool", "inputModel", "projectPath"];
report.missingFields = strings(0, 1);

state = rf2TgmGeneratorApp(options.InputPath, "Headless", true);
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

report.passed = isempty(report.missingFields) ...
    && report.kind == "state" ...
    && report.status == "ready" ...
    && report.chartCount > 0 ...
    && report.chartSeriesCount > 0 ...
    && report.materialCount > 0 ...
    && report.materialPointCount > 0;

if ~report.passed
    error("rf2TgmGeneratorSmoke:Failed", "TGM Generator smoke failed: %s", jsonencode(report));
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
