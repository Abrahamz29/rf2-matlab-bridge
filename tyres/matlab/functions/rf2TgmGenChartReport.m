function varargout = rf2TgmGenChartReport(varargin)
%RF2TGMGENCHARTREPORT Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGenChartReportImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGenChartReportImpl(varargin{:});
end
end