# RMOD-K teardown presentations

Created: 2026-05-25

These decks summarize the RMOD-K public documentation crawl, downloaded
Formula archives, and local `rf2-tyre` tooling.

## Files

- `rmodk_toolchain_gap_analysis.pptx` - tool inventory, RMOD-K public tools,
  and capability gaps versus the current `rf2-tyre` stack.
- `rmodk_model_types_physics.pptx` - RMOD-K model family overview: Formula,
  RB, FB, FB Misuse, RMOD-M, FlexView, Measurements/TPL/TDX, and schematic
  force-model structure.
- `rmodk_formula_code_teardown.pptx` - downloaded Formula C++ archive anatomy,
  core classes, continuous/discrete evaluator flow, friction/contact logic,
  optimizer path, wrapper options, and reuse checklist.

## Source basis

- Local RMOD-K crawl inventory under `references/rmod-k/`.
- Downloaded RMOD-K Formula VS2017/VS2013 archives and extracted source
  inventory.
- Local project documentation in `tyres/`, `bridge/`, and `docs/tyre/`.

The decks distinguish clearly between the public RMOD-K Formula source package
and the commercially described RB/FB/FlexView toolchain, which was not present
as public solver/source in the crawl.
