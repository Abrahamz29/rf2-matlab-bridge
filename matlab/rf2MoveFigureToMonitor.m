function rf2MoveFigureToMonitor(fig, monitorIndex)
%RF2MOVEFIGURETOMONITOR Move a MATLAB figure to a selected monitor.
if nargin < 1 || isempty(fig)
    fig = gcf;
end
if nargin < 2 || isempty(monitorIndex)
    monitorIndex = 2;
end

monitors = get(0, "MonitorPositions");
monitorIndex = min(max(1, monitorIndex), size(monitors, 1));
pos = monitors(monitorIndex, :);

margin = 40;
fig.Units = "pixels";
fig.WindowState = "normal";
fig.Position = [
    pos(1) + margin, ...
    pos(2) + margin, ...
    max(600, pos(3) - 2 * margin), ...
    max(400, pos(4) - 2 * margin)
];
figure(fig);
end
