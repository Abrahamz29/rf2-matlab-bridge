# BlackLake 12000m

This folder contains generated source geometry and layout references for the
custom BlackLake proving-ground stage `12000m`.

Geometry:
- `BlackLake_Surface.obj`: flat asphalt plane
- `BlackLake_Markings.obj`: lane and skidpad paint geometry

Layout references:
- `waypoints_fast_path.csv`: seed path for AIW authoring
- `markers.csv`: origin, limits, and skidpad reference points

Stage parameters:
- half extent: 6000.0 m
- lane length: 11000.0 m
- lane width: 18.0 m

These OBJ files still need to be imported into a GMT-capable authoring tool and
exported as GMT before rFactor 2 can load them as drivable terrain.
