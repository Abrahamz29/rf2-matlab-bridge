function info = rf2GetCurrentTrack()
%RF2GETCURRENTTRACK Return current loaded track/session information from rF2.
client = RF2Client();
data = client.snapshot();

info = struct();
info.trackName = "";
info.sceneDescription = "";
info.controlMode = NaN;
info.speed_kph = NaN;
info.connected = false;

if isfield(data, "meta") && isfield(data.meta, "connected")
    info.connected = logical(data.meta.connected);
end

if isfield(data, "convenience")
    if isfield(data.convenience, "playerScoring")
        scoring = data.convenience.playerScoring;
        if isfield(scoring, "mTrackName")
            info.trackName = string(scoring.mTrackName);
        end
        if isfield(scoring, "mControl")
            info.controlMode = double(scoring.mControl);
        end
    end
    if isfield(data.convenience, "playerDynamics")
        dynamics = data.convenience.playerDynamics;
        if isfield(dynamics, "speed_kph")
            info.speed_kph = double(dynamics.speed_kph);
        end
    end
end

if isfield(data, "scoring") && isfield(data.scoring, "mScoringInfo")
    scoringInfo = data.scoring.mScoringInfo;
    if strlength(info.trackName) == 0 && isfield(scoringInfo, "mTrackName")
        info.trackName = string(scoringInfo.mTrackName);
    end
end

playerPath = "C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\UserData\player\player.JSON";
if isfile(playerPath)
    try
        playerData = jsondecode(localReadUtf8Text(playerPath));
        if isfield(playerData, "SCENE") && isfield(playerData.SCENE, "Scene Description")
            info.sceneDescription = string(playerData.SCENE.("Scene Description"));
        end
    catch
        info.sceneDescription = "";
    end
end
end

function text = localReadUtf8Text(pathStr)
fid = fopen(pathStr, "r", "n", "UTF-8");
assert(fid >= 0, "Could not open %s", pathStr);
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
raw = fread(fid, Inf, "*char")';
text = string(raw);
end
