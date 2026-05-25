# AGENTS.md

## Purpose

This repository is a MATLAB + Python workspace for tyre-model research,
conversion, analysis, plotting, validation, and supporting tooling across tyre
model families. rFactor 2 TGM/TBC/tTool work remains one important supported
target, but the project scope is broader than rFactor 2 and includes market
and research tyre models wherever useful.

## Working Rules

- Keep changes scoped to tyre models, tyre data, telemetry needed for tyre
  validation, plotting, automation for tyre experiments, documentation, and
  supporting tooling for this project.
- Do not expand track, car, or general vehicle-authoring features unless the
  user explicitly asks or they are directly needed to validate a tyre model.
- Prefer domain-first folders over language-first folders:
  - `bridge/` for shared-memory access, telemetry, automation runners, and
    MATLAB/Python bridge code used by tyre validation workflows
  - `tracks/blacklake/` for legacy/reference BlackLake assets only; do not
    grow track-authoring features without an explicit request
  - `docs/` for operational notes and workflow documentation
  - `scenarios/` for tyre-model experiment batches, sweeps, validation cases,
    and reproducible test inputs
  - `tyres/` for tyre model inputs, rFactor 2 TGM/TBC data, model databases,
    tyre references, tTool scenarios, MATLAB apps, tools, generated lookup
    extracts, and local tyre caches
  - `references/` for external model documentation, papers, formula references,
    public tool crawls, downloaded documentation, and concise source notes
- Preserve user changes. Do not revert unrelated edits.
- Verify changes with the narrowest relevant check before committing.
- When external sources, papers, guides, web pages, formula references, or
  datasets are used for implementation or analysis decisions, record them under
  `references/` in addition to citing them in the conversation. Keep entries
  concise but include title/source, URL or local path, retrieval date when
  applicable, and what the source was used for.
- Create presentation deliverables as HTML first. Generate PowerPoint/PPTX only
  when the user explicitly asks for PowerPoint output.

## Git Workflow

- Initialize and maintain this directory as a Git repository.
- Do not commit or push every small edit. Create a local commit only after an
  important, verified checkpoint, such as a completed UI menu/page, a finished
  parser feature, a database/schema update, a validated workflow milestone, or
  a coherent documentation update.
- Push to the configured `origin` after those verified checkpoints, before
  ending a larger work session, or when the user explicitly asks for a push.
- If no remote exists yet, prepare the repo locally and document the exact
  commands needed to add `origin` and push `main`.
- Keep commit messages short and descriptive.

## Minimum Verification

- Python changes: run syntax or targeted execution checks.
- MATLAB changes: run the narrowest callable smoke test available.
- Documentation-only changes: ensure referenced paths and commands exist.

## Project Context

- Tyre-model understanding is the primary project objective. Treat rFactor 2,
  RMOD-K, Pacejka/Magic Formula, MF-Tyre/MF-Swift, FTire, CDTire, TMeasy,
  brush models, finite-element belt/carcass models, and other commercial or
  research models as comparable members of the broader tyre-model landscape.
- rFactor 2 shared-memory telemetry and the existing rF toolchain remain
  supported data paths, but they are no longer the only project center.
- Live rFactor 2 telemetry still requires the rFactor 2 client, not only the
  dedicated server.
- Mock and offline data modes are acceptable for plot, parser, and model
  comparison development when a simulator or solver is not running.
- Automation should focus on repeatable tyre experiments, data extraction, and
  validation workflows. Avoid new track/car automation unless explicitly
  requested.

## General Tyre Model Working Memory

Use this section whenever discussing Reifenmodelle, model conversion,
parameterization, measurements, contact patch behavior, force/moment curves,
transient response, thermal behavior, wear, pressure, or validation across tyre
model families. Treat it as standing context, not as a replacement for local
file inspection.

- Keep the distinction clear between empirical, semi-empirical, physical,
  structural, finite-element, and simulator-specific tyre models.
- For every model, identify its intended use: steady-state force/moment,
  transient handling, ride/cleat response, contact patch detail, misuse/load
  cases, thermal/wear behavior, AI guidance, or simulator runtime lookup.
- Track units, coordinate systems, sign conventions, slip definitions, camber
  definitions, load normalization, pressure conventions, and temperature scales
  before comparing parameters across tools.
- Prefer measured tyre data and published model documentation over copied
  parameter sets. When data is incomplete, record assumptions and avoid
  presenting fitted parameters as physical truth.
- Separate model generation from validation. A model parser or converter is not
  validated until force/moment curves, pressure/temperature behavior, and at
  least one relevant transient or simulator workflow have been checked.
