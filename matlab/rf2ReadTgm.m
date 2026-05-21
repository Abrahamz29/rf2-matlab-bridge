function model = rf2ReadTgm(path)
%RF2READTGM Read a rFactor 2 TGM file into a MATLAB struct.
arguments
    path (1,1) string
end

if ~isfile(path)
    error("rf2ReadTgm:FileNotFound", "TGM file not found: %s", path);
end

rawText = fileread(path);
lines = splitlines(string(rawText));

sections = strings(0, 1);
keys = strings(0, 1);
nodeIndex = zeros(0, 1);
valueText = strings(0, 1);
values = cell(0, 1);

section = "";
currentNode = NaN;
lookupV2Lines = 0;
patchV1Lines = 0;

for lineIndex = 1:numel(lines)
    line = strtrim(lines(lineIndex));
    if line == ""
        continue;
    end

    if startsWith(line, "[")
        token = extractBefore(extractAfter(line, "["), "]");
        section = token;
        currentNode = NaN;
        if section == "Node"
            nodeMatch = regexp(line, '\[Node\]\s*//\s*(\d+)', 'tokens', 'once');
            if ~isempty(nodeMatch)
                currentNode = str2double(nodeMatch{1});
            end
        end
        continue;
    end

    if section == "LookupV2"
        lookupV2Lines = lookupV2Lines + 1;
        continue;
    elseif section == "PatchV1"
        patchV1Lines = patchV1Lines + 1;
        continue;
    end

    equalsIndex = strfind(line, "=");
    if isempty(equalsIndex)
        continue;
    end

    key = strtrim(extractBefore(line, equalsIndex(1)));
    rawValue = strtrim(extractAfter(line, equalsIndex(1)));
    rawValue = strtrim(extractBefore(rawValue + "//", "//"));

    sections(end + 1, 1) = section; %#ok<AGROW>
    keys(end + 1, 1) = key; %#ok<AGROW>
    nodeIndex(end + 1, 1) = currentNode; %#ok<AGROW>
    valueText(end + 1, 1) = rawValue; %#ok<AGROW>
    values{end + 1, 1} = localParseValue(rawValue); %#ok<AGROW>
end

parameters = table(sections, keys, nodeIndex, valueText, values, ...
    'VariableNames', {'section', 'key', 'nodeIndex', 'valueText', 'value'});

nodeRows = parameters.section == "Node";
nodeCount = numel(unique(parameters.nodeIndex(nodeRows & ~isnan(parameters.nodeIndex))));

model = struct();
model.path = path;
model.fileName = string(getfield(dir(path), "name")); %#ok<GFLD>
model.rawText = rawText;
model.lines = lines;
model.parameters = parameters;
model.nodeCount = nodeCount;
model.lookupV2LineCount = lookupV2Lines;
model.patchV1LineCount = patchV1Lines;
model.summary = localSummary(parameters, nodeCount, lookupV2Lines, patchV1Lines);
end

function value = localParseValue(text)
text = strip(string(text));
if startsWith(text, "(") && endsWith(text, ")")
    inner = extractBetween(text, 2, strlength(text) - 1);
    if isempty(inner)
        value = [];
        return;
    end
    parts = split(inner, ",");
    numeric = nan(1, numel(parts));
    allNumeric = true;
    for index = 1:numel(parts)
        candidate = str2double(strip(parts(index)));
        if isnan(candidate) && strip(parts(index)) ~= "NaN"
            allNumeric = false;
            break;
        end
        numeric(index) = candidate;
    end
    if allNumeric
        value = numeric;
    else
        value = cellstr(strip(parts));
    end
else
    numeric = str2double(text);
    if ~isnan(numeric) || text == "NaN"
        value = numeric;
    else
        value = text;
    end
end
end

function summary = localSummary(parameters, nodeCount, lookupV2Lines, patchV1Lines)
summary = struct();
summary.nodeCount = nodeCount;
summary.lookupV2LineCount = lookupV2Lines;
summary.patchV1LineCount = patchV1Lines;
summary.qsaParameterCount = nnz(parameters.section == "QuasiStaticAnalysis");
summary.nodeParameterCount = nnz(parameters.section == "Node");
summary.realtimeParameterCount = nnz(parameters.section == "Realtime");
summary.materialRows = nnz(ismember(parameters.key, ["BulkMaterial", "TreadMaterial", "PlyMaterial"]));
summary.plyParamRows = nnz(parameters.key == "PlyParams");
end
