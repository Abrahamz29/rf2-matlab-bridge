function varargout = rf2TgmGeneratorApp(varargin)
%RF2TGMGENERATORAPP Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGeneratorAppImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGeneratorAppImpl(varargin{:});
end
end