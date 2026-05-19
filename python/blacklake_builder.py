"""Build source assets and ModDev scaffolding for a custom BlackLake track.

This generator creates:
- parametric OBJ source geometry for a flat proving-ground surface
- lane marking geometry and CSV reference layouts
- a ModDev location scaffold (GDB/SCN/TDF/WET placeholders)

It does not convert geometry to GMT. rFactor 2 official docs state GMT meshes
are exported from DCC tools such as 3ds Max via plugins, so this generator
stops at source geometry and track text files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BLACKLAKE_ROOT = PROJECT_ROOT / "tracks" / "blacklake"
SOURCE_ROOT = BLACKLAKE_ROOT / "source"
MODDEV_ROOT = BLACKLAKE_ROOT / "moddev"

STAGES = {
    "250m": {"half_extent_m": 125.0, "lane_length_m": 220.0, "lane_width_m": 12.0},
    "500m": {"half_extent_m": 250.0, "lane_length_m": 440.0, "lane_width_m": 12.0},
    "1000m": {"half_extent_m": 500.0, "lane_length_m": 900.0, "lane_width_m": 12.0},
    "2000m": {"half_extent_m": 1000.0, "lane_length_m": 1800.0, "lane_width_m": 14.0},
    "5000m": {"half_extent_m": 2500.0, "lane_length_m": 4600.0, "lane_width_m": 16.0},
    "12000m": {"half_extent_m": 6000.0, "lane_length_m": 11000.0, "lane_width_m": 18.0},
}


@dataclass
class Quad:
    name: str
    points: List[Tuple[float, float, float]]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: Sequence[Sequence[object]], header: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def quad(x0: float, z0: float, x1: float, z1: float, y: float = 0.0, name: str = "quad") -> Quad:
    return Quad(
        name=name,
        points=[
            (x0, y, z0),
            (x1, y, z0),
            (x1, y, z1),
            (x0, y, z1),
        ],
    )


def build_surface_quads(half_extent_m: float) -> List[Quad]:
    return [quad(-half_extent_m, -half_extent_m, half_extent_m, half_extent_m, name="BlackLake_Surface")]


def build_marking_quads(half_extent_m: float, lane_length_m: float, lane_width_m: float) -> List[Quad]:
    stripe = 0.15
    gap = lane_width_m / 2.0
    end_margin = min(half_extent_m - 5.0, lane_length_m / 2.0)
    quads: List[Quad] = []

    # Cross axes
    quads.append(quad(-stripe / 2, -end_margin, stripe / 2, end_margin, 0.01, "Axis_NS"))
    quads.append(quad(-end_margin, -stripe / 2, end_margin, stripe / 2, 0.01, "Axis_EW"))

    # Main maneuver lane boundaries
    quads.append(quad(-gap - stripe, -end_margin, -gap, end_margin, 0.01, "Lane_W"))
    quads.append(quad(gap, -end_margin, gap + stripe, end_margin, 0.01, "Lane_E"))

    # Launch box
    launch_half = lane_width_m / 2.0
    launch_len = min(40.0, end_margin / 3.0)
    quads.append(quad(-launch_half, -launch_len, launch_half, -launch_len + stripe, 0.01, "Launch_Rear"))
    quads.append(quad(-launch_half, launch_len - stripe, launch_half, launch_len, 0.01, "Launch_Front"))
    quads.append(quad(-launch_half, -launch_len, -launch_half + stripe, launch_len, 0.01, "Launch_Left"))
    quads.append(quad(launch_half - stripe, -launch_len, launch_half, launch_len, 0.01, "Launch_Right"))

    # Skidpad ring markings
    quads.extend(build_ring_markers(radius=40.0, width=0.25, segments=64, name="Skidpad_40m"))
    quads.extend(build_ring_markers(radius=80.0, width=0.25, segments=96, name="Skidpad_80m"))
    return quads


def build_ring_markers(radius: float, width: float, segments: int, name: str) -> List[Quad]:
    quads: List[Quad] = []
    for idx in range(segments):
        angle0 = (2.0 * math.pi * idx) / segments
        angle1 = (2.0 * math.pi * (idx + 1)) / segments
        r0 = radius - (width / 2.0)
        r1 = radius + (width / 2.0)
        points = [
            (r0 * math.cos(angle0), 0.01, r0 * math.sin(angle0)),
            (r1 * math.cos(angle0), 0.01, r1 * math.sin(angle0)),
            (r1 * math.cos(angle1), 0.01, r1 * math.sin(angle1)),
            (r0 * math.cos(angle1), 0.01, r0 * math.sin(angle1)),
        ]
        quads.append(Quad(name=f"{name}_{idx:03d}", points=points))
    return quads


def write_obj(path: Path, quads: Sequence[Quad], material_name: str) -> None:
    lines = [f"mtllib {path.with_suffix('.mtl').name}"]
    vertex_count = 0
    for mesh in quads:
        lines.append(f"o {mesh.name}")
        lines.append(f"usemtl {material_name}")
        for x, y, z in mesh.points:
            lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
        lines.append(f"f {vertex_count + 1} {vertex_count + 2} {vertex_count + 3} {vertex_count + 4}")
        vertex_count += 4
    write_text(path, "\n".join(lines) + "\n")


def write_mtl(path: Path, material_name: str, kd: Tuple[float, float, float]) -> None:
    lines = [
        f"newmtl {material_name}",
        "Ka 0.000000 0.000000 0.000000",
        f"Kd {kd[0]:.6f} {kd[1]:.6f} {kd[2]:.6f}",
        "Ks 0.000000 0.000000 0.000000",
        "d 1.0",
        "illum 1",
    ]
    write_text(path, "\n".join(lines) + "\n")


def build_waypoints(lane_length_m: float, sample_spacing_m: float = 5.0) -> List[Tuple[float, float, float, str]]:
    rows: List[Tuple[float, float, float, str]] = []
    half_length = lane_length_m / 2.0
    num_points = max(2, int(lane_length_m / sample_spacing_m) + 1)
    for index in range(num_points):
        z = -half_length + ((lane_length_m * index) / (num_points - 1))
        rows.append((0.0, 0.0, z, "fast_path"))
    return rows


def build_markers(half_extent_m: float, lane_length_m: float) -> List[Tuple[str, float, float, float]]:
    end_margin = min(half_extent_m - 5.0, lane_length_m / 2.0)
    return [
        ("origin", 0.0, 0.0, 0.0),
        ("north_limit", 0.0, 0.0, end_margin),
        ("south_limit", 0.0, 0.0, -end_margin),
        ("east_limit", end_margin, 0.0, 0.0),
        ("west_limit", -end_margin, 0.0, 0.0),
        ("skidpad_40m", 40.0, 0.0, 0.0),
        ("skidpad_80m", 80.0, 0.0, 0.0),
    ]


def build_stage(stage_name: str, stage: dict[str, float], root: Path) -> None:
    stage_root = root / stage_name
    geometry_root = stage_root / "geometry"
    layout_root = stage_root / "layout"
    moddev_root = stage_root / "moddev" / "BlackLake"

    half_extent = stage["half_extent_m"]
    lane_length = stage["lane_length_m"]
    lane_width = stage["lane_width_m"]

    surface_obj = geometry_root / "BlackLake_Surface.obj"
    surface_mtl = geometry_root / "BlackLake_Surface.mtl"
    markings_obj = geometry_root / "BlackLake_Markings.obj"
    markings_mtl = geometry_root / "BlackLake_Markings.mtl"

    write_obj(surface_obj, build_surface_quads(half_extent), "BlackLakeAsphalt")
    write_mtl(surface_mtl, "BlackLakeAsphalt", (0.11, 0.11, 0.11))
    write_obj(markings_obj, build_marking_quads(half_extent, lane_length, lane_width), "BlackLakePaint")
    write_mtl(markings_mtl, "BlackLakePaint", (0.92, 0.92, 0.92))

    write_csv(
        layout_root / "waypoints_fast_path.csv",
        build_waypoints(lane_length),
        ["x_m", "y_m", "z_m", "path_type"],
    )
    write_csv(
        layout_root / "markers.csv",
        build_markers(half_extent, lane_length),
        ["name", "x_m", "y_m", "z_m"],
    )
    write_text(layout_root / "README.md", layout_readme(stage_name, half_extent, lane_length, lane_width))

    write_text(moddev_root / "BlackLake.tdf", blacklake_tdf())
    write_text(moddev_root / "BlackLake.gdb", blacklake_gdb(stage_name, lane_length))
    layout_folder = moddev_root / f"BlackLake_{stage_name}"
    write_text(layout_folder / f"BlackLake_{stage_name}.scn", blacklake_scn(stage_name))
    write_text(layout_folder / f"BlackLake_{stage_name}.wet", blacklake_wet())
    write_text(layout_folder / "README.md", moddev_readme(stage_name))

    manifest = {
        "stage": stage_name,
        "half_extent_m": half_extent,
        "lane_length_m": lane_length,
        "lane_width_m": lane_width,
        "generated_files": [
            str(surface_obj.relative_to(PROJECT_ROOT)),
            str(markings_obj.relative_to(PROJECT_ROOT)),
            str((layout_root / "waypoints_fast_path.csv").relative_to(PROJECT_ROOT)),
            str((layout_root / "markers.csv").relative_to(PROJECT_ROOT)),
            str((moddev_root / "BlackLake.tdf").relative_to(PROJECT_ROOT)),
            str((layout_folder / f"BlackLake_{stage_name}.scn").relative_to(PROJECT_ROOT)),
            str((layout_folder / f"BlackLake_{stage_name}.wet").relative_to(PROJECT_ROOT)),
            str((layout_folder / "README.md").relative_to(PROJECT_ROOT)),
        ],
    }
    write_text(stage_root / "manifest.json", json.dumps(manifest, indent=2) + "\n")


def layout_readme(stage_name: str, half_extent_m: float, lane_length_m: float, lane_width_m: float) -> str:
    return f"""# BlackLake {stage_name}

