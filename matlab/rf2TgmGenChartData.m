function report = rf2TgmGenChartData(options)
%RF2TGMGENCHARTDATA Evaluate embedded ODS chart source ranges.
arguments
    options.OdsPath (1,1) string = fullfile("tools", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.Mode (1,1) string {mustBeMember(options.Mode, ["cached", "recursive"])} = "recursive"
    options.FallbackOnError (1,1) logical = false
    options.ProjectPath (1,1) string = ""
    options.PythonExe (1,1) string = ""
end

pythonExe = options.PythonExe;
if pythonExe == ""
    pythonExe = localFindPython();
end

extraArgs = ["--mode", options.Mode];
if options.FallbackOnError
    extraArgs(end + 1) = "--fallback-on-error";
end
if options.ProjectPath ~= ""
    extraArgs(end + 1:end + 2) = ["--project", options.ProjectPath];
end

scriptPath = fullfile("tools", "tgm_gen_ods.py");
args = strjoin("""" + extraArgs + """", " ");
command = sprintf('"%s" "%s" --ods "%s" chart-data %s --json', ...
    pythonExe, scriptPath, options.OdsPath, args);
[status, output] = system(command);
if status ~= 0
    error("rf2TgmGenChartData:CommandFailed", "Chart data extraction failed:\n%s", output);
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
error("rf2TgmGenChartData:PythonNotFound", "Could not find a Python executable.");
end
