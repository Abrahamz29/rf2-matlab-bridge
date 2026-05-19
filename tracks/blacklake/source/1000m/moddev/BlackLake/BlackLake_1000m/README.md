# BlackLake ModDev Scaffold (1000m)

This folder is a text scaffold for the custom BlackLake proving ground.

What is ready:
- `BlackLake.tdf`
- `BlackLake.gdb`
- `BlackLake_1000m.scn`
- `BlackLake_1000m.wet`

What is still required before rFactor 2 can load and drive it:
- export `BlackLake_Surface.obj` to `BlackLake_Surface.gmt`
- export `BlackLake_Markings.obj` to `BlackLake_Markings.gmt`
- add any textures/materials into `Assets\Maps`
- create `AIW` in ModDev AI editor
- package as `.rfcmp`

Official Studio 397 documentation states GMT meshes are exported from DCC tools
via plugins. This repository currently generates the source geometry and the
track text files, but not the final GMT binaries.
