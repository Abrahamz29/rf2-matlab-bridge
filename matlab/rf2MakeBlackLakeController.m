function controllerFcn = rf2MakeBlackLakeController(config)
%RF2MAKEBLACKLAKECONTROLLER Build a configurable BlackLake MATLAB controller.
if nargin < 1 || isempty(config)
    config = struct();
end

if ~isfield(config, "targetSpeedKph"), config.targetSpeedKph = 80; end
if ~isfield(config, "stepStartS"), config.stepStartS = 3.0; end
if ~isfield(config, "stepDurationS"), config.stepDurationS = 1.0; end
if ~isfield(config, "stepAmplitude"), config.stepAmplitude = -0.20; end
if ~isfield(config, "holdThrottleBias"), config.holdThrottleBias = 0.18; end
if ~isfield(config, "holdThrottleKp"), config.holdThrottleKp = 0.015; end
if ~isfield(config, "overspeedBrakeKp"), config.overspeedBrakeKp = 0.01; end
if ~isfield(config, "overspeedThresholdKph"), config.overspeedThresholdKph = 10; end

controllerFcn = @(state) localController(state, config);
end

function cmd = localController(state, config)
speedError = config.targetSpeedKph - state.speed_kph;
throttle = config.holdThrottleBias + config.holdThrottleKp * speedError;
brake = 0.0;
steer = 0.0;

if state.t >= config.stepStartS && state.t < (config.stepStartS + config.stepDurationS)
    steer = config.stepAmplitude;
end

if speedError < -config.overspeedThresholdKph
    throttle = 0.0;
    brake = min(0.3, (-speedError) * config.overspeedBrakeKp);
end

cmd = struct( ...
    "throttle", max(0, min(1, throttle)), ...
    "brake", max(0, min(1, brake)), ...
    "steer", max(-1, min(1, steer)));
end
