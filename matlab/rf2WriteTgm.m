function rf2WriteTgm(model, outPath, options)
%RF2WRITETGM Write a TGM model back to disk.
arguments
    model (1,1) struct
    outPath (1,1) string
    options.StripGeneratedLookups (1,1) logical = true
end

if ~isfield(model, "lines")
    error("rf2WriteTgm:InvalidModel", "Model must come from rf2ReadTgm and contain original lines.");
end

outLines = strings(0, 1);
skipSection = false;

for index = 1:numel(model.lines)
    line = model.lines(index);
    trimmed = strtrim(line);
    if startsWith(trimmed, "[")
        section = extractBefore(extractAfter(trimmed, "["), "]");
        skipSection = options.StripGeneratedLookups && ismember(section, ["LookupV2", "PatchV1"]);
    end
    if ~skipSection
        outLines(end + 1, 1) = line; %#ok<AGROW>
    end
end

outDir = fileparts(outPath);
if strlength(outDir) > 0 && ~isfolder(outDir)
    mkdir(outDir);
end

fid = fopen(outPath, "w");
cleanup = onCleanup(@() fclose(fid));
if fid < 0
    error("rf2WriteTgm:OpenFailed", "Could not open output file: %s", outPath);
end
for index = 1:numel(outLines)
    fprintf(fid, "%s\n", outLines(index));
end
end
