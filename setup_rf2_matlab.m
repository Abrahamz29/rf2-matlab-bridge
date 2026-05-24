function status = setup_rf2_matlab()
%SETUP_RF2_MATLAB Add this project's MATLAB bridge to the path and check rF2.
projectRoot = fileparts(mfilename("fullpath"));
addpath(fullfile(projectRoot, "bridge", "matlab"));
addpath(fullfile(projectRoot, "tyres", "matlab", "functions"));
addpath(fullfile(projectRoot, "tyres", "matlab", "apps", "tyre_designer"));
addpath(fullfile(projectRoot, "tracks", "blacklake", "matlab"));
try
    client = RF2Client(projectRoot);
    status = client.status();
catch exception
    status = struct( ...
        "ok", false, ...
        "message", "MATLAB paths configured; RF2Client status unavailable.", ...
        "error", string(exception.message));
    warning("setup_rf2_matlab:RF2ClientUnavailable", "%s", exception.message);
end
disp(status);
end
