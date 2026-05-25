# RMOD-K public site inventory

Retrieved: 2026-05-25

Scope: same-origin public content from `https://www.rmod-k.com/`, respecting
`robots.txt`. Joomla system folders such as `/media/`, `/modules/`,
`/plugins/`, `/templates/`, and login-only user-area downloads were not
mirrored. The local mirror contains public content pages, public downloads, and
linked image/media assets under `references/rmod-k/site/`.

## Local mirror

- Manifest: `references/rmod-k/site/manifest.json`
- Pages index: `references/rmod-k/site/pages.csv`
- Assets index: `references/rmod-k/site/assets.csv`
- Crawl errors: `references/rmod-k/site/errors.csv` (0 errors)
- Public pages mirrored: 21
- Public assets mirrored: 39

Notable public downloads:

- `references/rmod-k/site/assets/images__stories__media__downloads__Formula__Formula-C_VS2017.7z`
- `references/rmod-k/site/assets/images__stories__media__downloads__Formula__Formula-C_VS2013.7z`
- `references/rmod-k/site/assets/images__stories__media__downloads__Formula__RMOD-K-Formula-Documentation.pdf`
- `references/rmod-k/site/assets/images__stories__media__downloads__Formula__formula.pdf`
- `references/rmod-k/site/assets/images__stories__media__downloads__measurements__RMOD-K-V7-Measurement_Packages.pdf`
- `references/rmod-k/site/assets/images__stories__media__downloads__measurements__RMOD-K-V7-Measurements-TDX_Format.pdf`
- `references/rmod-k/site/assets/images__stories__media__downloads__measurements__Date_Measurement_Package_Request_Example.xlsx`
- `references/rmod-k/site/assets/images__stories__media__downloads__TPL__TPL-THB-E.pdf`
- `references/rmod-k/site/pages/images__stories__media__downloads__FlexView_Animation_Rebars.htm`
- `references/rmod-k/site/assets/images__stories__media__downloads__FlexView_Animation_Rebars.swf`
- `references/rmod-k/site/assets/robots.txt`

## Tool and model overview

### RMOD-K Formula

Source pages/files:

- `https://www.rmod-k.com/formula`
- `https://www.rmod-k.com/images/stories/media/downloads/Formula/RMOD-K-Formula-Documentation.pdf`
- `https://www.rmod-k.com/images/stories/media/downloads/Formula/formula.pdf`
- `Formula-C++VS2013.7z`
- `Formula-C++VS2017.7z`

Public availability: public download.

Purpose: educational/source-available steady-state tyre modelling package. The
site describes it as an open-source collection of two simple tyre models plus
optimisation tooling and simulation interfaces. It is not the full RMOD-K 7 RB
or FB product.

Models included:

- Analytic/continuous algebraic Formula model with physically meaningful
  parameters.
- Extended discrete tangential-contact Formula model with contact area, normal
  stress distribution, friction properties, and camber support.
- Magic Formula 5.2 helper/import code is present in the source package.

Interfaces and tools included in the archives:

- C++ source code and Visual Studio 2013/2017 projects.
- Windows GUI project/application (`Formula-GUI`).
- Standalone runner (`RMOD-K-Formula-Run.exe` in the work tree of the archive).
- MATLAB MEX interface and optimisation scripts.
- Simulink S-function and example models.
- Scilab interface, DLL, and optimisation examples.
- Gnuplot scripts and sample `.dat` measurement/target/result data.

Archive inventory:

- VS2017 archive: 325 files. Main top-level folders: `BuildAll`,
  `Formula-GUI`, `MATLAB`, `SCILAB`, `SIMULINK`, `source`, `STANDALONE`.
- VS2013 archive: 320 files with the same functional layout.
- Notable source files include `ContinusFormula.*`, `DiscreteFormula.*`,
  `MF5p2.*`, `RMOD_K_Formula_Run.*`, `RMOD_K_Formula_Opti.*`,
  `RMOD_K_Formula_MATLAB.cpp`, `RMOD_K_Formula_SCILAB.cpp`, and
  `RMOD_K_Formula_S_function.cpp`.

License status: the page/PDF call it open source, but the inspected archives
do not contain a standard license file. Treat this as source-available until a
clear license grant is available. See `references/rmod_k_open_source.md`.

### RMOD-K 7 RB: Rigid Belt

Source page: `https://www.rmod-k.com/rigid-belt-rb`

Public availability: descriptive page only; no public RB executable/source
download was found in the crawl.

Purpose: rigid belt tyre model for low/medium frequency vehicle and road
inputs. The public page positions it up to about 100 Hz and about 100 mm road
disturbance wavelength.

Tools/data mentioned:

- RFNRB input deck parameters for grid, belt dynamics, contact geometry,
  pressure distribution, sticking/sliding behaviour.
- RMOD-M(otion), described as a standalone MBS system that can calculate
  steady-state forces versus slip and sweep-slip responses.
- `BELTBUSH.DAT` output from RMOD-M for bushing stiffness/damping and belt
  mass/inertia.
- MBS postprocessor visualization is mentioned for belt deformation/vibration
  when geometry exists.

Conclusion: RB is represented on the public site as a model/product with
parameter workflow notes, not as a public downloadable tool package.

### RMOD-K 7 FB: Flexible Belt

Source page: `https://www.rmod-k.com/flexible-belt-fb`

Public availability: descriptive page plus images; no public FB solver/source
download was found in the crawl.

