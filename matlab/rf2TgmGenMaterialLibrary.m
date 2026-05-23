function varargout = rf2TgmGenMaterialLibrary(varargin)
%RF2TGMGENMATERIALLIBRARY Compatibility wrapper for the TGM Generator app implementation.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGenMaterialLibraryImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGenMaterialLibraryImpl(varargin{:});
end
end