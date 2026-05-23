function varargout = rf2TgmGeometryApp(varargin)
%RF2TGMGEOMETRYAPP Lightweight Geometry-only TGM browser.
rf2TgmAppPath();
if nargout == 0
    rf2TgmGeometryAppImpl(varargin{:});
else
    [varargout{1:nargout}] = rf2TgmGeometryAppImpl(varargin{:});
end
end
