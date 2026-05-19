# AGENTS.md

## Purpose

This repository contains a MATLAB + Python bridge for rFactor 2 telemetry,
live plotting, and automated driving experiments.

## Working Rules

- Keep changes scoped to telemetry, plotting, automation, documentation, and
  supporting tooling for this project.
- Prefer the existing MATLAB/Python split:
  - `python/` for bridge, shared-memory access, and automation runners
  - `matlab/` for analysis, plotting, and experiment orchestration
  - `docs/` for operational notes and workflow documentation
  - `scenarios/` for maneuver batches and experiment inputs
- Preserve user changes. Do not revert unrelated edits.
- Verify changes with the narrowest relevant check before committing.

## Git Workflow

- Initialize and maintain this directory as a Git repository.
- Create a local commit after each meaningful, verified change set.
- Push to the configured `origin` regularly after verified checkpoints and
  before ending a larger work session.
- If no remote exists yet, prepare the repo locally and document the exact
  commands needed to add `origin` and push `main`.
- Keep commit messages short and descriptive.

## Minimum Verification

- Python changes: run syntax or targeted execution checks.
- MATLAB changes: run the narrowest callable smoke test available.
- Documentation-only changes: ensure referenced paths and commands exist.

## Project Context

- rFactor 2 shared-memory plugin is the primary data path.
- Live telemetry requires the rFactor 2 client, not only the dedicated server.
- Mock mode is acceptable for plot development when the simulator is not
  running.
- Automation is currently keyboard-actuated; future analog actuator backends
  such as `vJoy` or `ViGEm` are valid extensions.
