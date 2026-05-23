# TGM Generator App

This folder contains the MATLAB side of the rFactor 2 TGM Generator app.

## Launch

From the repository root:

```matlab
addpath("matlab")
rf2TgmGeneratorApp
```

Or, when this folder is on the MATLAB path:

```matlab
startTgmGeneratorApp
```

## Layout

- `rf2TgmGeneratorAppImpl.m`: uihtml app backend.
- `assets/rf2_tgm_generator.html`: frontend used by `uihtml`.
- `rf2TgmGen*Impl.m`: ODS extraction, generation, chart, formula, and material helpers.
- `rf2ReadTgmImpl.m`, `rf2WriteTgmImpl.m`: TGM parser and writer.
- `rf2TgmPlotDataImpl.m`, `rf2TgmBehaviourPlotDataImpl.m`: app plot data builders.
- `rf2TgmPrepareTToolImpl.m`: prepares generated files for rFactor 2 `pTool`.
- `rf2TgmGeneratorSmokeImpl.m`, `rf2TgmAllKnownTyresSmokeImpl.m`: smoke tests.

Public compatibility wrappers stay one level up in `matlab/` so existing
commands and scripts continue to work.
