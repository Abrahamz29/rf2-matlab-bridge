function projectRoot = rf2TgmGeometryProjectRoot()
%RF2TGMGEOMETRYPROJECTROOT Return the repository root for the standalone app.
appRoot = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(appRoot)));
end
