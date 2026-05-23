function varargout = rf2TgmGenFormulaReport(varargin)
%RF2TGMGENFORMULAREPORT Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGenFormulaReportImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGenFormulaReportImpl(varargin{:});
end
end