This folder contains generated source geometry and layout references for the
custom BlackLake proving-ground stage `{stage_name}`.

Geometry:
- `BlackLake_Surface.obj`: flat asphalt plane
- `BlackLake_Markings.obj`: lane and skidpad paint geometry

Layout references:
- `waypoints_fast_path.csv`: seed path for AIW authoring
- `markers.csv`: origin, limits, and skidpad reference points

Stage parameters:
- half extent: {half_extent_m:.1f} m
- lane length: {lane_length_m:.1f} m
- lane width: {lane_width_m:.1f} m

These OBJ files still need to be imported into a GMT-capable authoring tool and
exported as GMT before rFactor 2 can load them as drivable terrain.
"""


def blacklake_tdf() -> str:
    return """[FEEDBACK]
Dry=1.0
Wet=0.85
Resistance=0.0
BumpAmp=0.0
BumpWavelen=8.0
Legal=false
Spring=0.0
Damper=0.0
CollFrict=1.00
Sparks=0
Scraping=0
Sink=0.0
Sound=dry
Tex=asphalt
Max=0

[BLACKLAKE_ASPHALT]
Dry=1.00
Wet=0.85
Resistance=0.0
BumpAmp=0.0
BumpWavelen=8.0
Legal=true
Spring=0.0
Damper=0.0
CollFrict=1.00
Sparks=0
Scraping=0
Sink=0.0
Sound=dry
Tex=asphalt
Max=0
Reaction=tiresmoke Tex=SMOKETire.tga Max=1024 Scale=(0.5,0.5,0.5) Growth=(2.5,2.0,2.0) ASDEnvelope=(0.1,0.7,3.8) Suspension=0.98 DestBlend=InvSrcAlpha SrcBlend=SrcAlpha

