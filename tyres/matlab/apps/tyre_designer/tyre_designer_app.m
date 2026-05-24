function app = tyre_designer_app(inputPath, options)
%TYRE_DESIGNER_APP Open the lightweight tyre designer UI.
arguments
    inputPath (1,1) string = ""
    options.Headless (1,1) logical = false
    options.StartView (1,1) string = "model"
end

state = localBuildState(inputPath, options.StartView);
if options.Headless
    app = state;
    return;
end

fig = uifigure("Name", "tyre_designer", "Position", [120 90 1280 760]);
layout = uigridlayout(fig, [1 1], ...
    "Padding", [0 0 0 0], ...
    "RowHeight", {'1x'}, ...
    "ColumnWidth", {'1x'});
html = uihtml(layout, ...
    "HTMLSource", fullfile(fileparts(mfilename("fullpath")), "assets", "tyre_designer.html"));
fig.WindowState = "maximized";
html.Data = state;
html.DataChangedFcn = @(src, event) localHandleCommand(src, event); %#ok<INUSD>

app = struct("Figure", fig, "Layout", layout, "Html", html, "State", state);
end

function state = localBuildState(inputPath, startView)
arguments
    inputPath (1,1) string
    startView (1,1) string = "model"
end
requestedPath = inputPath;
inputPath = localResolveLoadPath(inputPath);

state = struct();
state.kind = "geometryState";
state.status = "ready";
state.startView = localNormalizeStartView(startView);
state.inputPath = inputPath;
state.loaded = false;
state.message = "No TGM loaded.";
state.summary = struct();
state.plotData = struct();
state.database = localDatabaseInfo();
state.tyres = localListKnownTyres(inputPath);
state.materialDatabase = localMaterialDatabaseInfo();
state.materialLibrary = localLoadMaterialLibraryDatabase(state.materialDatabase.path);

if inputPath ~= "" && isfile(inputPath)
    model = tyre_designer_read_tgm(inputPath);
    plotData = tyre_designer_plot_data(model);
    state.loaded = true;
    state.status = "loaded";
    state.message = "Loaded " + string(model.fileName);
    state.summary = model.summary;
    state.inputPath = string(model.path);
    state.plotData = localEncodePlotData(plotData);
elseif requestedPath ~= ""
    state.status = "not found";
    state.inputPath = requestedPath;
    state.message = "TGM not found: " + requestedPath;
end
end

function localHandleCommand(html, ~)
data = html.Data;
if ~isstruct(data) || ~isfield(data, "command")
    return;
end

try
    switch string(data.command)
        case "ping"
            html.Data = struct("kind", "pong", "message", "MATLAB backend ready");
        case "loadTgm"
            startView = "model";
            if isfield(data, "startView")
                startView = string(data.startView);
            end
            html.Data = localBuildState(string(data.path), startView);
        otherwise
            html.Data = struct("kind", "error", "message", "Unknown command: " + string(data.command));
    end
catch exception
    html.Data = struct("kind", "error", "message", string(exception.message));
end
end

function view = localNormalizeStartView(view)
view = lower(strtrim(string(view)));
view = replace(view, "_", "-");
view = replace(view, " ", "-");
switch view
    case {"node", "nodes", "node-explorer", "nodeexplorer"}
        view = "node-explorer";
    case {"material", "materials"}
        view = "materials";
    otherwise
        view = "model";
end
end

function info = localDatabaseInfo()
dbPath = fullfile(tyre_designer_project_root(), "tyres", "database", "rf2_tyre_database.sqlite");
info = struct();
info.path = string(dbPath);
info.available = isfile(dbPath) && exist("sqlite", "file") == 6;
info.message = "Tyre database ready.";
if ~info.available
    info.message = "Tyre database unavailable; using cache folder fallback.";
end
end

function info = localMaterialDatabaseInfo()
dbPath = fullfile(tyre_designer_project_root(), "tyres", "database", "rf2_material_database.sqlite");
info = struct();
info.path = string(dbPath);
info.available = isfile(dbPath) && exist("sqlite", "file") == 6;
info.message = "Material database ready.";
if ~info.available
    info.message = "Material database unavailable.";
end
end

