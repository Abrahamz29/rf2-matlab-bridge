function behaviour = rf2TgmBehaviourPlotData(options)
%RF2TGMBEHAVIOURPLOTDATA Read latest tTool realtime CSV for UI plots.
arguments
    options.ResultsRoot (1,1) string = fullfile("scenarios", "tyre", "ttool", "results")
    options.CsvPath (1,1) string = ""
    options.MaxRows (1,1) double = 3000
end

csvPath = options.CsvPath;
if csvPath == ""
    csvPath = localLatestRealtimeCsv(options.ResultsRoot);
end

emptyData = table([], [], [], [], [], [], [], [], [], [], [], ...
    'VariableNames', {'sample', 'testIndex', 'slipAngleDeg', 'slipRatioPct', ...
    'verticalForceN', 'longForceN', 'latForceN', 'aligningTorqueNm', ...
    'camberDeg', 'gaugePressureKpa', 'temperatureC'});

behaviour = struct();
behaviour.loaded = false;
behaviour.path = csvPath;
behaviour.sampleCount = 0;
behaviour.data = emptyData;
behaviour.summary = struct("maxLatForceN", NaN, "maxLongForceN", NaN, "maxVerticalForceN", NaN);

if csvPath == "" || ~isfile(csvPath)
    return;
end

opts = detectImportOptions(csvPath, "VariableNamingRule", "preserve");
T = readtable(csvPath, opts);
rowCount = height(T);
if rowCount == 0
    return;
end

takeCount = min(rowCount, max(1, round(options.MaxRows)));
rowIndex = unique(round(linspace(1, rowCount, takeCount))).';

data = table();
data.sample = rowIndex;
data.testIndex = localColumn(T, "Realtime Test Index", rowIndex);
data.slipAngleDeg = localColumn(T, "Slip Angle (deg)", rowIndex);
data.slipRatioPct = localColumn(T, "Slip Ratio (%)", rowIndex);
data.verticalForceN = localColumn(T, "Vertical Force (N)", rowIndex);
data.longForceN = localColumn(T, "Long Force (N)", rowIndex);
data.latForceN = localColumn(T, "Lat Force (N)", rowIndex);
data.aligningTorqueNm = localColumn(T, "Aligning Torque (Nm)", rowIndex);
data.camberDeg = localColumn(T, "Camber (deg)", rowIndex);
data.gaugePressureKpa = localColumn(T, "Gauge Pressure (kPa)", rowIndex);
data.temperatureC = localColumn(T, "Temperature (C)", rowIndex);

behaviour.loaded = true;
behaviour.sampleCount = rowCount;
behaviour.data = data;
behaviour.summary = struct( ...
    "maxLatForceN", max(abs(localColumn(T, "Lat Force (N)", (1:rowCount).')), [], "omitnan"), ...
    "maxLongForceN", max(abs(localColumn(T, "Long Force (N)", (1:rowCount).')), [], "omitnan"), ...
    "maxVerticalForceN", max(abs(localColumn(T, "Vertical Force (N)", (1:rowCount).')), [], "omitnan"));
end

function csvPath = localLatestRealtimeCsv(resultsRoot)
csvPath = "";
if ~isfolder(resultsRoot)
    return;
end

files = dir(fullfile(resultsRoot, "**", "CustomRealtimeTable.csv"));
if isempty(files)
    return;
end

[~, index] = max([files.datenum]);
csvPath = string(fullfile(files(index).folder, files(index).name));
end

function values = localColumn(T, columnName, rowIndex)
if ismember(columnName, string(T.Properties.VariableNames))
    raw = T.(columnName);
    values = raw(rowIndex);
    if iscell(values)
        values = str2double(string(values));
    end
    if isstring(values) || ischar(values)
        values = str2double(string(values));
    end
    values = double(values);
else
    values = nan(numel(rowIndex), 1);
end
values = values(:);
end
