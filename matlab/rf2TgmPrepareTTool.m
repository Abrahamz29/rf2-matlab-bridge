function varargout = rf2TgmPrepareTTool(varargin)
%RF2TGMPREPARETTOOL Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmPrepareTToolImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmPrepareTToolImpl(varargin{:});
end
end