- Document external sources under `references/` and keep local notes concise:
  what was retrieved, when, which model/tool it describes, and how it informed
  the analysis.

## rFactor 2 Tire Model Working Memory

Use this section whenever discussing rFactor 2 TGM, TBC, tTool, tire geometry,
tire grip, heat, wear, pressure, or AI tire behavior. It condenses the
MotorLaps rFactor 2 tire development guide into project rules and must be
treated as standing context, not as a replacement for local file inspection.
Source reference: https://motorlaps.com/tire-development-rfactor2.php

### Model hierarchy

- The `.tgm` file is the master driver-feel model. It controls deformation,
  contact patch behavior, grip generation, heat transfer, wear, pressure
  sensitivity, and the lookup data used by rFactor 2 at runtime.
- The `.tbc` file is mainly an AI, compound, and visual wrapper. It points to
  the `.tgm`, gives AI strategy hints, defines visual dimensions around the
  rim, and includes a few collaborative spring/damper parameters.
- When grip, feedback, sliding, warmup, overheating, or wear feel wrong, inspect
  and tune the `.tgm`, especially `[Realtime]`, before chasing `.tbc`
  `DryLatLong` or `WetLatLong` values.
- As a rule of thumb, tire physics work is mostly TGM work and only secondarily
  TBC work.

### TGM structure assumptions

- `[QuasiStaticAnalysis]` defines structural test conditions for tTool lookup
  generation: layer count, radial sections, rim volume, pressure test points,
  carcass temperatures, rotation speeds, and node count.
- Current rFactor 2 QSA expects `NumLayers=2`. `NumSections=132` is a common
  recommended target; more sections cost more computation. Node counts around
  41-49 are preferred for accurate tire profiles, with about 31 as a lower
  practical floor.
- Temperatures are Kelvin. Convert with `C = K - 273.15`. Common anchors:
  273K cold/freezing, 293K ambient, 353K warm, 378K around 105C slick optimum,
  428K overheated.
- Node `Geometry=(X,Y,thickness)` is in meters. `X` is radial position, `Y` is
  lateral position, and the third value is the local node thickness. Do not
  confuse this with `TreadDepth`; both matter for cross-section plots.
- `TreadDepth` is tread rubber depth in meters. It affects stiffness and grip
  behavior and should be plotted separately from full node thickness.
- `BulkMaterial` entries define temperature-dependent density, Young's modulus,
  Poisson ratio, compression multiplier, specific heat, and conductivity.
- `PlyParams=(angle, thickness, connection_flags)` defines internal fabric/ply
  layers. For geometry visualization, respect cumulative ply thickness and
  keep layer offsets physically distinct.
- `[LookupData]` is generated by tTool and represents precomputed behavior over
  load, speed, temperature, pressure, and slip combinations.

### TBC and SlipCurve assumptions

- TBC `SlipCurve` data is normalized AI guidance, not the main human-driver
  grip source. Lateral curves are slip-angle based; acceleration and
  deceleration curves are slip-ratio based.
- Typical `Step` ranges: lateral about `0.004-0.010` for roughly 6-12 degrees
  slip angle; longitudinal about `0.003-0.005` for roughly 1.5-2.5% slip ratio.
- Narrow grip windows are preferred for realistic racing tires. Wide windows
  make drifting, lockups, and wheelspin too forgiving. TBC `DropoffFunction`
  around `0.35-0.45` is a useful aggressive-falloff reference.
- In `[COMPOUND]`, `TGM="file.tgm"` is the key link to real driver feel.
  `DryLatLong`, `WetLatLong`, `LoadSensLat`, `LatPeak`, `LongPeak`,
  `Temperatures`, `Heating`, `Transfer`, `OptimumPressure`, `GripTempPress`,
  `WearRate`, and `WearGrip*` mostly inform AI strategy and high-level
  behavior.
- TBC `Radius`, `Width`, and `Rim` are visual/AI dimensions. `SpringBase`,
  `SpringkPa`, and `Damper` can collaborate with TGM tire compliance.

### Realtime tuning anchors

- Make small changes and test one parameter group at a time. Base coefficient
  changes of about `+/-0.1` to `+/-0.3` are already significant; curve value
  changes of about `+/-0.05` to `+/-0.1` are typical.
- `StaticBaseCoefficient` controls baseline non-sliding grip. Lower it when
  initial bite is too strong; a change around `0.1-0.2` is meaningful.
- `SlidingBaseCoefficient` controls post-peak sliding grip. Lower it when slides
  are too easy to hold or recover.
- `StaticDiffusiveAdhesion` controls peak sharpness. Raising the third value
  sharpens falloff and narrows the grip window; lowering it makes feedback more
  progressive.
