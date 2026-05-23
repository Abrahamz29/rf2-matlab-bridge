function varargout = startTgmGeneratorApp(varargin)
%STARTTGMGENERATORAPP Launch the TGM Generator app from this app folder.
appPath = fileparts(mfilename("fullpath"));
pathText = pathsep + string(path) + pathsep;
appPathText = pathsep + string(appPath) + pathsep;
if ~contains(pathText, appPathText)
    addpath(appPath);
end
if nargout == 0
    rf2TgmGeneratorAppImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGeneratorAppImpl(varargin{:});
end
end