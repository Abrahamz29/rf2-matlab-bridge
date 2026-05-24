function appPath = rf2TgmAppPath()
%RF2TGMAPPPATH Add the TGM Generator app folder to the MATLAB path.
matlabRoot = fileparts(fileparts(mfilename("fullpath")));
appPath = fullfile(matlabRoot, "apps", "tgm_generator");
if ~isfolder(appPath)
    error("rf2TgmAppPath:MissingAppFolder", "TGM app folder not found: %s", appPath);
end
pathText = pathsep + string(path) + pathsep;
appPathText = pathsep + string(appPath) + pathsep;
if ~contains(pathText, appPathText)
    addpath(appPath);
end
end
