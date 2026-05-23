function status = rf2RunAutomation(configPath, outputDir, dryRun)
%RF2RUNAUTOMATION Run scripted rFactor 2 maneuvers from MATLAB.
if nargin < 1 || isempty(configPath)
    configPath = fullfile("scenarios", "blacklake_step_steer_batch.json");
end
if nargin < 2 || isempty(outputDir)
    outputDir = fullfile("logs");
end
if nargin < 3 || isempty(dryRun)
    dryRun = false;
end

projectRoot = fileparts(fileparts(mfilename("fullpath")));
pythonExe = "C:\Users\Victor\.platformio\penv\Scripts\python.exe";
scriptPath = fullfile(projectRoot, "bridge", "python", "rf2_automation.py");
configFullPath = localResolvePath(projectRoot, configPath);
outputFullPath = localResolvePath(projectRoot, outputDir);

command = sprintf('"%s" "%s" "%s" --out "%s"', ...
    pythonExe, scriptPath, configFullPath, outputFullPath);
if dryRun
    command = command + " --dry-run";
end
[code, text] = system(command);
status = struct("exitCode", code, "output", string(strtrim(text)));
disp(status);
end

function resolved = localResolvePath(projectRoot, pathValue)
pathText = string(pathValue);
if isfile(pathText) || isfolder(pathText) || localIsAbsolutePath(pathText)
    resolved = char(pathText);
else
    resolved = fullfile(projectRoot, char(pathText));
end
end

function tf = localIsAbsolutePath(pathValue)
pathText = char(pathValue);
tf = ~isempty(regexp(pathText, "^[A-Za-z]:[\\/]", "once")) || startsWith(pathText, "\\");
end
