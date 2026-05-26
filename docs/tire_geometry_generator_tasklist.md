# Tire Geometry Generator Tasklist

Goal: build a tyre generator page that creates usable node coordinates from
professional tyre-construction scalars instead of editing every node manually.

- [x] 1. Parametric contour V1: generate a complete cross-section preview from
  outer diameter, rim diameter, section width, rim width, tread/crown width,
  crown radius, shoulder radius, sidewall bulge, bead radius, node thickness,
  tread depth, and node count.
- [ ] 2. Construction layers: generate tread, carcass/ply, belt, chafer, bead
  filler, and sidewall layer paths from scalar widths, thicknesses, wrap points,
  and start/end nodes.
- [ ] 3. Material assignment: connect generated layers to the shared material
  database and store the selected tyre construction as database tables.
- [ ] 4. Export preview: show the generated TGM node geometry, PlyParams,
  BulkMaterial/TreadMaterial assignments, and export-impact summary before
  writing a model file.
- [ ] 5. Reverse-engineering bridge: use imported Excel/ODS/TGM data as a
  fitted starting point for the same generator parameters.
- [ ] 6. Advanced profile mode: add optional spline/control-point fitting for
  race-tyre shapes that cannot be represented well by the V1 scalar model.

Reference basis: see `references/tire_geometry_cross_section_sources.md`.
