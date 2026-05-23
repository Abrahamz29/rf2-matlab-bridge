function varargout = rf2ReadTgm(varargin)
%RF2READTGM Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2ReadTgmImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2ReadTgmImpl(varargin{:});
end
end