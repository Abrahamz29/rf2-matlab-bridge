function fig = rf2PlotTelemetry(run)
%RF2PLOTTELEMETRY Plot setup-relevant rFactor 2 telemetry captured in MATLAB.
if nargin < 1 || isempty(run)
    run = rf2CollectTelemetry(60, 20);
end

wheelNames = run.wheelNames;
fig = figure("Name", "rFactor 2 Telemetry Overview", "Color", "w");
if exist("rf2MoveFigureToMonitor", "file") == 2
    rf2MoveFigureToMonitor(fig, 2);
end
layout = tiledlayout(fig, 3, 2, "TileSpacing", "compact", "Padding", "compact");

nexttile(layout);
yyaxis left;
plot(run.time, run.speedKph, "LineWidth", 1.2);
ylabel("Speed km/h");
yyaxis right;
plot(run.time, run.rpm, "LineWidth", 1.0);
ylabel("RPM");
grid on;
title("Speed and Engine");

nexttile(layout);
plot(run.time, [run.throttle, run.brake, run.steering], "LineWidth", 1.0);
ylim([-1.05 1.05]);
grid on;
title("Inputs");
ylabel("0..1 / steering -1..1");
legend(["Throttle", "Brake", "Steering"], "Location", "best");

nexttile(layout);
plot(run.time, [run.longG, run.latG, run.yawRate], "LineWidth", 1.0);
grid on;
title("Vehicle Dynamics");
ylabel("g / rad s^{-1}");
legend(["Long G", "Lat G", "Yaw rate"], "Location", "best");

nexttile(layout);
plot(run.time, run.tireLoad, "LineWidth", 1.0);
grid on;
title("Tire Load");
ylabel("N");
legend(wheelNames, "Location", "best");

nexttile(layout);
plot(run.time, run.surfaceTempC, "LineWidth", 1.0);
hold on;
plot(run.time, run.carcassTempC, "--", "LineWidth", 0.9);
hold off;
grid on;
title("Tire Temperatures");
ylabel("deg C");
legend([wheelNames + " surface", wheelNames + " carcass"], "Location", "bestoutside");

nexttile(layout);
yyaxis left;
plot(run.time, run.pressure, "LineWidth", 1.0);
ylabel("kPa");
yyaxis right;
plot(run.time, run.gripFract, "--", "LineWidth", 0.9);
ylabel("Grip fraction");
grid on;
title("Pressure and Sliding");
legend([wheelNames + " pressure", wheelNames + " grip"], "Location", "bestoutside");

xlabel(layout, "Time s");
end
