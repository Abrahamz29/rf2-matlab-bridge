function model = rf2TgmGenExtractInputsImpl(options)
%RF2TGMGENEXTRACTINPUTS Extract ODS input cells into a project seed model.
arguments
    options.OdsPath (1,1) string = fullfile(rf2TgmProjectRoot(), "tyres", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.OutPath (1,1) string = fullfile(rf2TgmProjectRoot(), "tmp", "tgm_gen_port", "inputs.json")
    options.Sheets string = ["General", "Geometry", "Construction", "Compound", "Realtime", "WLF", "ContactProps", "LoadSens", "Materials", "TBC"]
    options.EditableOnly (1,1) logical = false
    options.PythonExe (1,1) string = ""
end

pythonExe = options.PythonExe;
if pythonExe == ""
    pythonExe = localFindPython();
end

sheetArgs = strjoin("""" + options.Sheets + """", " ");
editableArg = "";
if options.EditableOnly
    editableArg = " --editable-only";
end
scriptPath = fullfile(rf2TgmProjectRoot(), "tyres", "tools", "tgm_gen_ods.py");
command = sprintf('"%s" "%s" --ods "%s" extract-inputs --sheets %s --out "%s"%s --json', ...
    pythonExe, scriptPath, options.OdsPath, sheetArgs, options.OutPath, editableArg);
[status, output] = system(command);
if status ~= 0
    error("rf2TgmGenExtractInputsImpl:CommandFailed", "Input extraction failed:\n%s", output);
end
model = jsondecode(output);
end

function pythonExe = localFindPython()
candidates = [
    fullfile(getenv("USERPROFILE"), ".platformio", "penv", "Scripts", "python.exe")
    "python"
    "py"
];
for index = 1:numel(candidates)
    [status, ~] = system(sprintf('"%s" --version', candidates(index)));
    if status == 0
        pythonExe = candidates(index);
        return;
    end
end
error("rf2TgmGenExtractInputsImpl:PythonNotFound", "Could not find a Python executable.");
end