- `SlidingDiffusiveAdhesion` and `SlidingAdhesionCurve` tune sliding behavior
  across sliding speeds. Reduce sliding multipliers when high-slip driving is
  too rewarding.
- `StaticCurve` maps grip to temperature. Use it to define cold grip, optimum
  temperature, and overheating penalty. Slick optimums often live around
  90-110C; road tires often around 60-80C.
- `AbrasionVolumePerUnitEnergy` controls physical wear rate. Scaling the whole
  array is a direct tire-life tuning lever; halving values roughly doubles
  lifetime.
- `DegradationPerUnitHistory` and `DegradationPerWearFraction` control grip
  loss from heat history and wear fraction.
- `RubberPressureSensitivityPower` controls pressure optimum and sensitivity.
  Realistic slick pressure targets often land around 1.5-2.2 bar, but verify
  against the actual tire.
- `LongitudinalDistributionMultiplier` affects braking/acceleration force
  distribution and ABS feel. Reducing it toward about `0.35-0.40` can smooth
  harsh ABS behavior.
- `TemporaryBristleSpring`, `TemporaryBristleDamper`, `WLFParameters`,
  `GrooveEffects`, `DampnessEffects`, and `MarbleEffectOnEffectiveLoad` are
  secondary but important realism levers for deformation, viscoelastic
  temperature response, rubbered track, wetness, and marbles.

### Symptom-to-parameter triage

- Too much front bite: reduce `StaticBaseCoefficient` slightly.
- Drifting is fast or the car is too forgiving at high slip: narrow the grip
  window by increasing `StaticDiffusiveAdhesion` third value, reducing
  `SlidingBaseCoefficient`, reducing `SlidingAdhesionCurve` multipliers, and
  checking sidewall stiffness / TBC `SpringBase`.
- Tire feels wooden or snaps with no warning: lower `StaticDiffusiveAdhesion`
  third value, soften lateral `TemporaryBristleSpring`, and consider higher
  `SlidingMicroDeformationCurve` multipliers for smoother transition.
- Tire overheats from wheelspin or lockups: reduce TBC `Heating` first value,
  increase TGM `ExternalGasHeatTransfer`, and consider higher
  `GroundConductance`.
- Tire overheats under sustained cornering: revisit pressure sensitivity,
  optimum pressure, `StaticCurve` peak temperature, and lateral
  `TemporaryBristleDamper`.
- Pressure keeps running away: verify QSA pressure points, tune
  `InternalGasHeatTransfer`, and consider greater `ThermalDepthBelowSurface`.
- Tire life is wrong: scale `AbrasionVolumePerUnitEnergy`, align TBC
  `WearRate`, and verify degradation curves.
- ABS is harsh or intrusive: reduce `LongitudinalDistributionMultiplier`,
  balance static vs sliding coefficients, and check TBC deceleration curve
  dropoff.

### tTool workflow

- Use a dedicated rFactor 2 `pTool` working directory and start from a validated
  candidate TGM of similar size and compound whenever possible. Building from
  scratch is high-risk.
- Prefer clear names such as `Dry_260-650-R18-SOFT.tgm` using
  `Condition_Width-Diameter-RimSize-Compound.tgm`.
- Launch rFactor 2 DevMode with `+tTool`, manually enter the TGM filename in
  the tTool I/O area, load it, and confirm the cross-section appears.
- Enable `Run Physics`, then `Run Automated`. Expect about 590+ tests and about
  2 hours on a fast PC. Wait until calculations are truly complete.
- Save the file in tTool after the automated run. The saved TGM receives the
  generated lookup data; `.tgm.bak` backups are temporary and overwritten, so
  keep project-side version control with descriptive filenames.
- Move the calculated TGM to the mod tire directory and reference it from TBC.
  Validate in-game with MoTeC telemetry and repeat. Ten or more tTool cycles
  can be normal for serious tire work.

### Data, validation, and pitfalls

- Collect real tire dimensions, construction type, load rating, compound data,
  tread depth, internal construction hints, temperature ranges, pressure ranges,
  skidpad/braking/slalom data, lap times, and driver feedback where available.
- Validate against real lap time within about 0.5 s where data quality allows,
  plus telemetry for warmup, pressure rise, temperature spread, wear, and
  degradation. Cross-check the same tire on multiple vehicles when relevant.
- Avoid common mistakes: wrong slip-curve step values, focusing on TBC instead
  of TGM for driver feel, unrealistic load sensitivity, ignoring cold/overheat
  behavior, exaggerated wear, and copy-paste parameter sets without
  justification.
- Document every parameter choice and every test result. Because tTool runs are
  slow, changes must be traceable and reversible.

