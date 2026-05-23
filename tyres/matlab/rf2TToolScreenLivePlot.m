function samples = rf2TToolScreenLivePlot(durationSec, samplePeriodSec, varargin)
%RF2TTOOLSCREENLIVEPLOT Live-plot selected rF2 TTool screen values via OCR.
%
% samples = rf2TToolScreenLivePlot(300, 1)
% samples = rf2TToolScreenLivePlot(300, 1, "Roi", [1 45 340 820])
%
% The function reads visible TTool panel values from screenshots. It requires
% MATLAB's OCR function from Computer Vision Toolbox.

if nargin < 1 || isempty(durationSec)
    durationSec = inf;
end
if nargin < 2 || isempty(samplePeriodSec)
    samplePeriodSec = 1;
end

parser = inputParser;
parser.FunctionName = mfilename;
addParameter(parser, "Roi", [], @(x) isempty(x) || (isnumeric(x) && numel(x) == 4));
addParameter(parser, "ShowOcrText", false, @(x) islogical(x) || isnumeric(x));
addParameter(parser, "DryRun", false, @(x) islogical(x) || isnumeric(x));
parse(parser, varargin{:});

roi = parser.Results.Roi;
showOcrText = logical(parser.Results.ShowOcrText);
dryRun = logical(parser.Results.DryRun);

if dryRun
    samples = table();
    return;
end

if exist("ocr", "file") ~= 2
    error("rf2:TToolScreenLivePlot:MissingOCR", ...
        "MATLAB OCR function not found. Install/enable Computer Vision Toolbox or pass TTool results through CSV instead.");
end

robot = java.awt.Robot;
screenSize = java.awt.Toolkit.getDefaultToolkit().getScreenSize();

if isempty(roi)
    roi = [1 45 min(360, screenSize.width), min(820, screenSize.height - 44)];
end

fig = figure("Name", "rF2 TTool Screen Live Plot", "NumberTitle", "off");
tiledlayout(fig, 2, 1, "TileSpacing", "compact");

axIndex = nexttile;
idxLine = animatedline(axIndex, "Color", [0.15 0.35 0.85], "LineWidth", 1.2);
grid(axIndex, "on");
xlabel(axIndex, "Elapsed (s)");
ylabel(axIndex, "Realtime Test Index");

axForce = nexttile;
vLine = animatedline(axForce, "Color", [0.1 0.55 0.15], "LineWidth", 1.2, "DisplayName", "Vertical");
longLine = animatedline(axForce, "Color", [0.8 0.25 0.15], "LineWidth", 1.2, "DisplayName", "Long");
latLine = animatedline(axForce, "Color", [0.2 0.4 0.85], "LineWidth", 1.2, "DisplayName", "Lat");
grid(axForce, "on");
xlabel(axForce, "Elapsed (s)");
ylabel(axForce, "Force (N)");
legend(axForce, "Location", "best");

elapsed = [];
realtimeTestIndex = [];
verticalForceN = [];
longForceN = [];
latForceN = [];
aligningTorqueNm = [];

ticHandle = tic;
while ishandle(fig)
    t = toc(ticHandle);
    if isfinite(durationSec) && t > durationSec
        break;
    end

    img = localScreenCapture(robot, roi);
    text = ocr(img, "TextLayout", "Block").Text;

    idx = localReadValue(text, ["Realtime Test Index", "RealTime Test Index"]);
    fz = localReadValue(text, ["Vertical Force", "Vert Force"]);
    fx = localReadValue(text, ["Long Force", "Long Force (N)"]);
    fy = localReadValue(text, ["Lat Force", "Lateral Force"]);
    mz = localReadValue(text, ["Aligning Torque", "Aligning Torque (Nm)"]);

    elapsed(end + 1, 1) = t; %#ok<AGROW>
    realtimeTestIndex(end + 1, 1) = idx; %#ok<AGROW>
    verticalForceN(end + 1, 1) = fz; %#ok<AGROW>
    longForceN(end + 1, 1) = fx; %#ok<AGROW>
    latForceN(end + 1, 1) = fy; %#ok<AGROW>
    aligningTorqueNm(end + 1, 1) = mz; %#ok<AGROW>

    if ~isnan(idx)
        addpoints(idxLine, t, idx);
    end
    if ~isnan(fz)
        addpoints(vLine, t, fz);
    end
    if ~isnan(fx)
        addpoints(longLine, t, fx);
    end
    if ~isnan(fy)
        addpoints(latLine, t, fy);
    end

    title(axIndex, sprintf("Realtime Test Index: %s", localFmt(idx)));
    title(axForce, sprintf("Fz=%s N, Fx=%s N, Fy=%s N", localFmt(fz), localFmt(fx), localFmt(fy)));
    drawnow limitrate;

    if showOcrText
        fprintf("\n--- OCR %.1fs ---\n%s\n", t, text);
    end

    pause(samplePeriodSec);
end

samples = table(elapsed, realtimeTestIndex, verticalForceN, longForceN, ...
    latForceN, aligningTorqueNm);
end

function img = localScreenCapture(robot, roi)
x = max(0, round(roi(1)) - 1);
y = max(0, round(roi(2)) - 1);
w = max(1, round(roi(3)));
h = max(1, round(roi(4)));
rect = java.awt.Rectangle(x, y, w, h);
jimg = robot.createScreenCapture(rect);

tmp = [tempname, ".png"];
cleanup = onCleanup(@() localDeleteIfExists(tmp));
javax.imageio.ImageIO.write(jimg, char("png"), java.io.File(char(tmp)));
img = imread(tmp);
end

function value = localReadValue(text, labels)
value = NaN;
numberPattern = "([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)";
lines = regexp(string(text), "\r\n|\n|\r", "split");

for label = labels
    escaped = regexptranslate("escape", char(label));
    pattern = escaped + "[^\d\+\-]*" + numberPattern;
    token = regexp(char(text), char(pattern), "tokens", "once", "ignorecase");
    if ~isempty(token)
        value = str2double(token{1});
        return;
    end

    labelWords = lower(split(label));
    for i = 1:numel(lines)
        line = lower(lines(i));
        if all(contains(line, labelWords))
            token = regexp(char(lines(i)), char(numberPattern), "tokens", "once");
            if ~isempty(token)
                value = str2double(token{1});
                return;
            end
        end
    end
end
end

function out = localFmt(value)
if isnan(value)
    out = "n/a";
else
    out = string(sprintf("%.4g", value));
end
end

function localDeleteIfExists(path)
if exist(path, "file") == 2
    delete(path);
end
end
