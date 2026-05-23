function varargout = tyre_designer(varargin)
%TYRE_DESIGNER Start the standalone rFactor 2 tyre designer UI.
appPath = fullfile(fileparts(mfilename("fullpath")), "apps", "tyre_designer");
if ~isfolder(appPath)
    error("tyre_designer:MissingAppFolder", "Tyre designer app folder not found: %s", appPath);
end

pathText = pathsep + string(path) + pathsep;
appPathText = pathsep + string(appPath) + pathsep;
if ~contains(pathText, appPathText)
    addpath(appPath);
end

if nargout == 0
    tyre_designer_app(varargin{:});
else
    [varargout{1:nargout}] = tyre_designer_app(varargin{:});
end
end
