function model = rf2TgmGeometryReadTgmImpl(path)
%RF2TGMGEOMETRYREADTGMIMPL Read a rFactor 2 TGM file into a MATLAB struct.
arguments
    path (1,1) string
end

if ~isfile(path)
    error("rf2TgmGeometryReadTgmImpl:FileNotFound", "TGM file not found: %s", path);
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
    values{end + 1, 1} = localParseValue(rawValue, key); %#ok<AGROW>
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

function value = localParseValue(text, key)
text = strip(string(text));
if startsWith(text, "(") && endsWith(text, ")")
    inner = extractBetween(text, 2, strlength(text) - 1);
    if isempty(inner)
        value = [];
        return;
    end
    parts = split(inner, ",");

    width = localExpectedTupleWidth(key);
    if width > 0
        numeric = localParseTuple(parts, width, localExpectedRanges(key));
    else
        numeric = nan(1, numel(parts));
        for index = 1:numel(parts)
            numeric(index) = localParseNumber(parts(index));
        end
    end

    if ~any(isnan(numeric)) || all(strip(parts) == "NaN")
        value = numeric;
    else
        value = cellstr(strip(parts));
    end
else
    numeric = localParseNumber(text);
    if ~isnan(numeric) || text == "NaN"
        value = numeric;
    else
        value = text;
    end
end
end

function numeric = localParseTuple(parts, width, ranges)
parts = strip(parts(:));
partCount = numel(parts);
bestScore = inf;
bestValues = nan(1, width);

    function search(partIndex, fieldIndex, values, score)
        remainingParts = partCount - partIndex + 1;
        remainingFields = width - fieldIndex + 1;
        if remainingParts < remainingFields || remainingParts > remainingFields * 2
            return;
        end
        if fieldIndex > width
            if partIndex > partCount && score < bestScore
                bestScore = score;
                bestValues = values;
            end
            return;
        end

        for groupLength = 1:2
            if partIndex + groupLength - 1 > partCount
                continue;
            end
            [candidate, ok, candidateScore] = localParseTupleCandidate(parts(partIndex:partIndex + groupLength - 1));
            if ~ok
                continue;
            end
            rangeScore = localRangeScore(candidate, ranges(fieldIndex, :));
            nextValues = values;
            nextValues(fieldIndex) = candidate;
            search(partIndex + groupLength, fieldIndex + 1, nextValues, score + candidateScore + rangeScore);
        end
    end

search(1, 1, nan(1, width), 0);
numeric = bestValues;
end

function [value, ok, score] = localParseTupleCandidate(parts)
parts = strip(parts(:));
ok = false;
value = NaN;
score = inf;

if numel(parts) == 1
    value = localParseNumber(parts(1));
    ok = ~isnan(value) || parts(1) == "NaN";
    score = 0;
    return;
end

if numel(parts) ~= 2 || ~localCanBeDecimalComma(parts(1), parts(2))
    return;
end

value = str2double(parts(1) + "." + parts(2));
ok = ~isnan(value);
score = -0.1;
if contains(parts(2), ["e", "E"])
    score = 0.2;
end
end

function tf = localCanBeDecimalComma(left, right)
left = strip(left);
right = strip(right);
tf = ~isempty(regexp(char(left), "^[+-]?\d+$", "once")) ...
    && ~isempty(regexp(char(right), "^\d+(?:[eE][+-]?\d+)?$", "once"));
end

function value = localParseNumber(text)
text = strip(string(text));
if contains(text, ",") && ~contains(text, ".")
    value = str2double(replace(text, ",", "."));
    if ~isnan(value)
        return;
    end
end
value = str2double(text);
end

function width = localExpectedTupleWidth(key)
switch string(key)
    case {"Geometry", "PlyParams"}
        width = 3;
    case {"InnerGeometryOverride", "RingAndRim"}
        width = 2;
    case {"BulkMaterial", "TreadMaterial", "PlyMaterial"}
        width = 7;
    otherwise
        width = 0;
end
end

function ranges = localExpectedRanges(key)
switch string(key)
    case "Geometry"
        ranges = [-1 1; -1 1; -1 1];
    case "InnerGeometryOverride"
        ranges = [-1 1; -1 1];
    case "PlyParams"
        ranges = [-360 360; 0 1; -10 10];
    case "RingAndRim"
        ranges = [-inf inf; -inf inf];
    case {"BulkMaterial", "TreadMaterial", "PlyMaterial"}
        ranges = [
            100 1000
            100 20000
            1000 1e13
            -1 1
            0 10
            50 10000
            0 100
        ];
    otherwise
        ranges = nan(0, 2);
end
end

function score = localRangeScore(value, range)
if any(isnan(range)) || isinf(range(1)) || isinf(range(2))
    score = 0;
elseif value >= range(1) && value <= range(2)
    score = 0;
else
    score = 1000 + min(abs(value - range(1)), abs(value - range(2)));
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
