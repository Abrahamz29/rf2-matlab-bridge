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
- ModDev `GDB/SCN/AIW/TDF/WET` scaffolding for each stage
- rFactor 2 GMT meshes for stages exported through the bundled Blender path

## GMT export path

Studio 397's developer documentation says track meshes for rFactor 2 are GMT
files exported from DCC tools via plugins. On this machine we now use a local
portable Blender 2.83 setup plus Traveller's rFactor 2 Blender exporter.

The downloaded Blender and exporter archives stay under ignored local
`tools/downloads/` paths. The reproducible project scripts are:

- `tools/Install-BlackLakeExportToolchain.ps1`
- `tools/Export-BlackLakeGmt.ps1`
- `tools/blender_export_blacklake.py`

Export and install the first real BlackLake stage:

```powershell
cd C:\Users\Victor\Documents\PYTHON\RFactor2
.\tools\Install-BlackLakeExportToolchain.ps1
.\tools\Export-BlackLakeGmt.ps1 -Stage 250m -InstallModDev
.\tools\Install-BlackLakeModDev.ps1 -Stage 250m -Mode Scaffold -RegisterSceneViewer
.\tools\Test-BlackLakeModDevInstall.ps1 -Stage 250m
```

The current `250m` stage has exported:

- `tracks/blacklake/source/250m/gmt/BlackLake_Surface.gmt`
- `tracks/blacklake/source/250m/gmt/BlackLake_Markings.gmt`

The `250m` ModDev install now also includes a stage-local
`BlackLake_250m.gdb` and a generated `BlackLake_250m.AIW`, so rFactor 2 has
start, teleport, pit, and waypoint data instead of relying on copied Joesville
session files.

At the moment `BlackLake` is still a loose `ModDev` location. That means it
does not show up in the normal retail single-player track search yet. For the
first drivable validation use:

```powershell
.\tools\Start-BlackLakeModDev.ps1 -Mode Viewer -Stage 250m
```

To prepare the first normal-game install package staging for MAS2:

```powershell
.\tools\Prepare-BlackLakePackage.ps1 -Stage 250m
```

For reference, on this machine we also have:

- `ModDev`
- `MAS2.exe`
- official 3ds Max exporter plugins

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

Install one generated stage into rFactor 2 ModDev after GMT export:

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
custom GMT export path is validated in-game.

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

## Remaining work

After the first GMT export, the remaining steps are:

1. validate `BlackLake_250m` visually in the ModDev viewer
2. test that `BlackLake 250m` is visible in ModDev track selection
3. test a player car on the 250m stage
4. refine the generated AIW if rFactor reports waypoint or garage issues
5. package as `.rfcmp` once the stage is stable
6. repeat export and validation for `500m`, `1000m`, and larger stages
