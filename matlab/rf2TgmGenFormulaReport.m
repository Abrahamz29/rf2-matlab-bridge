function report = rf2TgmGenFormulaReport(options)
%RF2TGMGENFORMULAREPORT Run the ODS formula harness for selected sheets.
arguments
    options.OdsPath (1,1) string = fullfile("tools", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.Sheets string = ["General", "Realtime", "Materials"]
    options.PythonExe (1,1) string = ""
end

pythonExe = options.PythonExe;
if pythonExe == ""
    pythonExe = localFindPython();
end

sheetArgs = strjoin("""" + options.Sheets + """", " ");
scriptPath = fullfile("tools", "tgm_gen_ods.py");
command = sprintf('"%s" "%s" --ods "%s" formula-report --sheets %s --json', ...
    pythonExe, scriptPath, options.OdsPath, sheetArgs);
[status, output] = system(command);
if status ~= 0
    error("rf2TgmGenFormulaReport:CommandFailed", "Formula report failed:\n%s", output);
end
report = jsondecode(output);
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
error("rf2TgmGenFormulaReport:PythonNotFound", "Could not find a Python executable.");
end
