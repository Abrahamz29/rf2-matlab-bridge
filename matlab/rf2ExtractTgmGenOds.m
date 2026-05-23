function varargout = rf2ExtractTgmGenOds(varargin)
%RF2EXTRACTTGMGENODS Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2ExtractTgmGenOdsImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2ExtractTgmGenOdsImpl(varargin{:});
end
end