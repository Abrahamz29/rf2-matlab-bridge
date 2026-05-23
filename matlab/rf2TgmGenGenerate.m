function varargout = rf2TgmGenGenerate(varargin)
%RF2TGMGENGENERATE Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGenGenerateImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGenGenerateImpl(varargin{:});
end
end