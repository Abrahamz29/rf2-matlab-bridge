function report = rf2TgmGenGenerate(options)
%RF2TGMGENGENERATE Generate and compare TGM Gen ODS exports.
arguments
    options.OdsPath (1,1) string = fullfile("tools", "downloads", "studio397", "TGM Gen V0.33 - GY F1 1975 Front.ods")
    options.OutDir (1,1) string = fullfile("tmp", "tgm_gen_port")
    options.Mode (1,1) string {mustBeMember(options.Mode, ["cached", "recursive"])} = "recursive"
    options.FallbackOnError (1,1) logical = false
    options.ProjectPath (1,1) string = ""
    options.PythonExe (1,1) string = ""
end

pythonExe = options.PythonExe;
if pythonExe == ""
    pythonExe = localFindPython();
end

scriptPath = fullfile("tools", "tgm_gen_ods.py");
localRunJson(pythonExe, scriptPath, options.OdsPath, "export-reference", ["--out-dir", options.OutDir]);
generateArgs = ["--out-dir", options.OutDir, "--mode", options.Mode];
if options.FallbackOnError
    generateArgs(end + 1) = "--fallback-on-error";
end
if options.ProjectPath ~= ""
    generateArgs(end + 1:end + 2) = ["--project", options.ProjectPath];
end
generateReport = localRunJson(pythonExe, scriptPath, options.OdsPath, "generate", generateArgs);

referenceTgm = fullfile(options.OutDir, "reference_from_ods.tgm");
referenceTbc = fullfile(options.OutDir, "reference_from_ods.tbc");
generatedTgm = fullfile(options.OutDir, "generated.tgm");
generatedTbc = fullfile(options.OutDir, "generated.tbc");

tgmCompare = localRunCompare(pythonExe, scriptPath, referenceTgm, generatedTgm, true);
tbcCompare = localRunCompare(pythonExe, scriptPath, referenceTbc, generatedTbc, false);

report = struct();
report.kind = "generationReport";
report.odsPath = options.OdsPath;
report.outDir = options.OutDir;
report.mode = options.Mode;
report.fallbackOnError = options.FallbackOnError;
report.projectPath = options.ProjectPath;
report.generated = generateReport.outputs;
report.tgm = tgmCompare;
report.tbc = tbcCompare;
report.equal = logical(tgmCompare.equal) && logical(tbcCompare.equal);
end

function report = localRunJson(pythonExe, scriptPath, odsPath, commandName, extraArgs)
args = strjoin("""" + extraArgs + """", " ");
command = sprintf('"%s" "%s" --ods "%s" %s %s --json', ...
    pythonExe, scriptPath, odsPath, commandName, args);
[status, output] = system(command);
if status ~= 0
    error("rf2TgmGenGenerate:CommandFailed", "%s failed:\n%s", commandName, output);
end
report = jsondecode(output);
end

function report = localRunCompare(pythonExe, scriptPath, referencePath, candidatePath, stripLookup)
stripArg = "";
if stripLookup
    stripArg = " --strip-lookup";
end
command = sprintf('"%s" "%s" compare "%s" "%s"%s --json', ...
    pythonExe, scriptPath, referencePath, candidatePath, stripArg);
[status, output] = system(command);
if status ~= 0 && strlength(strtrim(output)) == 0
    error("rf2TgmGenGenerate:CompareFailed", "Compare failed:\n%s", output);
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
error("rf2TgmGenGenerate:PythonNotFound", "Could not find a Python executable.");
end
