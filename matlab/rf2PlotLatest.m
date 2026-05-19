function run = rf2PlotLatest(seconds, hz, source)
%RF2PLOTLATEST Capture a short run and open the telemetry overview plot.
if nargin < 1 || isempty(seconds)
    seconds = 60;
end
if nargin < 2 || isempty(hz)
    hz = 20;
end
if nargin < 3 || isempty(source)
    source = "rf2";
end

run = rf2CollectTelemetry(seconds, hz, source);
rf2PlotTelemetry(run);
end
