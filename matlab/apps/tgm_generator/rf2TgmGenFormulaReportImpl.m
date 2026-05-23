function report = rf2TgmGenFormulaReportImpl(options)
%RF2TGMGENFORMULAREPORT Run the ODS formula harness for selected sheets.
arguments
    options.OdsPath (1,1) string = fullfile(rf2TgmProjectRoot(), "tools", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.Sheets string = ["General", "Realtime", "Materials"]
    options.Mode (1,1) string {mustBeMember(options.Mode, ["cached", "recursive"])} = "recursive"
    options.FallbackOnError (1,1) logical = false
    options.ProjectPath (1,1) string = ""
    options.PythonExe (1,1) string = ""
end

pythonExe = options.PythonExe;
if pythonExe == ""
    pythonExe = localFindPython();
end

sheetArgs = strjoin("""" + options.Sheets + """", " ");
scriptPath = fullfile(rf2TgmProjectRoot(), "tools", "tgm_gen_ods.py");
fallbackArg = "";
if options.FallbackOnError
    fallbackArg = " --fallback-on-error";
end
projectArg = "";
if options.ProjectPath ~= ""
    projectArg = " --project """ + options.ProjectPath + """";
end
command = sprintf('"%s" "%s" --ods "%s" formula-report --sheets %s --mode %s%s%s --json', ...
    pythonExe, scriptPath, options.OdsPath, sheetArgs, options.Mode, fallbackArg, projectArg);
[status, output] = system(command);
if status ~= 0
    error("rf2TgmGenFormulaReportImpl:CommandFailed", "Formula report failed:\n%s", output);
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
error("rf2TgmGenFormulaReportImpl:PythonNotFound", "Could not find a Python executable.");
end
