function data = rf2ListInstalledTracks()
%RF2LISTINSTALLEDTRACKS List installed rFactor 2 locations via the Python runner.
projectRoot = fileparts(fileparts(mfilename("fullpath")));
pythonExe = "C:\Users\Victor\.platformio\penv\Scripts\python.exe";
scriptPath = fullfile(projectRoot, "bridge", "python", "rf2_automation.py");

command = sprintf('"%s" "%s" --list-tracks', pythonExe, scriptPath);
[code, text] = system(command);
if code ~= 0
    error("rf2ListInstalledTracks failed: %s", strtrim(text));
end
data = jsondecode(text);
end
