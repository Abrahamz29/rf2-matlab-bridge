function varargout = rf2TgmGenChartData(varargin)
%RF2TGMGENCHARTDATA Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGenChartDataImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGenChartDataImpl(varargin{:});
end
end