function library = localLoadMaterialLibraryDatabase(dbPath)
library = localEmptyMaterialLibrary(dbPath);
if ~isfile(dbPath) || exist("sqlite", "file") ~= 6
    return;
end

try
    conn = sqlite(dbPath, "readonly");
    cleanup = onCleanup(@() close(conn)); %#ok<NASGU>
    categoryRows = fetch(conn, "select id, name, material_count, point_count from categories order by id");
    materialRows = fetch(conn, [
        "select id, category_id, category, name, coalesce(title, '') as title, " + ...
        "coalesce(name_cell, '') as name_cell, coalesce(start_col, -1.0e308) as start_col, " + ...
        "coalesce(end_col, -1.0e308) as end_col, coalesce(point_count, 0) as point_count, " + ...
        "coalesce(temperature_min_k, -1.0e308) as temperature_min_k, " + ...
        "coalesce(temperature_max_k, -1.0e308) as temperature_max_k, " + ...
        "coalesce(youngs_modulus_min_pa, -1.0e308) as youngs_modulus_min_pa, " + ...
        "coalesce(youngs_modulus_max_pa, -1.0e308) as youngs_modulus_max_pa " + ...
        "from materials order by category, name, id"]);
    pointRows = fetch(conn, [
        "select id, material_id, category, material, " + ...
        "coalesce(sample_index, -1.0e308) as sample_index, " + ...
        "coalesce(col_index, -1.0e308) as col_index, coalesce(address, '') as address, " + ...
        "coalesce(temperature_k, -1.0e308) as temperature_k, " + ...
        "coalesce(density_kg_m3, -1.0e308) as density_kg_m3, " + ...
        "coalesce(youngs_modulus_pa, -1.0e308) as youngs_modulus_pa, " + ...
        "coalesce(poissons_ratio, -1.0e308) as poissons_ratio, " + ...
        "coalesce(compression_tension_ratio, -1.0e308) as compression_tension_ratio, " + ...
        "coalesce(specific_heat, -1.0e308) as specific_heat, " + ...
        "coalesce(thermal_conductivity, -1.0e308) as thermal_conductivity, " + ...
        "coalesce(longitudinal_conductivity, -1.0e308) as longitudinal_conductivity, " + ...
        "coalesce(shore_a, -1.0e308) as shore_a " + ...
        "from material_points order by material_id, sample_index"]);

    library.available = true;
    library.message = "Material database ready.";
    library.categoryCount = height(categoryRows);
    library.materialCount = height(materialRows);
    library.pointCount = height(pointRows);
    library.categories = localMaterialCategoryRecords(categoryRows);
    library.materials = localMaterialRecords(materialRows, pointRows);
catch exception
    library.available = false;
    library.message = "Material database load failed: " + string(exception.message);
end
end

function library = localEmptyMaterialLibrary(dbPath)
library = struct();
library.available = false;
library.path = string(dbPath);
library.message = "Material database unavailable.";
library.categoryCount = 0;
library.materialCount = 0;
library.pointCount = 0;
library.categories = localEmptyMaterialCategories();
library.materials = localEmptyMaterials();
end

function categories = localMaterialCategoryRecords(rows)
categories = localEmptyMaterialCategories();
for index = 1:height(rows)
    item = struct();
    item.id = double(rows.id(index));
    item.name = string(rows.name(index));
    item.materialCount = double(rows.material_count(index));
    item.pointCount = double(rows.point_count(index));
    categories(end + 1, 1) = item; %#ok<AGROW>
end
end

function categories = localEmptyMaterialCategories()
categories = repmat(struct( ...
    "id", NaN, ...
    "name", "", ...
    "materialCount", 0, ...
    "pointCount", 0), 0, 1);
end

