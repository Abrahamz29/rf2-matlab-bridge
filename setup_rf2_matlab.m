function status = setup_rf2_matlab()
%SETUP_RF2_MATLAB Add this project's MATLAB bridge to the path and check rF2.
projectRoot = fileparts(mfilename("fullpath"));
addpath(fullfile(projectRoot, "bridge", "matlab"));
addpath(fullfile(projectRoot, "tyres", "matlab"));
addpath(fullfile(projectRoot, "tracks", "blacklake", "matlab"));
client = RF2Client(projectRoot);
status = client.status();
disp(status);
end
