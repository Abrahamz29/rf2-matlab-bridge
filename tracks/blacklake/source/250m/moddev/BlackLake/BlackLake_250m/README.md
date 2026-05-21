# BlackLake ModDev Scaffold (250m)

This folder is a text scaffold for the custom BlackLake proving ground.

What is ready:
- `BlackLake.tdf`
- `BlackLake.gdb`
- `BlackLake_250m.gdb`
- `BlackLake_250m.scn`
- `BlackLake_250m.AIW`
- `BlackLake_250m.wet`

What is still required before rFactor 2 can load and drive it:
- export or copy `BlackLake_Surface.gmt`
- export or copy `BlackLake_Markings.gmt`
- export or copy `BlackLake_Reference.gmt`
- export or copy mandatory timing trigger GMTs: `xfinish.gmt`, `xsector1.gmt`,
  `xsector2.gmt`, `xpitin.gmt`, `xpitout.gmt`
- package as `.rfcmp`

This repository can export GMT for the generated BlackLake geometry with
`tools\Export-BlackLakeGmt.ps1`.
