# Tyre Model Workspace

This repository is a MATLAB + Python workspace for tyre-model research,
conversion, analysis, plotting, validation, and supporting tooling. rFactor 2
TGM/TBC/tTool work remains one supported target, but the project is broader
than rFactor 2 and is meant to cover useful market and research tyre models.

Track authoring, vehicle automation, vehicle data capture, proving-ground
generation, and car-control tooling are outside the current scope.

## Repository Workflow

- Working rules for Codex and contributors live in `AGENTS.md`.
- GitHub initialization and remote setup notes live in `docs/github_bootstrap.md`.
- Vendor dependencies are included as Git submodules where they support tyre
  model work directly.
- Commit only coherent, verified checkpoints.
- Push to `origin` after stable checkpoints, before longer pauses, or on
  explicit request.

Fresh clone with submodules:

```powershell
git clone --recurse-submodules <repo-url>
```

## Folder Structure

- `tyres/`: tyre model inputs, rFactor 2 TGM/TBC data, model databases,
  references, tTool scenarios, MATLAB apps, parser tools, generated lookup
  extracts, and local tyre caches.
- `tyres/matlab/apps/tgm_generator/`: MATLAB/uihtml TGM Generator app.
- `tyres/matlab/apps/tyre_designer/`: tyre browsing and geometry/plot UI.
- `tyres/tools/`: tyre parsers, DB builders, TGM generator checks, tTool
  helpers, and analysis scripts.
- `tyres/scenarios/`: tyre-only test matrices and validation inputs.
- `docs/tyre/`: operational notes for tyre generation, tTool, lookup data,
  model analysis, and validation.
- `references/`: external model documentation, papers, formula references,
  public tool crawls, downloaded documentation, and concise source notes.
- `tools/`: general developer utilities, such as the VS Code MATLAB runner.
- `input/`: legacy scratch area for older open files; prefer domain folders
  for new data.

## Embedded Reference Projects

- `vendor/TGM-Utils`: local submodule for TGM-related helper code.

## MATLAB Setup

From MATLAB:

```matlab
cd("C:\Users\Victor\Documents\PYTHON\rf2-tyre")
status = setup_rf2_matlab()
```

This adds the MATLAB tyre functions and tyre apps to the path.

TGM Generator:

```matlab
rf2TgmGeneratorApp
```

Tyre Designer:

```matlab
rf2TyreDesignerApp
```

## rFactor 2 TGM/TBC/tTool Scope

For rFactor 2 tyre work:

- `.tgm` is the main driver-feel tyre model.
- `.tbc` is mostly AI, compound, and visual wrapper data.
- `tTool`/`pTool` is the official rFactor 2 tyre simulation and lookup
  generation tool.
- Generated `LookupV2`, `[LookupData]`, and `PatchV1` payloads are still
  produced by tTool, not by the MATLAB generator.

Useful docs:

- `docs/tyre/tgm_generator_port.md`
- `docs/tyre/ttool_tyre_only_batch.md`
- `docs/tyre/ttool_tyre_database.md`
- `docs/tyre/tgm_lookup_table_research.md`

Useful commands:

```powershell
py .\tyres\tools\build_tyre_database.py
py .\tyres\tools\tgm_lookup_extract.py .\tyres\input\tgm\example.tgm --include-patch
.\tyres\tools\Invoke-TgmGenAcceptance.ps1
```

## External Sources

When external papers, guides, tools, formulas, datasets, or websites are used
for implementation or analysis decisions, record them under `references/` with
title/source, URL or local path, retrieval date when applicable, and how the
source was used.

Presentation deliverables should be produced as HTML first. Generate PPTX only
when explicitly requested.
