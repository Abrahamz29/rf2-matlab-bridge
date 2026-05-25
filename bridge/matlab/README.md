# Bridge MATLAB

This folder contains the rFactor 2 shared-memory client and telemetry plotting
entry points used for tyre validation workflows.

## TGM Generator App

The TGM Generator app implementation is grouped here:

```text
tyres/matlab/apps/tgm_generator/
```

The TGM-generator compatibility commands live in `tyres/matlab/functions/`.
The Tyre Designer commands live with their app implementation under
`tyres/matlab/apps/tyre_designer/`. Both locations are added by the normal
project setup:

```matlab
setup_rf2_matlab()
rf2TgmGeneratorApp
```

The `rf2Tgm*.m`, `rf2ReadTgm.m`, `rf2WriteTgm.m`, and
`rf2ExtractTgmGenOds.m` files are compatibility wrappers under
`tyres/matlab/functions/`. They add the app folder to the MATLAB path and call
the implementation files under `tyres/matlab/apps/tgm_generator`.

Bridge files here remain telemetry and plotting entry points. Track, vehicle,
actuator, and open-loop automation code has been removed from this repository
scope.
