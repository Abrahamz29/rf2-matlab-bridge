function varargout = tyre_designer(varargin)
%TYRE_DESIGNER Start the standalone rFactor 2 tyre designer UI.
appPath = fileparts(mfilename("fullpath"));
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