function materials = localMaterialRecords(materialRows, pointRows)
materials = localEmptyMaterials();
points = localMaterialPointRecords(pointRows);
pointMaterialIds = arrayfun(@(point) point.materialId, points);
for index = 1:height(materialRows)
    materialId = double(materialRows.id(index));
    materialPoints = points(pointMaterialIds == materialId);
    item = struct();
    item.id = materialId;
    item.categoryId = double(materialRows.category_id(index));
    item.category = string(materialRows.category(index));
    item.name = string(materialRows.name(index));
    item.title = string(materialRows.title(index));
    item.nameCell = string(materialRows.name_cell(index));
    item.startCol = localDbNumber(materialRows.start_col(index));
    item.endCol = localDbNumber(materialRows.end_col(index));
    item.pointCount = localDbNumber(materialRows.point_count(index));
    item.temperatureMinK = localDbNumber(materialRows.temperature_min_k(index));
    item.temperatureMaxK = localDbNumber(materialRows.temperature_max_k(index));
    item.youngsModulusMinPa = localDbNumber(materialRows.youngs_modulus_min_pa(index));
    item.youngsModulusMaxPa = localDbNumber(materialRows.youngs_modulus_max_pa(index));
    item.points = materialPoints;
    materials(end + 1, 1) = item; %#ok<AGROW>
end
end

function materials = localEmptyMaterials()
materials = repmat(struct( ...
    "id", NaN, ...
    "categoryId", NaN, ...
    "category", "", ...
    "name", "", ...
    "title", "", ...
    "nameCell", "", ...
    "startCol", NaN, ...
    "endCol", NaN, ...
    "pointCount", 0, ...
    "temperatureMinK", NaN, ...
    "temperatureMaxK", NaN, ...
    "youngsModulusMinPa", NaN, ...
    "youngsModulusMaxPa", NaN, ...
    "points", localEmptyMaterialPoints()), 0, 1);
end

function points = localMaterialPointRecords(rows)
points = localEmptyMaterialPoints();
for index = 1:height(rows)
    item = struct();
    item.id = double(rows.id(index));
    item.materialId = double(rows.material_id(index));
    item.category = string(rows.category(index));
    item.material = string(rows.material(index));
    item.sampleIndex = localDbNumber(rows.sample_index(index));
    item.colIndex = localDbNumber(rows.col_index(index));
    item.address = string(rows.address(index));
    item.temperatureK = localDbNumber(rows.temperature_k(index));
    item.densityKgM3 = localDbNumber(rows.density_kg_m3(index));
    item.youngsModulusPa = localDbNumber(rows.youngs_modulus_pa(index));
    item.poissonsRatio = localDbNumber(rows.poissons_ratio(index));
    item.compressionTensionRatio = localDbNumber(rows.compression_tension_ratio(index));
    item.specificHeat = localDbNumber(rows.specific_heat(index));
    item.thermalConductivity = localDbNumber(rows.thermal_conductivity(index));
    item.longitudinalConductivity = localDbNumber(rows.longitudinal_conductivity(index));
    item.shoreA = localDbNumber(rows.shore_a(index));
    points(end + 1, 1) = item; %#ok<AGROW>
end
end

function points = localEmptyMaterialPoints()
points = repmat(struct( ...
    "id", NaN, ...
    "materialId", NaN, ...
    "category", "", ...
    "material", "", ...
    "sampleIndex", NaN, ...
    "colIndex", NaN, ...
    "address", "", ...
    "temperatureK", NaN, ...
    "densityKgM3", NaN, ...
    "youngsModulusPa", NaN, ...
    "poissonsRatio", NaN, ...
    "compressionTensionRatio", NaN, ...
    "specificHeat", NaN, ...
    "thermalConductivity", NaN, ...
    "longitudinalConductivity", NaN, ...
    "shoreA", NaN), 0, 1);
end

function number = localDbNumber(value)
number = double(value);
if ~isfinite(number) || number <= -1.0e307
    number = NaN;
end
end

function tyres = localListKnownTyres(inputPath)
dbPath = fullfile(tyre_designer_project_root(), "tyres", "database", "rf2_tyre_database.sqlite");
selectedPath = localNormalizePath(inputPath);
try
    tyres = localListDatabaseTyres(dbPath, selectedPath);
    if ~isempty(tyres)
        return;
    end
catch
end

tyres = localListCachedTyres(selectedPath);
end

function tyres = localListDatabaseTyres(dbPath, selectedPath)
tyres = localEmptyTyres();
if ~isfile(dbPath) || exist("sqlite", "file") ~= 6
    return;
end

conn = sqlite(dbPath, "readonly");
cleanup = onCleanup(@() close(conn)); %#ok<NASGU>
rows = fetch(conn, "select id, display_name, file_name, local_copy_path, sha256, length_bytes, source_count from tyres order by display_name");

