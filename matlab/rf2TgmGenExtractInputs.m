function varargout = rf2TgmGenExtractInputs(varargin)
%RF2TGMGENEXTRACTINPUTS Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGenExtractInputsImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGenExtractInputsImpl(varargin{:});
end
end