# TGM Geometry App

Standalone lightweight MATLAB `uihtml` app for browsing cached rFactor 2 TGM
tyres and plotting only the tyre geometry/cross-section.

Start from the repository root:

```matlab
addpath("matlab")
rf2TgmGeometryApp
```

This app reads the tyre database at
`scenarios/tyre/database/rf2_tyre_database.sqlite` and only loads the selected
`.tgm` file when a tyre is selected. It does not load the old TGM Generator ODS
inputs, material library, chart reports, acceptance checks, or tTool setup.
