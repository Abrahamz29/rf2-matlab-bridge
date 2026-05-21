function fig = rf2PlotTyreBenchSweep(results)
%RF2PLOTTYREBENCHSWEEP Plot virtual tyre bench slip-angle sweep results.
%
% Required input columns:
%   slip_angle_deg
%   lateral_force_n, fy_n, or Fy_N
%
% Recommended input columns:
%   actual_vertical_load_n or target_vertical_load_n
%   longitudinal_force_n or fx_n
%   aligning_torque_nm or mz_nm
if nargin < 1 || isempty(results)
    results = fullfile("scenarios", "tyre", "slip_angle_5000N_minus12_to_12deg_results_template.csv");
end

if istable(results)
    T = results;
else
    T = readtable(results);
end

angleCol = localFindColumn(T, ["slip_angle_deg", "SlipAngleDeg", "alpha_deg", "AlphaDeg"]);
fyCol = localFindColumn(T, ["lateral_force_n", "fy_n", "Fy_N", "fy", "Fy"]);
fzCol = localFindColumn(T, ["actual_vertical_load_n", "vertical_load_n", "fz_n", "Fz_N", "target_vertical_load_n"]);
fxCol = localFindColumn(T, ["longitudinal_force_n", "fx_n", "Fx_N", "fx", "Fx"]);
mzCol = localFindColumn(T, ["aligning_torque_nm", "mz_nm", "Mz_Nm", "mz", "Mz"]);
muYCol = localFindColumn(T, ["mu_y", "muy", "MuY"]);

alpha = localNumeric(T.(angleCol));
fy = localNumeric(T.(fyCol));
fz = localNumeric(T.(fzCol));
if all(isnan(fz))
    targetFzCol = localFindColumn(T, "target_vertical_load_n");
    if ~isempty(targetFzCol)
        fzCol = targetFzCol;
        fz = localNumeric(T.(fzCol));
    end
end

if ~isempty(muYCol)
    muY = localNumeric(T.(muYCol));
else
    muY = fy ./ fz;
end

[alpha, order] = sort(alpha);
fy = fy(order);
fz = fz(order);
muY = muY(order);

fig = figure("Name", "Tyre Bench Slip Angle Sweep", "Color", "w");
layout = tiledlayout(fig, 2, 2, "TileSpacing", "compact", "Padding", "compact");

nexttile(layout);
plot(alpha, fy, "o-", "LineWidth", 1.2);
grid on;
xlabel("Slip angle deg");
ylabel("Lateral force N");
title("Fy vs Slip Angle");

nexttile(layout);
plot(alpha, muY, "o-", "LineWidth", 1.2);
grid on;
xlabel("Slip angle deg");
ylabel("mu_y");
title("Lateral Friction");

nexttile(layout);
plot(alpha, fz, "o-", "LineWidth", 1.2);
grid on;
xlabel("Slip angle deg");
ylabel("Vertical load N");
title("Fz Check");

nexttile(layout);
if ~isempty(mzCol)
    mz = localNumeric(T.(mzCol));
    plot(alpha, mz(order), "o-", "LineWidth", 1.2);
    ylabel("Aligning torque Nm");
    title("Mz vs Slip Angle");
elseif ~isempty(fxCol)
    fx = localNumeric(T.(fxCol));
    plot(alpha, fx(order), "o-", "LineWidth", 1.2);
    ylabel("Longitudinal force N");
    title("Fx Cross-Coupling");
else
    plot(alpha, zeros(size(alpha)), "Color", [0.65 0.65 0.65]);
    ylabel("No optional channel");
    title("Optional Force Channel");
end
grid on;
xlabel("Slip angle deg");

title(layout, "Tyre Bench Sweep");
end

function values = localNumeric(values)
if isnumeric(values)
    values = double(values);
elseif iscell(values) || isstring(values) || ischar(values) || iscategorical(values)
    values = str2double(string(values));
else
    values = double(values);
end
end

function name = localFindColumn(T, candidates)
names = string(T.Properties.VariableNames);
name = "";
for candidate = candidates
    match = find(strcmpi(names, candidate), 1);
    if ~isempty(match)
        name = T.Properties.VariableNames{match};
        return
    end
end

required = ["slip_angle_deg", "lateral_force_n", "actual_vertical_load_n", "target_vertical_load_n"];
if any(strcmpi(candidates(1), required))
    error("Missing required result column. Expected one of: %s", strjoin(candidates, ", "));
end
end