for index = 1:height(rows)
    localCopyPath = localResolveProjectPath(string(rows.local_copy_path(index)));
    resolvedPath = localBestExistingTyrePath(conn, double(rows.id(index)), localCopyPath, string(rows.file_name(index)));
    item = struct();
    item.displayName = string(rows.display_name(index));
    item.fileName = string(rows.file_name(index));
    item.path = resolvedPath;
    item.selected = selectedPath ~= "" && localNormalizePath(resolvedPath) == selectedPath;
    item.sha256 = string(rows.sha256(index));
    item.lengthBytes = double(rows.length_bytes(index));
    item.sourceCount = double(rows.source_count(index));
    item.source = "database";
    tyres(end + 1, 1) = item; %#ok<AGROW>
end
end

function resolvedPath = localResolveLoadPath(inputPath)
resolvedPath = string(inputPath);
if resolvedPath == ""
    return;
end

resolvedPath = localResolveProjectPath(resolvedPath);
if isfile(resolvedPath)
    return;
end

dbPath = fullfile(tyre_designer_project_root(), "tyres", "database", "rf2_tyre_database.sqlite");
try
    resolvedPath = localResolveDatabasePath(dbPath, resolvedPath);
catch
end
end

function resolvedPath = localResolveDatabasePath(dbPath, requestedPath)
resolvedPath = string(requestedPath);
if ~isfile(dbPath) || exist("sqlite", "file") ~= 6
    return;
end

conn = sqlite(dbPath, "readonly");
cleanup = onCleanup(@() close(conn)); %#ok<NASGU>
rows = fetch(conn, "select id, display_name, file_name, local_copy_path from tyres order by display_name");
requestedPath = localResolveProjectPath(requestedPath);
requestedNormalized = localNormalizePath(requestedPath);
requestedLeaf = localPathLeaf(requestedPath);
requestedFileName = localTyreFileNameKey(requestedLeaf);
requestedStem = localTyreStemKey(requestedLeaf);
requestedText = lower(strtrim(string(requestedLeaf)));

for index = 1:height(rows)
    localCopyPath = localResolveProjectPath(string(rows.local_copy_path(index)));
    fileName = string(rows.file_name(index));
    [~, fileStem, fileExt] = fileparts(char(fileName));
    fileNameLower = lower(string(fileStem) + string(fileExt));
    fileStemLower = lower(string(fileStem));
    displayLower = lower(strtrim(string(rows.display_name(index))));
    tyreId = double(rows.id(index));

    if localNormalizePath(localCopyPath) == requestedNormalized ...
            || fileNameLower == requestedFileName ...
            || fileStemLower == requestedStem ...
            || displayLower == requestedText ...
            || displayLower == requestedStem ...
            || lower(displayLower + ".tgm") == requestedFileName
        resolvedPath = localBestExistingTyrePath(conn, tyreId, localCopyPath, fileName);
        return;
    end
end
end

