function projectRoot = tyre_designer_project_root()
%TYRE_DESIGNER_PROJECT_ROOT Return the repository root for the standalone app.
appRoot = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(appRoot)));
end
