function run = rf2RunBlackLakeController(durationSeconds, hz, config, options)
%RF2RUNBLACKLAKECONTROLLER Run a MATLAB-only controller on BlackLake.
if nargin < 1 || isempty(durationSeconds)
    durationSeconds = 30;
end
if nargin < 2 || isempty(hz)
    hz = 20;
end
if nargin < 3 || isempty(config)
    config = struct();
end
if nargin < 4 || isempty(options)
    options = struct();
end

if ~isfield(options, "requiredTrackTokens")
    options.requiredTrackTokens = ["black", "lake"];
end
if ~isfield(options, "focusWindow")
    options.focusWindow = true;
end
if ~isfield(options, "ensurePlayerControl")
    options.ensurePlayerControl = true;
end
if ~isfield(options, "logSnapshots")
    options.logSnapshots = false;
end

trackInfo = rf2GetCurrentTrack();
if ~trackInfo.connected
    error("rFactor 2 shared memory is not connected.");
end

actual = lower(strcat(trackInfo.trackName, " ", trackInfo.sceneDescription));
for token = options.requiredTrackTokens
    if ~contains(actual, lower(string(token)))
        error("BlackLake is not loaded. Current track/session: trackName='%s', sceneDescription='%s'.", ...
            trackInfo.trackName, trackInfo.sceneDescription);
    end
end

controllerFcn = rf2MakeBlackLakeController(config);
run = rf2RunMatlabController(controllerFcn, durationSeconds, hz, options);
run.trackInfo = trackInfo;
run.controllerConfig = config;
end
