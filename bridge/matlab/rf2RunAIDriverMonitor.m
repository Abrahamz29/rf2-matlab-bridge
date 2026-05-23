function status = rf2RunAIDriverMonitor(durationSeconds, outputDir, dryRun)
%RF2RUNAIDRIVERMONITOR Run the canned AI-driver telemetry monitor scenario.
if nargin < 1 || isempty(durationSeconds)
    durationSeconds = 60;
end
if nargin < 2 || isempty(outputDir)
    outputDir = fullfile("logs");
end
if nargin < 3 || isempty(dryRun)
    dryRun = false;
end

projectRoot = fileparts(fileparts(mfilename("fullpath")));
scenarioPath = fullfile(projectRoot, "scenarios", "tigermoth_ai_monitor.json");
data = jsondecode(fileread(scenarioPath));

for idx = 1:numel(data.scenarios)
    data.scenarios(idx).duration_s = durationSeconds;
    data.scenarios(idx).name = sprintf("ai_monitor_%ds_rep%02d", durationSeconds, idx);
end

tmpScenario = fullfile(projectRoot, "scenarios", sprintf("tigermoth_ai_monitor_%ds_tmp.json", durationSeconds));
cleanupObj = onCleanup(@() localDeleteIfExists(tmpScenario));
fid = fopen(tmpScenario, "w");
assert(fid >= 0, "Could not create temporary AI monitor scenario.");
fwrite(fid, jsonencode(data, PrettyPrint=true), "char");
fclose(fid);

status = rf2RunAutomation(tmpScenario, outputDir, dryRun);
end

function localDeleteIfExists(pathStr)
if exist(pathStr, "file")
    delete(pathStr);
end
end
