function rf2LivePlotExample(seconds, hz)
%RF2LIVEPLOTEXAMPLE Plot live player speed and tire load from rFactor 2.
if nargin < 1 || isempty(seconds)
    seconds = 60;
end
if nargin < 2 || isempty(hz)
    hz = 20;
end

client = RF2Client();
samples = max(1, ceil(seconds * hz));
timeAxis = nan(samples, 1);
speedKph = nan(samples, 1);
tireLoad = nan(samples, 4);
wheelNames = ["frontLeft", "frontRight", "rearLeft", "rearRight"];

figure("Name", "rFactor 2 MATLAB Live Telemetry");
if exist("rf2MoveFigureToMonitor", "file") == 2
    rf2MoveFigureToMonitor(gcf, 2);
end
tiledlayout(2, 1);
speedAx = nexttile;
speedLine = plot(speedAx, timeAxis, speedKph);
grid(speedAx, "on");
ylabel(speedAx, "Speed km/h");

loadAx = nexttile;
loadLines = plot(loadAx, timeAxis, tireLoad);
grid(loadAx, "on");
xlabel(loadAx, "s");
ylabel(loadAx, "Tire load N");
legend(loadAx, wheelNames, "Location", "best");

t0 = tic;
for index = 1:samples
    loopStart = tic;
    data = client.snapshot();
    dynamics = client.playerDynamics(data);
    timeAxis(index) = toc(t0);

    if isfield(dynamics, "speed_kph")
        speedKph(index) = dynamics.speed_kph;
    end
    if isfield(dynamics, "wheels")
        wheels = dynamics.wheels;
        for wheelIndex = 1:min(4, numel(wheels))
            tireLoad(index, wheelIndex) = wheels(wheelIndex).mTireLoad;
        end
    end

    speedLine.XData = timeAxis;
    speedLine.YData = speedKph;
    for wheelIndex = 1:4
        loadLines(wheelIndex).XData = timeAxis;
        loadLines(wheelIndex).YData = tireLoad(:, wheelIndex);
    end
    drawnow limitrate;

    pause(max(0, 1 / hz - toc(loopStart)));
end
end
