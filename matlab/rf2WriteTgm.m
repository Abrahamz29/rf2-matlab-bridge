function varargout = rf2WriteTgm(varargin)
%RF2WRITETGM Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2WriteTgmImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2WriteTgmImpl(varargin{:});
end
end