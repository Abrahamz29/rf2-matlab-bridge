function report = rf2TgmGenChartReportImpl(options)
%RF2TGMGENCHARTREPORT Extract embedded ODS chart source ranges.
arguments
    options.OdsPath (1,1) string = fullfile(rf2TgmProjectRoot(), "tyres", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.PythonExe (1,1) string = ""
end

pythonExe = options.PythonExe;
if pythonExe == ""
    pythonExe = localFindPython();
end

scriptPath = fullfile(rf2TgmProjectRoot(), "tyres", "tools", "tgm_gen_ods.py");
command = sprintf('"%s" "%s" --ods "%s" chart-report --json', ...
    pythonExe, scriptPath, options.OdsPath);
[status, output] = system(command);
if status ~= 0
    error("rf2TgmGenChartReportImpl:CommandFailed", "Chart report failed:\n%s", output);
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
error("rf2TgmGenChartReportImpl:PythonNotFound", "Could not find a Python executable.");
end

