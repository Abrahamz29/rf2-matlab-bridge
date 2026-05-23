function varargout = rf2TgmGeneratorSmoke(varargin)
%RF2TGMGENERATORSMOKE Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGeneratorSmokeImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGeneratorSmokeImpl(varargin{:});
end
end