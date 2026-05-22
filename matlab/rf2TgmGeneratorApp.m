function app = rf2TgmGeneratorApp(inputPath, options)
%RF2TGMGENERATORAPP Open the modern HTML UI for the TGM Generator port.
arguments
    inputPath (1,1) string = ""
    options.Headless (1,1) logical = false
end

state = localBuildState(inputPath);
if options.Headless
    app = state;
    return;
end

fig = uifigure("Name", "rF2 TGM Generator", "Position", [100 80 1280 820]);
html = uihtml(fig, ...
    "HTMLSource", fullfile(fileparts(mfilename("fullpath")), "assets", "rf2_tgm_generator.html"), ...
    "Position", [1 1 1280 820]);
html.Data = state;
html.DataChangedFcn = @(src, event) localHandleCommand(src, event); %#ok<INUSD>

app = struct("Figure", fig, "Html", html, "State", state);
end

function state = localBuildState(inputPath)
state = struct();
state.kind = "state";
state.status = "ready";
state.inputPath = inputPath;
state.loaded = false;
state.message = "No TGM loaded.";
state.summary = struct();
state.plotData = struct();
state.behaviour = localEncodeBehaviourData(rf2TgmBehaviourPlotData);
state.odsPath = fullfile("tools", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods");
state.validation = struct("available", true, "message", "Acceptance test not run.");
state.inputModel = struct("loaded", false, "input_count", 0, "sheet_counts", struct());

if inputPath ~= "" && isfile(inputPath)
    model = rf2ReadTgm(inputPath);
    plotData = rf2TgmPlotData(model);
    state.loaded = true;
    state.message = "Loaded " + string(model.fileName);
    state.summary = model.summary;
    state.plotData = localEncodePlotData(plotData);
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
        case "runAcceptance"
            state = localBuildState(string(data.inputPath));
            state.status = "running acceptance";
            state.validation = rf2TgmGenGenerate("OdsPath", string(data.odsPath));
            if state.validation.equal
                state.message = "ODS acceptance test passed.";
                state.status = "validated";
            else
                state.message = "ODS acceptance test failed.";
                state.status = "validation failed";
            end
            html.Data = state;
        case "loadOdsInputs"
            state = localBuildState(string(data.inputPath));
            state.inputModel = rf2TgmGenExtractInputs("OdsPath", string(data.odsPath));
            state.inputModel.loaded = true;
            state.message = "Loaded ODS input model.";
            html.Data = state;
        case "generateFromInputs"
            state = localBuildState(string(data.inputPath));
            projectPath = fullfile("tmp", "tgm_gen_port_ui", "inputs_from_ui.json");
            if ~isfolder(fileparts(projectPath))
                mkdir(fileparts(projectPath));
            end
            projectText = jsonencode(data.inputModel);
            fid = fopen(projectPath, "w");
            if fid < 0
                error("rf2TgmGeneratorApp:ProjectWriteFailed", "Could not write %s", projectPath);
            end
            cleanup = onCleanup(@() fclose(fid));
            fwrite(fid, projectText, "char");
            clear cleanup
            state.inputModel = data.inputModel;
            state.validation = rf2TgmGenGenerate( ...
                "OdsPath", string(data.odsPath), ...
                "OutDir", fullfile("tmp", "tgm_gen_port_ui"), ...
                "Mode", "recursive", ...
                "FallbackOnError", false, ...
                "ProjectPath", projectPath);
            state.message = "Generated from UI input model.";
            state.status = "generated";
            html.Data = state;
        otherwise
            html.Data = struct("kind", "error", "message", "Unknown command: " + string(data.command));
    end
catch exception
    html.Data = struct("kind", "error", "message", string(exception.message));
end
end

function encoded = localEncodePlotData(plotData)
encoded = struct();
encoded.summary = plotData.summary;
encoded.geometry = localTableToRecords(plotData.geometry);
encoded.treadDepth = localTableToRecords(plotData.treadDepth);
encoded.plyParams = localTableToRecords(plotData.plyParams);
encoded.materials = localTableToRecords(plotData.materials);
end

function encoded = localEncodeBehaviourData(behaviour)
encoded = struct();
encoded.loaded = behaviour.loaded;
encoded.path = behaviour.path;
encoded.sampleCount = behaviour.sampleCount;
encoded.summary = behaviour.summary;
encoded.records = localTableToRecords(behaviour.data);
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