Purpose: flexible belt model for cleats, short-wavelength obstacles, ride/load
case studies, and misuse simulations. The site says version 7.10x and later are
reimplemented in C++ and can compute each tyre of a vehicle model in parallel
mode.

Model features described:

- Discrete finite element structure based on a master cross-section.
- Adjustable topology/mesh density and model properties by application.
- Belt and sidewall rebar elements, sidewall nodes, bending ties, preload,
  inflation pressure, contact loading, and analytical nonlinear stiffness.
- Gap sensors on the outer tyre surface, independent from the structure node
  grid.
- Modal analysis support from the analytical stiffness matrix.
- Contact/friction handling with sliding velocity and normal stress dependence.

### FB preprocessor and postprocessor / FlexView

Source pages:

- `https://www.rmod-k.com/flexible-belt-fb#prepost`
- `https://www.rmod-k.com/faqs/16-version-7-09c3-flexview`
- `https://www.rmod-k.com/faqs/18-fb-friction-3d-equidistant-velocity-axis-linear-log`
- `https://www.rmod-k.com/faqs/19-fb-simulationtstart-time-0-0-seconds`
- `https://www.rmod-k.com/faqs/22-first-steps-to-use-the-rmod-k-flexview-animation-tool`

Public availability: FlexView program download is stated to be in the
registered user area. The public crawl found a Flash tutorial
(`FlexView_Animation_Rebars.htm` plus `.swf`) but not the FlexView executable.

Preprocessor capabilities described:

- GUI-based FB parameterisation.
- Standard manoeuvres including steady-state tyre behaviour.
- Drum cleat test runs.
- Design-of-experiments sensitivity studies over parameter sets.
- Single input-file concentration of model parameters, manoeuvre data, and
  output settings.

Postprocessor/FlexView capabilities described:

- Animation of modal-analysis results for unloaded inflated tyre states and
  loaded rolling states.
- Time-domain structure dynamics animation.
- Footprint/contact point dynamics with velocity or stress components.
- Friction3D editor settings for linear or logarithmic velocity-axis lookup
  tables and maximum sliding velocity.
- 3D editor for footprint results in a separate GUI program.
- Extended TDX result format and plotting through the RMOD-K GUI plot program
  using gnuplot.

Conclusion: yes, RMOD-K offers/mentions a preprocessor/postprocessor toolchain
for FB, but the actual Windows program appears to be behind the RMOD-K user
area, not in the public download set.

### FB Misuse

Source page: `https://www.rmod-k.com/fb-misuse`

Public availability: descriptive page plus images; no public misuse executable
or source download was found in the crawl.

Purpose: extension of the FB workflow for large obstacles and tyre/rim inner
contact. The page mentions cleat and pothole cases and vehicle-suspension
strength/durability studies.

Features described:

- Inner contact between tyre and rim.
- Nonlinear unilateral stiffness elements.
- Gap data generated from cross-section information.
- Large displacement cleat/pothole manoeuvres.
- Integration with full-vehicle MBS models.

## Measurement and data support

### Measurements

Source page/files:

- `https://www.rmod-k.com/measurements`
- `RMOD-K-V7-Measurement_Packages.pdf`
- `RMOD-K-V7-Measurements-TDX_Format.pdf`
- `Date_Measurement_Package_Request_Example.xlsx`

Public availability: public PDF/XLSX downloads.

Purpose: define measurement packages for parameterising RMOD-K FB.

Measurement groups described by the page:

- General tyre/rim dimensions and mass.
- Topology data such as cross-section and belt angle.
- Force and moments.
- Static stiffness.
- Cleat measurements.
- Modal system data.

The TDX format document defines the ASCII result-file structure used for
measurement data. The public XLSX is a request template with columns for front
and rear tyre positions and rows for vehicle, tyre, rim, pressure, load index,
stiffness, phase-cleat, Magic Formula tyre file, footprint, cross-section,
mass/inertia, and modal-analysis requests.

### Tyre Property Lab (TPL)

Source page/file:

- `https://www.rmod-k.com/tyre-property-lab`
- `TPL-THB-E.pdf`

Public availability: public PDF and images.

Purpose: lab/test-facility overview for FE-model-oriented tyre-property
measurement. The public material covers static/dynamic tyre properties,
contact pressure distribution, cross-section measurement, vertical stiffness,
modal analysis, and rolling-wheel tests used for model parameter optimisation.

## What the public site does not provide

- No public downloadable RMOD-K 7 RB solver/source package was found.
- No public downloadable RMOD-K 7 FB solver/source package was found.
- No public downloadable FB misuse extension package was found.
- No public downloadable FlexView Windows executable was found; the FAQ points
  to the registered user area.
- No standard open-source license file was found inside the public Formula
  source archives.

## Relevance to our rf2-tyre work

- The only public source package we can directly inspect and potentially reuse
  is RMOD-K Formula. It is useful as a steady-state tyre-model reference and as
  C++/MATLAB/Simulink/Scilab example code, but it is not a replacement for
  rFactor 2 TGM/tTool physics.
- RB, FB, FlexView, RMOD-M, and FB Misuse are important conceptual references
  for future tyre-tool design, especially measurement formats, pre/post
  processing, contact/friction visualisation, and parameter workflows.
- For any implementation reuse, first resolve Formula licensing beyond the
  plain "open source" wording on the web page/PDF.
