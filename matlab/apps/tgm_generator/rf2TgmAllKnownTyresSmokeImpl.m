function report = rf2TgmAllKnownTyresSmokeImpl(options)
%RF2TGMALLKNOWNTYRESSMOKE Validate all locally known cached TGM tyres.
arguments
    options.TgmRoot (1,1) string = fullfile(rf2TgmProjectRoot(), "tools", "cache", "tyres", "tgm")
    options.ReportPath (1,1) string = fullfile(rf2TgmProjectRoot(), "tmp", "tgm_all_known_tyres_smoke_report.json")
    options.RoundtripDir (1,1) string = fullfile(rf2TgmProjectRoot(), "tmp", "tgm_all_known_tyres_roundtrip")
    options.WriteReport (1,1) logical = true
end

tgmRoot = options.TgmRoot;
files = dir(fullfile(tgmRoot, "*.tgm"));
files = files(~[files.isdir]);

report = struct();
report.generatedAt = string(datetime("now", "TimeZone", "UTC", "Format", "yyyy-MM-dd'T'HH:mm:ss'Z'"));
report.tgmRoot = tgmRoot;
report.count = numel(files);
report.passed = report.count > 0;
report.results = repmat(localEmptyResult(), 1, report.count);

if ~isfolder(options.RoundtripDir)
    mkdir(options.RoundtripDir);
end

for index = 1:numel(files)
    path = fullfile(files(index).folder, files(index).name);
    item = localCheckTyre(path, options.RoundtripDir);
    report.results(index) = item;
    report.passed = report.passed && item.passed;
end

if options.WriteReport
    localWriteJson(options.ReportPath, report);
end

if ~report.passed
    error("rf2TgmAllKnownTyresSmokeImpl:Failed", "Known tyre smoke failed: %s", jsonencode(report));
end
end

function item = localCheckTyre(path, roundtripDir)
item = localEmptyResult();
item.file = string(getfield(dir(path), "name")); %#ok<GFLD>
item.path = string(path);

try
    model = rf2ReadTgmImpl(path);
    plotData = rf2TgmPlotDataImpl(model);

    item.nodeCount = double(model.summary.nodeCount);
    item.qsaNumNodes = localScalarParameter(model, "QuasiStaticAnalysis", "NumNodes");
    item.materialRows = double(model.summary.materialRows);
    item.plyParamRows = double(model.summary.plyParamRows);
    item.geometryRows = double(height(plotData.geometry));
    item.materialPlotRows = double(height(plotData.materials));
    item.plyRows = double(height(plotData.plyParams));
    item.plyCrossSectionRows = double(height(plotData.plyCrossSection));
    item.maxPlyLayers = double(plotData.summary.maxPlyLayers);
    item.lookupV2LineCount = double(model.lookupV2LineCount);
    item.patchV1LineCount = double(model.patchV1LineCount);

    roundtripPath = fullfile(roundtripDir, item.file);
    rf2WriteTgmImpl(model, roundtripPath, "StripGeneratedLookups", false);
    item.roundtripEqual = localCanonicalText(path) == localCanonicalText(roundtripPath);

    item.checks = struct();
    item.checks.hasNodes = item.nodeCount > 0;
    item.checks.qsaNumNodesMatches = isnan(item.qsaNumNodes) || item.qsaNumNodes == item.nodeCount;
    item.checks.geometryMatchesNodes = item.geometryRows == item.nodeCount;
    item.checks.hasMaterials = item.materialPlotRows > 0 && item.materialRows == item.materialPlotRows;
    item.checks.hasPlyRows = item.plyRows > 0 && item.plyRows == item.plyParamRows;
    item.checks.plyCrossSectionComplete = item.plyCrossSectionRows == item.plyRows;
    item.checks.hasPlyLayers = item.maxPlyLayers > 0;
    item.checks.roundtripEqual = item.roundtripEqual;

    item.passed = all(structfun(@logical, item.checks));
    item.message = "ok";
catch exception
    item.message = string(exception.message);
    item.passed = false;
end
end

function item = localEmptyResult()
item = struct( ...
    "file", "", ...
    "path", "", ...
    "passed", false, ...
    "message", "", ...
    "nodeCount", NaN, ...
    "qsaNumNodes", NaN, ...
    "materialRows", NaN, ...
    "plyParamRows", NaN, ...
    "geometryRows", NaN, ...
    "materialPlotRows", NaN, ...
    "plyRows", NaN, ...
    "plyCrossSectionRows", NaN, ...
    "maxPlyLayers", NaN, ...
    "lookupV2LineCount", NaN, ...
    "patchV1LineCount", NaN, ...
    "roundtripEqual", false, ...
    "checks", struct());
end

function value = localScalarParameter(model, section, key)
rows = model.parameters.section == section & model.parameters.key == key;
value = NaN;
if ~any(rows)
    return;
end
raw = model.parameters.value{find(rows, 1, "first")};
if isnumeric(raw) && isscalar(raw)
    value = double(raw);
end
end

function text = localCanonicalText(path)
text = string(fileread(path));
text = replace(text, sprintf("\r\n"), sprintf("\n"));
text = replace(text, sprintf("\r"), sprintf("\n"));
text = regexprep(text, "[ \t]+\n", "\n");
text = strip(text, "right");
end

function localWriteJson(path, data)
outDir = fileparts(path);
if strlength(outDir) > 0 && ~isfolder(outDir)
    mkdir(outDir);
end
fid = fopen(path, "w");
cleanup = onCleanup(@() fclose(fid));
if fid < 0
    error("rf2TgmAllKnownTyresSmokeImpl:OpenFailed", "Could not open report: %s", path);
end
fwrite(fid, jsonencode(data), "char");
end
