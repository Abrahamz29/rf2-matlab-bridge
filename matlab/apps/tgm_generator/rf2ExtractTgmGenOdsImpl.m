function report = rf2ExtractTgmGenOdsImpl(options)
%RF2EXTRACTTGMGENODS Reconstruct ODS reference exports for the TGM Gen port.
arguments
    options.OdsPath (1,1) string = fullfile(rf2TgmProjectRoot(), "tools", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.OutDir (1,1) string = fullfile(rf2TgmProjectRoot(), "tmp", "tgm_gen_port")
    options.PythonExe (1,1) string = ""
end

pythonExe = options.PythonExe;
if pythonExe == ""
    pythonExe = localFindPython();
end

scriptPath = fullfile(rf2TgmProjectRoot(), "tools", "tgm_gen_ods.py");
command = sprintf('"%s" "%s" --ods "%s" export-reference --out-dir "%s" --json', ...
    pythonExe, scriptPath, options.OdsPath, options.OutDir);
[status, output] = system(command);
if status ~= 0
    error("rf2ExtractTgmGenOdsImpl:CommandFailed", "ODS extraction failed:\n%s", output);
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
error("rf2ExtractTgmGenOdsImpl:PythonNotFound", "Could not find a Python executable.");
end
