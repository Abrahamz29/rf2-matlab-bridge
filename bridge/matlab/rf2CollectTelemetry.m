function run = rf2CollectTelemetry(seconds, hz, source)
%RF2COLLECTTELEMETRY Capture live rFactor 2 telemetry into MATLAB arrays.
if nargin < 1 || isempty(seconds)
    seconds = 60;
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
samples = max(1, ceil(seconds * hz));
wheelNames = ["frontLeft", "frontRight", "rearLeft", "rearRight"];

run = struct();
run.meta = struct("seconds", seconds, "hz", hz, "source", string(source), "created", datetime("now"));
run.wheelNames = wheelNames;
run.time = nan(samples, 1);
run.speedKph = nan(samples, 1);
run.throttle = nan(samples, 1);
run.brake = nan(samples, 1);
run.steering = nan(samples, 1);
run.gear = nan(samples, 1);
run.rpm = nan(samples, 1);
run.latG = nan(samples, 1);
run.longG = nan(samples, 1);
run.yawRate = nan(samples, 1);

wheelFields = ["tireLoad", "gripFract", "pressure", "wear", ...
    "surfaceTempC", "carcassTempC", "innerTempC", "brakeTempC", ...
    "rideHeight", "lateralForce", "longitudinalForce", ...
    "longSlipProxy", "latSlipProxy"];
for field = wheelFields
    run.(field) = nan(samples, 4);
end

t0 = tic;
for index = 1:samples
    loopStart = tic;
    data = client.snapshot();
    dynamics = client.playerDynamics(data);
    telemetry = client.playerTelemetry(data);

    run.time(index) = toc(t0);
    if isfield(dynamics, "speed_kph")
        run.speedKph(index) = dynamics.speed_kph;
    end
    if isfield(telemetry, "mUnfilteredThrottle")
        run.throttle(index) = telemetry.mUnfilteredThrottle;
    end
    if isfield(telemetry, "mUnfilteredBrake")
        run.brake(index) = telemetry.mUnfilteredBrake;
    end
    if isfield(telemetry, "mUnfilteredSteering")
        run.steering(index) = telemetry.mUnfilteredSteering;
    end
    if isfield(telemetry, "mGear")
        run.gear(index) = telemetry.mGear;
    end
    if isfield(telemetry, "mEngineRPM")
        run.rpm(index) = telemetry.mEngineRPM;
    end
    if isfield(telemetry, "mLocalAccel")
        run.latG(index) = telemetry.mLocalAccel.x / 9.80665;
        run.longG(index) = telemetry.mLocalAccel.z / 9.80665;
    end
    if isfield(telemetry, "mLocalRot")
        run.yawRate(index) = telemetry.mLocalRot.y;
    end

    if isfield(dynamics, "wheels")
        wheels = dynamics.wheels;
        for wheelIndex = 1:min(4, numel(wheels))
            wheel = wheels(wheelIndex);
            run.tireLoad(index, wheelIndex) = getfieldOrNaN(wheel, "mTireLoad");
            run.gripFract(index, wheelIndex) = getfieldOrNaN(wheel, "mGripFract");
            run.pressure(index, wheelIndex) = getfieldOrNaN(wheel, "mPressure");
            run.wear(index, wheelIndex) = getfieldOrNaN(wheel, "mWear");
            run.carcassTempC(index, wheelIndex) = kelvinToC(getfieldOrNaN(wheel, "mTireCarcassTemperature"));
            run.brakeTempC(index, wheelIndex) = getfieldOrNaN(wheel, "mBrakeTemp");
            run.rideHeight(index, wheelIndex) = getfieldOrNaN(wheel, "mRideHeight");
            run.lateralForce(index, wheelIndex) = getfieldOrNaN(wheel, "mLateralForce");
            run.longitudinalForce(index, wheelIndex) = getfieldOrNaN(wheel, "mLongitudinalForce");

            if isfield(wheel, "mTemperature")
                run.surfaceTempC(index, wheelIndex) = mean(double(wheel.mTemperature), "omitnan") - 273.15;
            end
            if isfield(wheel, "mTireInnerLayerTemperature")
                run.innerTempC(index, wheelIndex) = mean(double(wheel.mTireInnerLayerTemperature), "omitnan") - 273.15;
            end

            patchLong = getfieldOrNaN(wheel, "mLongitudinalPatchVel");
            groundLong = getfieldOrNaN(wheel, "mLongitudinalGroundVel");
            run.longSlipProxy(index, wheelIndex) = patchLong - groundLong;

            patchLat = getfieldOrNaN(wheel, "mLateralPatchVel");
            groundLat = getfieldOrNaN(wheel, "mLateralGroundVel");
            run.latSlipProxy(index, wheelIndex) = patchLat - groundLat;
        end
    end

    pause(max(0, 1 / hz - toc(loopStart)));
end
end

function value = getfieldOrNaN(s, fieldName)
if isfield(s, fieldName)
    value = double(s.(fieldName));
else
    value = nan;
end
end

function value = kelvinToC(value)
if ~isnan(value)
    value = value - 273.15;
end
end