[BLACKLAKE_GRASS]
Dry=0.80
Wet=0.60
Resistance=8000.0
BumpAmp=0.010
BumpWavelen=2.5
Legal=true
Spring=0.0
Damper=0.0
CollFrict=0.95
Sparks=0
Scraping=0
Sink=0.0
Sound=grass
Tex=grass
Max=0
"""


def blacklake_gdb(stage_name: str, lane_length_m: float) -> str:
    km = lane_length_m / 1000.0
    return f"""BlackLake_{stage_name}
{{
  TrackName = BlackLake {stage_name}
  EventName = BlackLake Proving Ground {stage_name}
  VenueName = BlackLake
  Location = Synthetic Test Facility
  Length = {km:.3f} KM
  TrackType = Test Track
  TerrainDataFile=..\\BlackLake.tdf
  HeadlightsRequired = false
  Max Vehicles = 20
  RaceLaps = 3
  RaceTime = 30
  TestDayStart = 12:00
  Latitude = 0.0
  Longitude = 0.0
  Altitude = 0.0
  RaceDate = June 1, 2026
  TimezoneRelativeGMT = 0.0
  SettingsFolder = BlackLake
  SettingsCopy = BlackLake.svm
  SettingsAI = BlackLake.svm
}}
"""


def blacklake_scn(stage_name: str) -> str:
    stage_folder = f"BLACKLAKE_{stage_name.upper()}"
    return f"""SearchPath=.
SearchPath=BLACKLAKE
SearchPath=BLACKLAKE\\{stage_folder}
SearchPath=BLACKLAKE\\ASSETS\\GMT
SearchPath=BLACKLAKE\\ASSETS\\MAPS
SearchPath=JOESVILLE\\ASSETS\\GMT
SearchPath=JOESVILLE\\ASSETS\\MAPS
MASFile=COMMONMAPS.MAS

