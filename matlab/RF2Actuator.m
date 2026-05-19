classdef RF2Actuator < handle
    %RF2ACTUATOR MATLAB wrapper around the Python keyboard actuator bridge.
    properties (Access = private)
        Module
        Impl
    end

    methods
        function obj = RF2Actuator()
            projectRoot = fileparts(fileparts(mfilename("fullpath")));
            pythonPath = fullfile(projectRoot, "python");
            vendorPath = fullfile(projectRoot, "vendor", "pyRfactor2SharedMemory");
            if count(py.sys.path, pythonPath) == 0
                insert(py.sys.path, int32(0), pythonPath);
            end
            if count(py.sys.path, vendorPath) == 0
                insert(py.sys.path, int32(0), vendorPath);
            end
            py.importlib.invalidate_caches();
            obj.Module = py.importlib.import_module("rf2_control");
            obj.Module = py.importlib.reload(obj.Module);
            obj.Impl = obj.Module.RF2Actuator();
        end

        function tf = focusWindow(obj)
            tf = logical(obj.Impl.focus_window());
        end

        function ensurePlayerControl(obj)
            obj.Impl.ensure_player_control();
        end

        function ensureAIControl(obj)
            obj.Impl.ensure_ai_control();
        end

        function setCommands(obj, throttle, brake, steer)
            obj.Impl.set_commands(throttle, brake, steer);
        end

        function neutral(obj)
            obj.Impl.neutral();
        end

        function releaseAll(obj)
            obj.Impl.release_all();
        end
    end
end
