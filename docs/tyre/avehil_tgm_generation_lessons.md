# AVEHIL Thesis: Lessons For Generating TGM Files

Source file:

```text
input/Optimisation+of+the+tyre+model+in+rFactor2+environment+for+AVEHIL+professional+simulator.pdf
```

This note extracts the parts that are directly useful for our TGM generator,
MATLAB/HTML UI, tTool automation and tyre behaviour database.

## Core Takeaway

The thesis does not replace the rFactor 2 tyre solver. It uses the official
TGM workflow:

1. Build a first `.tgm` from measured tyre data with TGM Generator.
2. Validate the structural model with tTool QSA batch tests.
3. Generate or refresh lookup data with tTool.
4. Tune `[Realtime]` parameters with tTool Realtime batch tests.
5. Validate offline in tTool and online in the simulator.

For our project this means the correct architecture is:

- MATLAB/HTML app for structured authoring, plotting, optimisation and export.
- tTool as the reference engine for QSA, Lookup and Realtime bench results.
- Database layer for TGM parameters, tTool results and optimisation history.

## TGM File Structure To Preserve

The thesis describes four important `.tgm` areas:

- `[QuasiStaticAnalysis]`
  Defines nominal structural data and the QSA operating grid. Important fields
  include mass/inertia, node count, `LateralTestForce`,
  `LongitudinalTestForce`, `GaugePressure`, `CarcassTemperature`,
  `RotationSquared`, `NumSections` and rim/cavity properties.

- `[Node]`
  Defines the tyre cross-section and local material stack. Each node carries
  geometry, bulk/tread material properties, tread depth, ring/rim flags and
  repeated ply definitions.

- `[Realtime]`
  Defines fast runtime tuning parameters: grip, spring/damper/bristle, thermal
  behaviour, degradation, pressure sensitivity and size multipliers. This is
  the main area for quick optimisation after the structural model is plausible.

- `[Lookup]` / `LookupData`
  Contains generated QSA/lookup results. The thesis treats this as not directly
  editable. It must be produced by running tTool.

## Data We Need Before Building A Tyre

The thesis stresses that the hardest part is data collection. Our UI should
therefore guide the user through required evidence, not just expose raw cells.

Minimum input groups:

- Tyre identity and intended use:
  tyre name, front/rear, dry/wet, compound, rim size, nominal pressure,
  target temperature, target speed/load range.

- Basic dimensions:
  section width, radius/diameter, rim width, rim diameter, tread width,
  bead/rim geometry, mounted but uninflated cross-section.

- Physical measurements:
  tyre mass, approximate inertia if available, cavity/rim volume, unloaded
  geometry, vertical deflection checks.

- Geometry:
  cross-section nodes as `(x, y, thickness)`, symmetric/asymmetric flag, tread
  bounds and material-region bounds.

- Construction:
  rubber layer selection, ply material, ply boundary nodes, ply thickness,
  ply angle, bead/filler and chafer details.

- Material library:
  rubber and ply properties over temperature, density, Young's modulus,
  Poisson ratio, thermal conductivity, heat capacity and damping-related values.

- Real target data:
  lateral force, longitudinal force and aligning moment curves if available;
  measured surface temperature and pressure traces if thermal tuning is
  required.

## Authoring Workflow To Implement

### 1. Geometry And Construction First

The initial `.tgm` must be driven by physical shape and construction:

- Build the cross-section from measured or scanned data.
- Prefer a realistic node count over a very dense model at first.
- Keep node count and `NumSections` aligned because more nodes increase QSA
  compute time.
- Plot the cross-section continuously while editing.
- Plot every ply layer and material boundary, because ply placement has direct
  influence on stiffness, growth, pressure distribution and pneumatic trail.

### 2. Material Stack And Compound

The ODS workflow separates construction materials from compound/realtime
behaviour. We should do the same:

- Construction materials define local structural and thermal behaviour at nodes.
- Compound selection fills large parts of `[Realtime]`.
- Compound page needs plots for abrasion, degradation, thermal fraction and
  grip-vs-temperature behaviour.
- Material dropdowns should resolve into actual editable material records.

### 3. Initial QSA Grid

In early development the thesis recommends only a few QSA operating conditions
to save time. For our app:

- Provide a "quick QSA grid" preset for early checks.
- Provide a "final QSA grid" preset with expanded pressure/temperature/speed
  combinations before final lookup generation.
- Make the final export explicit: quick files are not final tyres.

### 4. QSA Batch Validation

After generating the first `.tgm`, tTool QSA tests should verify:

- shape
- vertical stiffness
- lateral stiffness
- longitudinal stiffness
- growth with speed/pressure
- contact patch pressure distribution

Our app should generate QSA test files, collect tTool outputs and plot the
results next to expected/target data.

### 5. Realtime Batch Validation

Once the lookup is present, tTool Realtime batch tests are used for behaviour
that the driver feels:

- slip angle sweep for lateral force and aligning moment
- longitudinal slip test for braking/traction force
- rolling resistance
- deflection tests
- combined-slip curves