View=mainview
{{
  Clear=False
  Color=(0, 0, 0)
  Size=(1.00, 1.00) Center=(0.5, 0.5)
  FOV=(77.75, 31.25)
  ClipPlanes=(0.50, 20000.00)
}}

GroupMethod=Dynamic
MaxShadowRange=(900.00)
AmbientColor=(126, 126, 126)
ReflectPlane=(0.000, 1.000, 0.000, 0.000)
FogMode=LINEAR FogIn=(800.00) FogOut=(18000.00) FogDensity=(0.00002) FogColor=(205, 215, 235)

Light=Direct00
{{
 Type=Directional Color=(220, 220, 220) Dir=(0.5, -0.9, 0.5)
}}

// The following GMT names are placeholders for source geometry exported from
// tracks/blacklake/source/{stage_name}/geometry/*.obj through a GMT-capable DCC tool.

Instance=BlackLake_Surface
{{
  MeshFile=BlackLake_Surface.gmt Deformable=True CollTarget=True HATTarget=True
}}

Instance=BlackLake_Markings
{{
  MeshFile=BlackLake_Markings.gmt CollTarget=False HATTarget=False
}}

Instance=SkyBoxi
{{
  Planes=(4) ReflectPlane=(0.000, 1.000, 0.000, 0.000)
  MeshFile=SkyBoxi.gmt CollTarget=False HATTarget=False Reflect=True
}}

ReflectionMapper=STATIC01
{{
  Type=Cubic
  TextureSize=(512)
  UpdateRate=(0.100)
  StaticSwitch=(100.000)
  Pos=(0.000000,0.000000,0.000000)
  IncludeIns=BlackLake_Surface
  IncludeIns=BlackLake_Markings
}}

ReflectionMapper=REFMAP0
{{
  Type=Cubic
  TextureSize=(1024)
  UpdateRate=(100.000)
  StaticSwitch=(100.000)
  TrackingIns=True
  IncludeIns=BlackLake_Surface
  IncludeIns=BlackLake_Markings
  IncludeIns=SkyBoxi
}}
"""


def blacklake_wet() -> str:
    return """[HEADER]
RoadWetness=(0.0)
RealRoadRate=(1.0)
Cloudiness=(0.1)
RainDensity=(0.0)
AmbientTemp=(24.0)
TrackTemp=(28.0)
WindSpeed=(1.0)
"""


def moddev_readme(stage_name: str) -> str:
    return f"""# BlackLake ModDev Scaffold ({stage_name})

This folder is a text scaffold for the custom BlackLake proving ground.

What is ready:
- `BlackLake.tdf`
- `BlackLake.gdb`
- `BlackLake_{stage_name}.scn`
- `BlackLake_{stage_name}.wet`

What is still required before rFactor 2 can load and drive it:
- export or copy `BlackLake_Surface.gmt`
- export or copy `BlackLake_Markings.gmt`
- create `AIW` in ModDev AI editor
- package as `.rfcmp`

This repository can export GMT for the generated BlackLake geometry with
`tools\\Export-BlackLakeGmt.ps1`.
"""


def project_readme() -> str:
    lines = [
        "# BlackLake",
        "",
        "Custom proving-ground authoring workspace for rFactor 2.",
        "",
        "Generated stages:",
    ]
    for stage_name, stage in STAGES.items():
        lines.append(
            f"- `{stage_name}`: half extent {stage['half_extent_m']:.0f} m, "
            f"lane length {stage['lane_length_m']:.0f} m"
        )
    lines += [
        "",
        "Build source scaffolding:",
        "",
        "```powershell",
        '& "C:\\Users\\Victor\\.platformio\\penv\\Scripts\\python.exe" .\\python\\blacklake_builder.py --all',
        "```",
        "",
        "The generator creates geometry source and ModDev text scaffolding.",
        "Export GMT for a stage with:",
        "",
        "```powershell",
        ".\\tools\\Export-BlackLakeGmt.ps1 -Stage 250m -InstallModDev",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build custom BlackLake source geometry and ModDev scaffolding")
    parser.add_argument("--stage", choices=sorted(STAGES.keys()), help="Single stage to generate")
    parser.add_argument("--all", action="store_true", help="Generate all configured stages")
    args = parser.parse_args()

    if not args.all and not args.stage:
        parser.error("Specify --stage <name> or --all")

    write_text(BLACKLAKE_ROOT / "README.md", project_readme())
    write_text(BLACKLAKE_ROOT / "stages.json", json.dumps(STAGES, indent=2) + "\n")

    targets = STAGES.keys() if args.all else [args.stage]
    for stage_name in targets:
        build_stage(stage_name, STAGES[stage_name], SOURCE_ROOT)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
