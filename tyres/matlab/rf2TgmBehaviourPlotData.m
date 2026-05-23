function varargout = rf2TgmBehaviourPlotData(varargin)
%RF2TGMBEHAVIOURPLOTDATA Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmBehaviourPlotDataImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmBehaviourPlotDataImpl(varargin{:});
end
end