Our existing tyre database should store all of these runs as behaviour data,
not just raw CSV files.

## Parameters To Optimise First

The thesis selected the following `[Realtime]` parameters as high-value
mechanical tuning variables:

- `StaticBaseCoefficient`
- `SlidingBaseCoefficient`
- `LoadVsDeflectionMultiplier`
- base value of `BeltSpringX`
- base value of `BeltSpringZ`
- base value of `TreadSpringXPerUnitArea`
- base value of `TreadSpringZPerUnitArea`
- `RubberPressureSensitivityPower`

For vector parameters such as `BeltSpringX`, the thesis focuses on the base
term first to keep the search space manageable. Pressure, temperature and
rotation multipliers should be separate later-stage tuning dimensions.

## Objective Functions For Optimisation

The useful optimisation target is not "one parameter looks better". The thesis
uses objective functions against real target curves:

- MSE between target and virtual lateral force curve.
- MSE between target and virtual longitudinal force curve.
- MSE between target and virtual self-aligning moment curve.
- Difference between target and virtual longitudinal peak force.

The important curve region is the ascending part up to peak grip because that
is the main tyre utilisation range.

Implementation consequence:

- Add a behaviour comparison module that imports target curves.
- Normalize curves when confidential or cross-tyre comparison is needed.
- Store every parameter set and resulting objective values in the database.
- Support Pareto filtering, but keep final selection manual because a front/rear
  tyre may require different compromises.

## Parameter Sweep Strategy

The thesis uses a pragmatic training strategy:

- Vary one parameter at a time.
- Use constant steps around the current value.
- Record tTool output after each change.
- Fit/predict how objective functions react.
- Test selected combinations offline in tTool.
- Validate final candidates online in the simulator.

For us this suggests an automated loop:

1. Pick baseline `.tgm`.
2. Generate parameter variations.
3. Copy candidate `.tgm` to `pTool`.
4. Run selected tTool Realtime batch tests.
5. Import `CustomRealtimeTable.csv`.
6. Compute objective functions.
7. Rank candidates and show trade-offs.

## Thermal Tuning Lessons

The thesis highlights three practical thermal parameters:

- `StaticCurve`
  Temperature-to-grip multiplier curve. It is effectively a grip-vs-temperature
  calibration and should be plotted clearly.

- `GroundConductance`
  Controls heat exchange with the road/contact patch as a function of contact
  pressure.

- `ExternalGasHeatTransfer`
  Controls cooling by air. The thesis models it as:

```text
ExternalGasHeatTransfer = a + b * speed^c
```

Useful UI plots:

- `StaticCurve`: temperature `[K]` vs grip multiplier.
- `GroundConductance`: contact pressure vs conductance.
- `ExternalGasHeatTransfer`: speed vs cooling coefficient.
- Thermal comparison: measured surface temperature vs simulated temperature
  over test distance/time.

Thermal tuning is less directly supported by offline tTool curves, so the thesis
uses measured traces and driver feedback. Our tool should mark this as
lower-confidence than force-curve optimisation.

## Important Limitation

Realtime parameters mostly scale or shape the behaviour encoded in the lookup.
They cannot fully repair a structurally wrong tyre. In particular:

- self-aligning moment and pneumatic trail depend strongly on contact patch
  properties
- contact patch properties come from QSA/Lookup
- fixing those issues may require changing ply structure, node geometry or
  material stack, then regenerating lookup data

So our tool should warn when Realtime optimisation improves force curves but
aligning moment remains poor. That is likely a structural/QSA problem, not just
a coefficient problem.

## Features We Should Add To Our App

- A guided "TGM build wizard" with these phases:
  `Data -> Geometry -> Construction -> Compound -> QSA -> Lookup -> Realtime -> Validation`.

- A "physical evidence" panel:
  record which dimensions/materials came from measurement, scan, manufacturer
  data, guess or borrowed reference tyre.

- QSA presets:
  quick development grid and final production grid.

- tTool automation:
  copy `.tgm`, write QSA/realtime `.ini`, run/assist tTool, import results.

- Parameter sweep runner:
  vary selected `[Realtime]` parameters by percentage, run batch tests and store
  objective values.

- Target curve importer:
  support `.tir`/MF-style targets if available, plus CSV target curves.

- Plot pack:
  cross-section, all plies, material properties, `StaticCurve`,
  spring/stiffness parameters, QSA stiffness, Realtime sweep, longitudinal,
  aligning moment, rolling resistance, thermal traces.

- Database schema extension:
  store candidate parameter sets, source `.tgm`, generated `.tgm`, tTool run,
  target curve id and objective-function scores.

## Practical Rule For Our Generator

We can generate the readable `.tgm` text ourselves, but a usable final tyre still
needs tTool for Lookup/Patch generation. A good `.tgm` authoring tool is
therefore not just a file writer. It must be an iterative measurement,
simulation, optimisation and validation system around tTool.
