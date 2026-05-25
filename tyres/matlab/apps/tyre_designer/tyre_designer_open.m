function varargout = tyre_designer_open(tyre, options)
%TYRE_DESIGNER_OPEN Start tyre_designer with a tyre and an initial menu.
%   tyre_designer_open("G_9.2-20.0-13x10_Soft_Slick_1975", ...
%       "Menu", "node-explorer")
%
%   TYRE can be a TGM path, a database display name, or a TGM file name/stem.
%   MENU and VIEW accept "model", "node-explorer", "reengineering", or "materials".
arguments
    tyre (1,1) string = ""
    options.Menu (1,1) string = ""
    options.View (1,1) string = "model"
    options.Headless (1,1) logical = false
end

startView = options.View;
if options.Menu ~= ""
    startView = options.Menu;
end

if ~options.Headless
    localCloseExistingTyreDesignerInstances();
end

if nargout == 0
    tyre_designer(tyre, "StartView", startView, "Headless", options.Headless);
else
    [varargout{1:nargout}] = tyre_designer(tyre, "StartView", startView, "Headless", options.Headless);
end
end

function localCloseExistingTyreDesignerInstances()
figures = findall(groot, "Type", "figure", "Name", "tyre_designer");
if isempty(figures)
    return;
end

delete(figures(isvalid(figures)));
drawnow limitrate;
end
