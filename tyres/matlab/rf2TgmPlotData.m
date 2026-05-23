function varargout = rf2TgmPlotData(varargin)
%RF2TGMPLOTDATA Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmPlotDataImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmPlotDataImpl(varargin{:});
end
end