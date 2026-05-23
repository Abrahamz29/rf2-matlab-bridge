# MATLAB Folder

This folder keeps stable MATLAB entry points at the top level.

## TGM Generator App

The TGM Generator app implementation is grouped here:

```text
matlab/apps/tgm_generator/
```

Use the existing public commands from the MATLAB root as before:

```matlab
addpath("matlab")
rf2TgmGeneratorApp
```

The root `rf2Tgm*.m`, `rf2ReadTgm.m`, `rf2WriteTgm.m`, and
`rf2ExtractTgmGenOds.m` files are compatibility wrappers. They add the app
folder to the MATLAB path and call the implementation files under
`apps/tgm_generator`.

Other root files remain telemetry, plotting, and automation entry points.
