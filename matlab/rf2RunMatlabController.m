function run = rf2RunMatlabController(controllerFcn, durationSeconds, hz, options)
%RF2RUNMATLABCONTROLLER Closed-loop rFactor 2 control from MATLAB.
if nargin < 1 || isempty(controllerFcn)
    controllerFcn = @rf2BlackLakeExampleController;
end
if nargin < 2 || isempty(durationSeconds)
    durationSeconds = 30;
end
if nargin < 3 || isempty(hz)
    hz = 20;
end
if nargin < 4 || isempty(options)
    options = struct();
end

if ~isfield(options, "focusWindow"), options.focusWindow = true; end
if ~isfield(options, "ensurePlayerControl"), options.ensurePlayerControl = true; end
if ~isfield(options, "logSnapshots"), options.logSnapshots = false; end

client = RF2Client();
actuator = RF2Actuator();

if options.focusWindow
    actuator.focusWindow();
end
if options.ensurePlayerControl
    actuator.ensurePlayerControl();
end

sampleCount = max(1, ceil(durationSeconds * hz));
run = struct();
run.t = zeros(sampleCount, 1);
run.speed_kph = nan(sampleCount, 1);
run.throttleCmd = zeros(sampleCount, 1);
run.brakeCmd = zeros(sampleCount, 1);
run.steerCmd = zeros(sampleCount, 1);
run.controlMode = nan(sampleCount, 1);
if options.logSnapshots
    run.snapshots = cell(sampleCount, 1);
end

t0 = tic;
cleanupObj = onCleanup(@() localCleanup(actuator));

for idx = 1:sampleCount
    stepStart = tic;
    data = client.snapshot();
    state = localStateView(data, toc(t0), idx, hz);
    cmd = controllerFcn(state);
    cmd = localNormalizeCommand(cmd);

    actuator.setCommands(cmd.throttle, cmd.brake, cmd.steer);

    run.t(idx) = state.t;
    run.speed_kph(idx) = state.speed_kph;
    run.throttleCmd(idx) = cmd.throttle;
    run.brakeCmd(idx) = cmd.brake;
    run.steerCmd(idx) = cmd.steer;
    run.controlMode(idx) = state.controlMode;
    if options.logSnapshots
        run.snapshots{idx} = data;
    end

    remaining = (1 / hz) - toc(stepStart);
    if remaining > 0
        pause(remaining);
    end
end
end

function state = localStateView(data, elapsedTime, sampleIndex, hz)
dynamics = struct();
telemetry = struct();
scoring = struct();
if isfield(data, "convenience")
    if isfield(data.convenience, "playerDynamics"), dynamics = data.convenience.playerDynamics; end
    if isfield(data.convenience, "playerTelemetry"), telemetry = data.convenience.playerTelemetry; end
    if isfield(data.convenience, "playerScoring"), scoring = data.convenience.playerScoring; end
end

state = struct();
state.t = elapsedTime;
state.sampleIndex = sampleIndex;
state.hz = hz;
state.data = data;
state.dynamics = dynamics;
state.telemetry = telemetry;
state.scoring = scoring;
state.speed_kph = localGetField(dynamics, "speed_kph", NaN);
state.lat_g = localNestedAccel(telemetry, "x");
state.long_g = localNestedAccel(telemetry, "z");
state.controlMode = localGetField(scoring, "mControl", NaN);
state.trackName = localGetField(scoring, "mTrackName", "");
end

function value = localNestedAccel(telemetry, axisName)
value = NaN;
if isfield(telemetry, "mLocalAccel")
    accel = telemetry.mLocalAccel;
    if isfield(accel, axisName)
        value = accel.(axisName) / 9.80665;
    end
end
end

function value = localGetField(s, fieldName, defaultValue)
value = defaultValue;
if isstruct(s) && isfield(s, fieldName)
    value = s.(fieldName);
end
end

function cmd = localNormalizeCommand(cmd)
if ~isstruct(cmd)
    error("Controller function must return a struct with throttle, brake, steer.");
end
if ~isfield(cmd, "throttle"), cmd.throttle = 0; end
if ~isfield(cmd, "brake"), cmd.brake = 0; end
if ~isfield(cmd, "steer"), cmd.steer = 0; end
cmd.throttle = max(0, min(1, double(cmd.throttle)));
cmd.brake = max(0, min(1, double(cmd.brake)));
cmd.steer = max(-1, min(1, double(cmd.steer)));
end

function localCleanup(actuator)
actuator.neutral();
pause(0.1);
actuator.releaseAll();
end
