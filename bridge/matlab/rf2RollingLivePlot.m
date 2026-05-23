function rf2RollingLivePlot(windowSeconds, hz, source)
%RF2ROLLINGLIVEPLOT Continuously plot the last N seconds of live rF2 data.
if nargin < 1 || isempty(windowSeconds)
    windowSeconds = 15;
end
if nargin < 2 || isempty(hz)
    hz = 20;
end
if nargin < 3 || isempty(source)
    source = "rf2";
end

if strcmpi(string(source), "mock")
    client = RF2MockClient();
else
    client = RF2Client();
end
capacity = max(10, ceil(windowSeconds * hz));
wheelNames = ["frontLeft", "frontRight", "rearLeft", "rearRight"];

t = nan(capacity, 1);
speedKph = nan(capacity, 1);
latG = nan(capacity, 1);
longG = nan(capacity, 1);
throttle = nan(capacity, 1);
brake = nan(capacity, 1);
tireLoad = nan(capacity, 4);
gripFract = nan(capacity, 4);

fig = figure("Name", "rFactor 2 Rolling Live Telemetry (" + string(source) + ")", "Color", "w");
if exist("rf2MoveFigureToMonitor", "file") == 2
    rf2MoveFigureToMonitor(fig, 2);
end
layout = tiledlayout(fig, 3, 1, "TileSpacing", "compact", "Padding", "compact");

axSpeed = nexttile(layout);
yyaxis(axSpeed, "left");
speedLine = plot(axSpeed, t, speedKph, "LineWidth", 1.2);
ylabel(axSpeed, "Speed km/h");
yyaxis(axSpeed, "right");
inputLines = plot(axSpeed, t, [throttle, brake], "LineWidth", 1.0);
ylabel(axSpeed, "Input");
grid(axSpeed, "on");
title(axSpeed, "Speed, Throttle, Brake");
legend(axSpeed, ["Speed", "Throttle", "Brake"], "Location", "northwest");

axG = nexttile(layout);
gLines = plot(axG, t, [longG, latG], "LineWidth", 1.0);
grid(axG, "on");
ylabel(axG, "g");
title(axG, "Longitudinal and Lateral G");
legend(axG, ["Long G", "Lat G"], "Location", "northwest");

axTire = nexttile(layout);
yyaxis(axTire, "left");
loadLines = plot(axTire, t, tireLoad, "LineWidth", 1.0);
ylabel(axTire, "Tire load N");
yyaxis(axTire, "right");
gripLines = plot(axTire, t, gripFract, "--", "LineWidth", 0.9);
ylabel(axTire, "Grip fraction");
grid(axTire, "on");
xlabel(axTire, "Time s");
title(axTire, "Tire Load and Sliding");
legend(axTire, [wheelNames + " load", wheelNames + " grip"], "Location", "eastoutside");

t0 = tic;
sampleIndex = 0;
while isvalid(fig)
    loopStart = tic;
    sampleIndex = sampleIndex + 1;
    slot = mod(sampleIndex - 1, capacity) + 1;

    data = client.snapshot();
    dynamics = client.playerDynamics(data);
    telemetry = client.playerTelemetry(data);

    t(slot) = toc(t0);
    speedKph(slot) = valueOrNaN(dynamics, "speed_kph");
    throttle(slot) = valueOrNaN(telemetry, "mUnfilteredThrottle");
    brake(slot) = valueOrNaN(telemetry, "mUnfilteredBrake");

    if isfield(telemetry, "mLocalAccel")
        latG(slot) = telemetry.mLocalAccel.x / 9.80665;
        longG(slot) = telemetry.mLocalAccel.z / 9.80665;
    else
        latG(slot) = nan;
        longG(slot) = nan;
    end

    tireLoad(slot, :) = nan;
    gripFract(slot, :) = nan;
    if isfield(dynamics, "wheels")
        wheels = dynamics.wheels;
        for wheelIndex = 1:min(4, numel(wheels))
            tireLoad(slot, wheelIndex) = valueOrNaN(wheels(wheelIndex), "mTireLoad");
            gripFract(slot, wheelIndex) = valueOrNaN(wheels(wheelIndex), "mGripFract");
        end
    end

    valid = ~isnan(t);
    [plotT, order] = sort(t(valid));
    plotSpeed = speedKph(valid);
    plotThrottle = throttle(valid);
    plotBrake = brake(valid);
    plotLongG = longG(valid);
    plotLatG = latG(valid);
    plotLoad = tireLoad(valid, :);
    plotGrip = gripFract(valid, :);

    plotSpeed = plotSpeed(order);
    plotThrottle = plotThrottle(order);
    plotBrake = plotBrake(order);
    plotLongG = plotLongG(order);
    plotLatG = plotLatG(order);
    plotLoad = plotLoad(order, :);
    plotGrip = plotGrip(order, :);

    latestTime = max(plotT, [], "omitnan");
    xMin = max(0, latestTime - windowSeconds);
    xMax = max(windowSeconds, latestTime);

    speedLine.XData = plotT;
    speedLine.YData = plotSpeed;
    inputLines(1).XData = plotT;
    inputLines(1).YData = plotThrottle;
    inputLines(2).XData = plotT;
    inputLines(2).YData = plotBrake;
    xlim(axSpeed, [xMin xMax]);

    gLines(1).XData = plotT;
    gLines(1).YData = plotLongG;
    gLines(2).XData = plotT;
    gLines(2).YData = plotLatG;
    xlim(axG, [xMin xMax]);

    for wheelIndex = 1:4
        loadLines(wheelIndex).XData = plotT;
        loadLines(wheelIndex).YData = plotLoad(:, wheelIndex);
        gripLines(wheelIndex).XData = plotT;
        gripLines(wheelIndex).YData = plotGrip(:, wheelIndex);
    end
    xlim(axTire, [xMin xMax]);

    drawnow limitrate;
    pause(max(0, 1 / hz - toc(loopStart)));
end
end

function value = valueOrNaN(s, fieldName)
if isstruct(s) && isfield(s, fieldName)
    value = double(s.(fieldName));
else
    value = nan;
end
end
