# tyre_designer

Standalone lightweight MATLAB `uihtml` app for browsing cached rFactor 2 TGM
tyres and plotting the tyre geometry/cross-section.

Start from the repository root:

```matlab
setup_rf2_matlab()
tyre_designer
```

All Tyre Designer MATLAB entry points and helpers live in this app folder:
`tyre_designer.m`, `tyre_designer_open.m`, `tyre_designer_app.m`, parser and
plot-data helpers, and the HTML assets.

This app reads the tyre database at
`tyres/database/rf2_tyre_database.sqlite` and only loads the selected
`.tgm` file when a tyre is selected. Material library tables and saved material
mix assignments also live in that database. It does not load the old TGM
Generator ODS inputs, chart reports, acceptance checks, or tTool setup.


