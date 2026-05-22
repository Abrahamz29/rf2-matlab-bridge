function report = rf2TgmPrepareTTool(options)
%RF2TGMPREPARETTOOL Generate verified TGM/TBC files and copy them to pTool.
arguments
    options.OdsPath (1,1) string = fullfile("tools", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.OutDir (1,1) string = fullfile("tmp", "tgm_gen_ttool")
    options.PToolDir (1,1) string = fullfile(getenv("ProgramFiles(x86)"), "Steam", "steamapps", "common", "rFactor 2", "pTool")
    options.OutputBaseName (1,1) string = "generated_from_matlab"
    options.LaunchTTool (1,1) logical = false
    options.ModModeExe (1,1) string = fullfile(getenv("ProgramFiles(x86)"), "Steam", "steamapps", "common", "rFactor 2", "Bin64", "rFactor2 Mod Mode.exe")
end

validation = rf2TgmGenGenerate( ...
    "OdsPath", options.OdsPath, ...
    "OutDir", options.OutDir, ...
    "Mode", "recursive", ...
    "FallbackOnError", false);
if ~validation.equal
    error("rf2TgmPrepareTTool:AcceptanceFailed", "Generated files did not pass ODS acceptance.");
end

if ~isfolder(options.PToolDir)
    error("rf2TgmPrepareTTool:PToolMissing", "pTool directory not found: %s", options.PToolDir);
end

sourceTgm = fullfile(options.OutDir, "generated.tgm");
sourceTbc = fullfile(options.OutDir, "generated.tbc");
targetTgm = fullfile(options.PToolDir, options.OutputBaseName + ".tgm");
targetTbc = fullfile(options.PToolDir, options.OutputBaseName + ".tbc");
copyfile(sourceTgm, targetTgm, "f");
copyfile(sourceTbc, targetTbc, "f");

launched = false;
if options.LaunchTTool
    if ~isfile(options.ModModeExe)
        error("rf2TgmPrepareTTool:ModModeMissing", "Mod Mode executable not found: %s", options.ModModeExe);
    end
    command = sprintf('start "" "%s" +tTool +multiple +trace=2', options.ModModeExe);
    [status, output] = system(command);
    if status ~= 0
        error("rf2TgmPrepareTTool:LaunchFailed", "Could not launch tTool:\n%s", output);
    end
    launched = true;
end

report = struct();
report.kind = "ttoolPrepareReport";
report.validation = validation;
report.pToolDir = options.PToolDir;
report.sourceTgm = sourceTgm;
report.sourceTbc = sourceTbc;
report.targetTgm = targetTgm;
report.targetTbc = targetTbc;
report.launched = launched;
end
