# BlackLake Authoring

## Status

`BlackLake` is now scaffolded as a custom proving-ground project inside this
repository:

- `tracks/blacklake/README.md`
- `tracks/blacklake/stages.json`
- `python/blacklake_builder.py`

The generator creates:

- flat proving-ground OBJ source geometry
- lane/skidpad markings OBJ geometry
- waypoint and marker CSV references
- ModDev `GDB/SCN/TDF/WET` scaffolding for each stage

## Why this stops before GMT

Studio 397's developer documentation says track meshes for rFactor 2 are GMT
files exported from DCC tools via plugins. On this machine we currently have:

- `ModDev`
- `MAS2.exe`
- official 3ds Max exporter plugins

But we do not have an installed GMT-capable DCC authoring tool such as 3ds Max
configured for export. That means we can generate source geometry ourselves,
but we cannot complete the final `OBJ -> GMT` conversion locally right now.

Primary references:

- Track structure:
  https://docs.studio-397.com/display/DG/Track%2BStructure
- Scene file:
  https://docs.studio-397.com/pages/viewpage.action?pageId=37945743
- GMT converter / exporter:
  https://docs.studio-397.com/display/DG/GMT%2BConverter

## Build the stages

Generate every BlackLake stage:

```powershell
cd C:\Users\Victor\Documents\PYTHON\RFactor2
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\python\blacklake_builder.py --all
```

Generate only the first validation stage:

```powershell
& "C:\Users\Victor\.platformio\penv\Scripts\python.exe" .\python\blacklake_builder.py --stage 250m
```

Install one generated stage into rFactor 2 ModDev:

```powershell
.\tools\Install-BlackLakeModDev.ps1 -Stage 250m
```

Install a directly loadable BlackLake baseline in ModDev by reusing the loose
`Joesville` developer assets already present on this machine:

```powershell
.\tools\Install-BlackLakeModDev.ps1 -Stage 250m -Mode JoesvilleBaseline -RegisterSceneViewer
```

This baseline is intentionally not the final geometry. It exists to get a
named `BlackLake` location loading in ModDev now, so controller logic,
telemetry, MATLAB plots, and session plumbing can be developed before the
custom `OBJ -> GMT` export path is solved.

## Current stage ladder

- `250m`
- `500m`
- `1000m`
- `2000m`
- `5000m`
- `12000m`

The `12000m` stage is the first one aligned with the long-term requirement of
roughly 60 s straight-line maneuver space at around 300 km/h from a central
test area.

## Next blocking step

To make the custom BlackLake actually load in rFactor 2, we still need one of:

1. a local 3ds Max + rFactor 2 exporter setup
2. another proven GMT-capable pipeline

After GMT export, the remaining steps are straightforward:

1. copy GMT/maps into the generated ModDev scaffold
2. create AIW in ModDev
3. test in ModDev
4. package as `.rfcmp`
