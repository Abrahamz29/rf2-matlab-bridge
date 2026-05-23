# tyre_designer

Standalone lightweight MATLAB `uihtml` app for browsing cached rFactor 2 TGM
tyres and plotting the tyre geometry/cross-section.

Start from the repository root:

```matlab
setup_rf2_matlab()
tyre_designer
```

This app reads the tyre database at
`tyres/database/rf2_tyre_database.sqlite` and only loads the selected
`.tgm` file when a tyre is selected. It does not load the old TGM Generator ODS
inputs, material library, chart reports, acceptance checks, or tTool setup.


