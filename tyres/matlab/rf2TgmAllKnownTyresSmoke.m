function varargout = rf2TgmAllKnownTyresSmoke(varargin)
%RF2TGMALLKNOWNTYRESSMOKE Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmAllKnownTyresSmokeImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmAllKnownTyresSmokeImpl(varargin{:});
end
end