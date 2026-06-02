# ETRTO Rim Contour Sources

- **ETRTO Standards Manual 2017** (`input/ETRTO-Standards-Manual2017.pdf`, local copy inspected 2026-05-31)
  - Used pages **R.8** and **R.9** for the passenger-car 5 degree drop-centre rim basic contour, contour dimension symbols, J-profile dimensions, and specified rim diameters.
  - Used page **R.11** for Hump `H` geometry inputs, especially contour dimension `E`, hump radii `R3`/`R8`, and hump circumference values.
  - Rendered local reference crops in `tyres/analysis/_etrto_rim_reference/` for visual comparison while correcting the Tyre Designer rim contour.
  - Applied the R.8 hard dimensions as deterministic geometry: drop-centre depth `H`, well distance `Q`, ledge minimum `L`, well angle `beta`, flange width `B`, flange height `G`, flange radius `R1`, bead-seat radius `R2`, well transition radii `R4`/`R5`, and the 5 degree bead-seat line.
  - Applied the H-hump as true tangent circle arcs: crest at `D_H/2`, lateral position from `E`, crest radius `R3`, and tangent bead-seat transition radius `R8`.
  - Added `tyres/analysis/etrto_rim_overlay_check.html` as a local dimension-true overlay check against the rendered ETRTO crops.
  - Added schematic bitmap overlays `tyres/analysis/_etrto_rim_reference/etrto_R8_bitmap_overlay.png` and `tyres/analysis/_etrto_rim_reference/etrto_R11_bitmap_overlay.png`; these are visual aids only because the ETRTO detail drawings are not rendered at strict millimetre scale.
  - Added `tyres/analysis/_etrto_rim_reference/etrto_bitmap_alignment_metrics.json` for reproducible pixel-distance diagnostics of the current scan overlays; this records residuals but is not yet used as a dimension pass/fail gate.
  - Added `tyres/analysis/_etrto_rim_reference/etrto_rim_sweep_verification.json` to verify standard ETRTO rim width/diameter combinations separately from deliberately over-constrained rim-contour override cases.
  - Added `tyres/analysis/tyre_designer_display_rim_overlay.html` to render the same visible Tyre Designer rim layers over the independent dimension reference.
  - Added `tyres/tools/build_tyre_designer_etrto_rim_artifacts.py` to regenerate the display overlay, bitmap scan overlays, PNGs, exported rim points, and sweep JSON from the current Tyre Designer HTML/JavaScript source.
  - Added `tyres/tools/test_tyre_designer_etrto_rim_runtime.py` as the reproducible runtime gate for the Tyre Designer JavaScript rim contour.
  - Added `tyres/tools/test_tyre_designer_etrto_rim_artifacts.py` as the reproducible artifact gate for the generated overlay files, sweep JSON, source notes, and rendered PNG.
  - Applied in `tyres/matlab/apps/tyre_designer/assets/tyre_designer.html` for the Tyre Designer rim contour drawing and rim-contour controls.
