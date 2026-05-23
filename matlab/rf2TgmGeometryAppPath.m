function appPath = rf2TgmGeometryAppPath()
%RF2TGMGEOMETRYAPPPATH Add the standalone TGM Geometry app folder.
root = fileparts(mfilename("fullpath"));
appPath = fullfile(root, "apps", "tgm_geometry");
if ~isfolder(appPath)
    error("rf2TgmGeometryAppPath:MissingAppFolder", "TGM Geometry app folder not found: %s", appPath);
end

pathText = pathsep + string(path) + pathsep;
appPathText = pathsep + string(appPath) + pathsep;
if ~contains(pathText, appPathText)
    addpath(appPath);
end
end
