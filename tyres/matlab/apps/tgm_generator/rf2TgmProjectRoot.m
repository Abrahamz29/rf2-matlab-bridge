function projectRoot = rf2TgmProjectRoot()
%RF2TGMPROJECTROOT Return the repository root for the TGM app files.
appRoot = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(fileparts(appRoot))));
end
