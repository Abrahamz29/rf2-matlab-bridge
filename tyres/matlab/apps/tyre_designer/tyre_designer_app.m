function app = tyre_designer_app(inputPath, options)
%TYRE_DESIGNER_APP Open the lightweight tyre designer UI.
arguments
    inputPath (1,1) string = ""
    options.Headless (1,1) logical = false
end

state = localBuildState(inputPath);
if options.Headless
    app = state;
    return;
end

fig = uifigure("Name", "tyre_designer", "Position", [120 90 1280 760]);
html = uihtml(fig, ...
    "HTMLSource", fullfile(fileparts(mfilename("fullpath")), "assets", "tyre_designer.html"), ...
    "Position", [1 1 1280 760]);
html.Data = state;
html.DataChangedFcn = @(src, event) localHandleCommand(src, event); %#ok<INUSD>

app = struct("Figure", fig, "Html", html, "State", state);
end

function state = localBuildState(inputPath)
state = struct();
state.kind = "geometryState";
state.status = "ready";
state.inputPath = inputPath;
state.loaded = false;
state.message = "No TGM loaded.";
state.summary = struct();
state.plotData = struct();
state.database = localDatabaseInfo();
state.tyres = localListKnownTyres(inputPath);

if inputPath ~= "" && isfile(inputPath)
    model = tyre_designer_read_tgm(inputPath);
    plotData = tyre_designer_plot_data(model);
    state.loaded = true;
    state.status = "loaded";
    state.message = "Loaded " + string(model.fileName);
    state.summary = model.summary;
    state.inputPath = string(model.path);
    state.plotData = localEncodePlotData(plotData);
elseif inputPath ~= ""
    state.status = "not found";
    state.message = "TGM not found: " + inputPath;
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
            html.Data = localBuildState(string(data.path));
        otherwise
            html.Data = struct("kind", "error", "message", "Unknown command: " + string(data.command));
    end
catch exception
    html.Data = struct("kind", "error", "message", string(exception.message));
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
rows = fetch(conn, "select display_name, file_name, local_copy_path, sha256, length_bytes, source_count from tyres order by display_name");

for index = 1:height(rows)
    resolvedPath = localResolveProjectPath(string(rows.local_copy_path(index)));
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
