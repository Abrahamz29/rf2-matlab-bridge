function status = setup_rf2_matlab()
%SETUP_RF2_MATLAB Add this project's tyre MATLAB tools to the path.
projectRoot = fileparts(mfilename("fullpath"));
addpath(fullfile(projectRoot, "tyres", "matlab", "functions"));
addpath(fullfile(projectRoot, "tyres", "matlab", "apps", "tgm_generator"));
addpath(fullfile(projectRoot, "tyres", "matlab", "apps", "tyre_designer"));
status = struct( ...
    "ok", true, ...
    "message", "MATLAB tyre model paths configured.", ...
    "projectRoot", string(projectRoot));
disp(status);
end
