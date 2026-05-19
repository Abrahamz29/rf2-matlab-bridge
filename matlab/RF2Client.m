classdef RF2Client < handle
    %RF2Client MATLAB access to rFactor 2 shared-memory telemetry.

    properties (SetAccess = private)
        ProjectRoot
        Module
    end

    methods
        function obj = RF2Client(projectRoot)
            if nargin < 1 || strlength(string(projectRoot)) == 0
                projectRoot = fileparts(fileparts(mfilename("fullpath")));
            end

            obj.ProjectRoot = char(projectRoot);
            obj.addPythonPath(fullfile(obj.ProjectRoot, "python"));
            obj.addPythonPath(fullfile(obj.ProjectRoot, "vendor", "pyRfactor2SharedMemory"));

            py.importlib.invalidate_caches();
            obj.Module = py.importlib.import_module("rf2_matlab_bridge");
            obj.Module = py.importlib.reload(obj.Module);
        end

        function data = snapshot(obj, varargin)
            p = inputParser;
            addParameter(p, "Full", false, @(x) islogical(x) || isnumeric(x));
            addParameter(p, "IncludeExpansion", false, @(x) islogical(x) || isnumeric(x));
            parse(p, varargin{:});

            trim = ~logical(p.Results.Full);
            includeExpansion = logical(p.Results.IncludeExpansion);
            jsonText = char(obj.Module.snapshot_json(pyargs( ...
                "trim", trim, ...
                "include_expansion", includeExpansion)));
            data = jsondecode(jsonText);
        end

        function data = status(obj)
            data = jsondecode(char(obj.Module.status_json()));
        end

        function tf = isConnected(obj)
            data = obj.status();
            tf = isfield(data, "connected") && logical(data.connected);
        end

        function data = schema(obj)
            data = jsondecode(char(obj.Module.schema_json()));
        end

        function telemetry = playerTelemetry(obj, data)
            if nargin < 2
                data = obj.snapshot();
            end
            telemetry = struct();
            if isfield(data, "convenience") && isfield(data.convenience, "playerTelemetry")
                telemetry = data.convenience.playerTelemetry;
            end
        end

        function dynamics = playerDynamics(obj, data)
            if nargin < 2
                data = obj.snapshot();
            end
            dynamics = struct();
            if isfield(data, "convenience") && isfield(data.convenience, "playerDynamics")
                dynamics = data.convenience.playerDynamics;
            end
        end

        function T = vehicleTable(obj, data)
            if nargin < 2
                data = obj.snapshot();
            end
            if ~isfield(data, "telemetry") || ~isfield(data.telemetry, "mVehicles")
                T = table();
                return
            end
            T = struct2table(data.telemetry.mVehicles);
        end

        function T = wheelTable(obj, data)
            if nargin < 2
                data = obj.snapshot();
            end
            dynamics = obj.playerDynamics(data);
            if ~isfield(dynamics, "wheels")
                T = table();
                return
            end
            T = struct2table(dynamics.wheels);
            if isfield(data.convenience, "wheelOrder")
                wheelOrder = data.convenience.wheelOrder;
                if iscell(wheelOrder)
                    wheel = wheelOrder(:);
                else
                    wheel = cellstr(wheelOrder);
                end
                T.wheel = wheel(:);
                T = movevars(T, "wheel", "Before", 1);
            end
        end

        function result = logJsonl(obj, seconds, hz, outFile, full)
            if nargin < 2 || isempty(seconds)
                seconds = 10;
            end
            if nargin < 3 || isempty(hz)
                hz = 20;
            end
            if nargin < 4 || isempty(outFile)
                stamp = datestr(now, "yyyymmdd_HHMMSS");
                outFile = fullfile(obj.ProjectRoot, "logs", "rf2_" + string(stamp) + ".jsonl");
            end
            if nargin < 5
                full = false;
            end
            result = jsondecode(char(obj.Module.log_jsonl_json( ...
                char(outFile), double(seconds), double(hz), pyargs("full", logical(full)))));
        end
    end

    methods (Access = private)
        function addPythonPath(~, pathToAdd)
            pathToAdd = char(pathToAdd);
            py.sys.path().insert(int32(0), pathToAdd);
        end
    end
end
