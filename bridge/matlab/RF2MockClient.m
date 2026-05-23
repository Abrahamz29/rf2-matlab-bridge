classdef RF2MockClient < handle
    %RF2MockClient Synthetic rFactor 2 data source for plot development.

    properties (Access = private)
        T0
    end

    methods
        function obj = RF2MockClient()
            obj.T0 = tic;
        end

        function data = snapshot(obj, varargin) %#ok<INUSD>
            t = toc(obj.T0);
            wheelNames = ["frontLeft", "frontRight", "rearLeft", "rearRight"];

            speedKph = 145 + 85 * sin(0.11 * t) + 18 * sin(0.73 * t);
            speedKph = max(0, speedKph);
            throttle = min(1, max(0, 0.55 + 0.45 * sin(0.19 * t + 0.7)));
            brake = min(1, max(0, 0.75 * sin(0.31 * t - 1.4)));
            steering = 0.38 * sin(0.58 * t) + 0.08 * sin(2.3 * t);
            latG = 1.25 * sin(0.58 * t);
            longG = 0.45 * throttle - 1.15 * brake + 0.08 * sin(1.7 * t);

            baseLoad = 3600 + 750 * longG;
            latTransfer = 950 * latG;
            load = [
                baseLoad - latTransfer, ...
                baseLoad + latTransfer, ...
                baseLoad * 1.12 - latTransfer * 0.8, ...
                baseLoad * 1.12 + latTransfer * 0.8
            ];
            load = max(load, 400);

            wheels = repmat(struct(), 4, 1);
            for wheelIndex = 1:4
                phase = wheelIndex * 0.8;
                wheels(wheelIndex).mTireLoad = load(wheelIndex);
                wheels(wheelIndex).mGripFract = min(1, max(0, 0.18 + 0.35 * abs(latG) + 0.2 * brake + 0.03 * sin(t + phase)));
                wheels(wheelIndex).mPressure = 165 + 4 * sin(0.04 * t + phase) + 0.002 * load(wheelIndex);
                wheels(wheelIndex).mWear = min(1, 0.02 + 0.00004 * t + 0.002 * wheelIndex);
                wheels(wheelIndex).mTemperature = 273.15 + [78, 82, 80] + 5 * sin(0.08 * t + phase);
                wheels(wheelIndex).mTireCarcassTemperature = 273.15 + 72 + 3 * sin(0.05 * t + phase);
                wheels(wheelIndex).mTireInnerLayerTemperature = 273.15 + [74, 76, 75] + 2 * sin(0.06 * t + phase);
                wheels(wheelIndex).mBrakeTemp = 180 + 420 * brake + 20 * sin(0.2 * t + phase);
                wheels(wheelIndex).mRideHeight = 0.055 + 0.004 * sin(0.4 * t + phase);
                wheels(wheelIndex).mLateralForce = load(wheelIndex) * 0.75 * latG;
                wheels(wheelIndex).mLongitudinalForce = load(wheelIndex) * (0.45 * throttle - 0.75 * brake);
                wheels(wheelIndex).mLongitudinalPatchVel = speedKph / 3.6 + 0.8 * throttle - 1.2 * brake;
                wheels(wheelIndex).mLongitudinalGroundVel = speedKph / 3.6;
                wheels(wheelIndex).mLateralPatchVel = 0.4 * latG;
                wheels(wheelIndex).mLateralGroundVel = 0.2 * latG;
            end

            telemetry = struct();
            telemetry.mElapsedTime = t;
            telemetry.mVehicleName = "Mock Vehicle";
            telemetry.mTrackName = "Mock Track";
            telemetry.mLocalVel = struct("x", 0, "y", 0, "z", speedKph / 3.6);
            telemetry.mLocalAccel = struct("x", latG * 9.80665, "y", 0, "z", longG * 9.80665);
            telemetry.mLocalRot = struct("x", 0, "y", 0.45 * sin(0.58 * t), "z", 0);
            telemetry.mLocalRotAccel = struct("x", 0, "y", 0.25 * sin(0.93 * t), "z", 0);
            telemetry.mGear = max(1, min(6, floor(speedKph / 45) + 1));
            telemetry.mEngineRPM = 2500 + 5200 * mod(speedKph / 95, 1);
            telemetry.mUnfilteredThrottle = throttle;
            telemetry.mUnfilteredBrake = brake;
            telemetry.mUnfilteredSteering = steering;
            telemetry.mWheels = wheels;

            data = struct();
            data.meta = struct("connected", true, "pluginVersion", "mock", "source", "mock");
            data.telemetry = struct("mNumVehicles", 1, "mVehicles", telemetry);
            data.convenience = struct();
            data.convenience.wheelOrder = wheelNames;
            data.convenience.playerIndex = 1;
            data.convenience.playerTelemetry = telemetry;
            data.convenience.playerDynamics = struct( ...
                "speed_mps", speedKph / 3.6, ...
                "speed_kph", speedKph, ...
                "localAcceleration", telemetry.mLocalAccel, ...
                "localRotation", telemetry.mLocalRot, ...
                "localRotationAcceleration", telemetry.mLocalRotAccel, ...
                "wheels", wheels);
        end

        function data = status(~)
            data = struct("connected", true, "pluginVersion", "mock", "availableBuffers", "mock");
        end

        function telemetry = playerTelemetry(~, data)
            telemetry = data.convenience.playerTelemetry;
        end

        function dynamics = playerDynamics(~, data)
            dynamics = data.convenience.playerDynamics;
        end
    end
end