function leaf = localPathLeaf(path)
text = replace(string(path), "/", "\");
parts = split(text, "\");
leaf = parts(end);
end

function key = localTyreFileNameKey(name)
key = lower(strtrim(string(name)));
if key ~= "" && ~endsWith(key, ".tgm")
    key = key + ".tgm";
end
end

function key = localTyreStemKey(name)
key = lower(strtrim(string(name)));
if endsWith(key, ".tgm")
    key = extractBefore(key, strlength(key) - 3);
end
end

function resolvedPath = localBestExistingTyrePath(conn, tyreId, localCopyPath, fileName)
candidates = strings(0, 1);
candidates(end + 1, 1) = string(localCopyPath);

sourceRows = fetch(conn, "select source_path from tyre_sources where tyre_id = " + string(tyreId));
for index = 1:height(sourceRows)
    candidates(end + 1, 1) = string(sourceRows.source_path(index)); %#ok<AGROW>
end

if fileName ~= ""
    candidates(end + 1, 1) = string(fullfile(tyre_designer_project_root(), "tyres", "input", "tgm", fileName));
    candidates(end + 1, 1) = string(fullfile(tyre_designer_project_root(), "input", fileName));
end

resolvedPath = localFirstExistingPath(candidates);
if resolvedPath == ""
    resolvedPath = string(localCopyPath);
end
end

function resolvedPath = localFirstExistingPath(candidates)
existing = strings(0, 1);
ranks = zeros(0, 1);

for index = 1:numel(candidates)
    candidate = localResolveProjectPath(candidates(index));
    if isfile(candidate)
        existing(end + 1, 1) = candidate; %#ok<AGROW>
        ranks(end + 1, 1) = localPathPreference(candidate); %#ok<AGROW>
    end
end

if isempty(existing)
    resolvedPath = "";
    return;
end

[~, order] = sort(ranks);
resolvedPath = existing(order(1));
end

function rank = localPathPreference(path)
pathText = lower(replace(string(path), "/", "\"));
if contains(pathText, "\tyres\cache\tgm\")
    rank = 0;
elseif contains(pathText, "\ptool\")
    rank = 1;
elseif contains(pathText, "\tyres\input\tgm\")
    rank = 2;
elseif contains(pathText, "\moddev\")
    rank = 3;
else
    rank = 4;
end
end

function tyres = localListCachedTyres(selectedPath)
tgmRoot = fullfile(tyre_designer_project_root(), "tyres", "cache", "tgm");
files = dir(fullfile(tgmRoot, "*.tgm"));
tyres = localEmptyTyres();

for index = 1:numel(files)
    path = string(fullfile(tgmRoot, files(index).name));
    item = struct();
    item.fileName = string(files(index).name);
    item.displayName = localTyreDisplayName(files(index).name);
    item.path = path;
    item.selected = selectedPath ~= "" && localNormalizePath(path) == selectedPath;
    item.sha256 = "";
    item.lengthBytes = double(files(index).bytes);
    item.sourceCount = NaN;
    item.source = "cache";
    tyres(end + 1, 1) = item; %#ok<AGROW>
end
end

function tyres = localEmptyTyres()
tyres = repmat(struct( ...
    "displayName", "", ...
    "fileName", "", ...
    "path", "", ...
    "selected", false, ...
    "sha256", "", ...
    "lengthBytes", NaN, ...
    "sourceCount", NaN, ...
    "source", ""), 0, 1);
end

function name = localTyreDisplayName(fileName)
[~, stem] = fileparts(fileName);
stem = regexprep(string(stem), "__[0-9a-fA-F]{12}$", "");
name = replace(stem, "_", " ");
end

function path = localResolveProjectPath(path)
path = string(path);
if path == ""
    return;
end

pathText = char(path);
if isempty(regexp(pathText, "^[A-Za-z]:[\\/]|^\\\\", "once"))
    pathText = fullfile(tyre_designer_project_root(), pathText);
end
path = string(pathText);
end

function normalized = localNormalizePath(path)
path = string(path);
if path == ""
    normalized = "";
    return;
end

pathText = char(path);
if isempty(regexp(pathText, "^[A-Za-z]:[\\/]|^\\\\", "once"))
    pathText = fullfile(tyre_designer_project_root(), pathText);
end

info = dir(pathText);
if ~isempty(info)
    pathText = fullfile(info(1).folder, info(1).name);
end

normalized = lower(replace(string(pathText), "/", "\"));
end

function encoded = localEncodePlotData(plotData)
encoded = struct();
encoded.summary = plotData.summary;
encoded.geometry = localTableToRecords(plotData.geometry);
encoded.treadDepth = localTableToRecords(plotData.treadDepth);
encoded.rubberCrossSection = localTableToRecords(plotData.rubberCrossSection);
encoded.plyParams = localTableToRecords(plotData.plyParams);
encoded.plyCrossSection = localTableToRecords(plotData.plyCrossSection);
encoded.materials = localTableToRecords(plotData.materials);
end

function records = localTableToRecords(T)
records = table2struct(T);
names = string(T.Properties.VariableNames);
for row = 1:numel(records)
    for col = 1:numel(names)
        field = char(names(col));
        value = records(row).(field);
        if iscell(value) && isscalar(value)
            value = value{1};
        end
        if ischar(value)
            value = string(value);
        end
        records(row).(field) = value;
    end
end
end
