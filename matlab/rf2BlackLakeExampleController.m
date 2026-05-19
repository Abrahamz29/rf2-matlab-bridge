function cmd = rf2BlackLakeExampleController(state)
%RF2BLACKLAKEEXAMPLECONTROLLER Simple MATLAB controller template for BlackLake.
%
% This is intentionally conservative: speed-hold with a scripted steer pulse.
% Replace this with your real regulator once BlackLake is installed.

targetSpeed = 80; % kph
speedError = targetSpeed - state.speed_kph;
throttle = 0.18 + 0.015 * speedError;
brake = 0.0;

if state.t < 3
    steer = 0.0;
elseif state.t < 4
    steer = -0.20;
elseif state.t < 6
    steer = 0.0;
elseif state.t < 7
    steer = 0.20;
else
    steer = 0.0;
end

if speedError < -10
    throttle = 0.0;
    brake = min(0.3, (-speedError) * 0.01);
end

cmd = struct( ...
    "throttle", max(0, min(1, throttle)), ...
    "brake", max(0, min(1, brake)), ...
    "steer", max(-1, min(1, steer)));
end
