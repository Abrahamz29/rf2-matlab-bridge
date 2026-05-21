"""Build source assets and ModDev scaffolding for a custom BlackLake track.

This generator creates:
- parametric OBJ source geometry for a flat proving-ground surface
- lane marking geometry and CSV reference layouts
- a ModDev location scaffold (GDB/SCN/AIW/TDF/WET)

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
            (x0, y, z1),
            (x1, y, z1),
            (x1, y, z0),
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
            (r0 * math.cos(angle1), 0.01, r0 * math.sin(angle1)),
            (r1 * math.cos(angle1), 0.01, r1 * math.sin(angle1)),
            (r1 * math.cos(angle0), 0.01, r1 * math.sin(angle0)),
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

    layout_folder = moddev_root / f"BlackLake_{stage_name}"
    write_text(moddev_root / "BlackLake.tdf", blacklake_tdf())
    write_text(layout_folder / f"BlackLake_{stage_name}.gdb", blacklake_gdb(stage_name, lane_length))
    write_text(layout_folder / f"BlackLake_{stage_name}.scn", blacklake_scn(stage_name))
    write_text(layout_folder / f"BlackLake_{stage_name}.AIW", blacklake_aiw(stage_name, half_extent, lane_length, lane_width))
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
            str((layout_folder / f"BlackLake_{stage_name}.gdb").relative_to(PROJECT_ROOT)),
            str((layout_folder / f"BlackLake_{stage_name}.scn").relative_to(PROJECT_ROOT)),
            str((layout_folder / f"BlackLake_{stage_name}.AIW").relative_to(PROJECT_ROOT)),
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
    return """// BlackLake terrain feedback.
// Keep this close to the rFactor 2 Joesville sample TDF format; overly sparse
// feedback blocks can crash the client during SpecialFX initialization.
// NOTE: The current feedback materials intentionally do not match the generated
// BlackLakeAsphalt/BlackLakePaint GMT materials. Matching them currently causes
// the retail client to crash during load. Until the material/TDF contract is
// fixed, rFactor 2 will warn and fall back to default feedback for load tests.

[TRACKVARS]
RoadDryGrip=1.00
RoadWetGrip=0.85
RoadBumpAmp=0.001
RoadBumpLen=3.0
HATFilterMaxOffset=0.003

// Flat proving-ground asphalt.
[FEEDBACK]
Wear=1.05 Dry=1.02 Wet=0.80 Roughness=(0.50,0.25) Resistance=0 BumpAmp=RoadBumpAmp BumpWavelen=RoadBumpLen Legal=true Spring=0 Damper=0 CollFrict=0.40 Sparks=1 Scraping=1 Sink=-0.003 Sound=dry
Reaction=tiresmoke Tex=SMOKETire.tga Max=1024 Scale=(0.5,0.5,0.5) Growth=(2.5,2.0,2.0) ASDEnvelope=(0.1,0.7,3.8) Suspension=0.98 DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Reaction=skid Tex=skidhard.tga Max=2500 Pixel=NoReduceDetail Particle=Plane+Deformable+SingleSided DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Reaction=wetskid Tex=skidwet.tga Max=1024 Duration=0.40 Pixel=NoReduceDetail Particle=Plane+Deformable+SingleSided DestBlend=One SrcBlend=SrcAlpha
Reaction=spray Tex=rainspray.tga Max=1024 Scale=(1.3,0.02,0.02) Growth=(2.0,0.19,0.19) GrowthVel=(0.17,0.13,0.13) Power=0.41 RampSpeed=90 OffsetVel=0.10 ASDEnvelope=(0.01,3.0,2.0) DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Materials=unused_asph

// Painted lane and reference markings.
[FEEDBACK]
Wear=0.85 Dry=0.88 Wet=0.50 Roughness=(0.45,0.02) Resistance=0 BumpAmp=0.002 BumpWavelen=5 Legal=true Spring=0 Damper=0 CollFrict=0.20 Sparks=1 Scraping=1 OnTop=0.0015 Sound=dry
Reaction=tiresmoke Tex=SMOKETire.tga Max=1024 Scale=(0.5,0.5,0.5) Growth=(2.5,2.0,2.0) ASDEnvelope=(0.1,0.7,3.8) Suspension=0.98 DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Reaction=skid Tex=skidhard.tga Max=2500 Pixel=NoReduceDetail Particle=Plane+Deformable+SingleSided DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Reaction=wetskid Tex=skidwet.tga Max=1024 Duration=0.40 Pixel=NoReduceDetail Particle=Plane+Deformable+SingleSided DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Reaction=spray Tex=rainspray.tga Max=1024 Scale=(1.3,0.02,0.02) Growth=(2.0,0.19,0.19) GrowthVel=(0.17,0.13,0.13) Power=0.41 RampSpeed=70 OffsetVel=0.10 ASDEnvelope=(0.01,3.0,2.0) DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Materials=unused_strp

// Optional grass/off-surface material for future larger stages.
[FEEDBACK]
Wear=0.60 Dry=0.50 Wet=0.30 Resistance=2000 BumpAmp=0.039 BumpWavelen=2.0 Legal=false Spring=300 Damper=300 CollFrict=2 Sparks=0 Scraping=0 Sink=0.032 Sound=grass
Reaction=softskid Tex=skidgreen.tga Max=1024 Pixel=NoReduceDetail Particle=Plane+Deformable+SingleSided DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Reaction=dust Tex=DIRT_Cloud.tga Max=128 TopSpeed=105 Scale=(1.4,1.0,1.0) Growth=(3.0,2.0,2.0) Suspension=0.847 ASDEnvelope=(1.0,2.0,3.5) DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Reaction=dirt Tex=GrassDirtKick.tga Max=64 Scale=(0.7,0.7,0.7) Growth=(0.85,0.85,0.85) Suspension=0.693 ASDEnvelope=(0.2,0.8,0.2) DestBlend=InvSrcAlpha SrcBlend=SrcAlpha
Materials=gras
"""


def blacklake_gdb(stage_name: str, lane_length_m: float) -> str:
    km = lane_length_m / 1000.0
    return f"""BlackLake_{stage_name}
{{
  Filter Properties = rFRS TMOD NSCRS
  Attrition = 0
  TrackName = BlackLake {stage_name}
  EventName = BlackLake Proving Ground {stage_name}
  VenueName = BlackLake
  Location = Synthetic Test Facility
  Length = {km:.3f} KM
  TrackType = Test Track
  TerrainDataFile=..\\BlackLake.tdf
  HeadlightsRequired = false
  Max Vehicles = 104
  FormationAndStart=0
  PitlaneBoundary = 1
  RacePitKPH = 80.0
  NormalPitKPH = 80.0
  FormationSpeedKPH = 80.0
  RaceLaps = 3
  RaceTime = 30
  NumStartingLights = 2
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


def blacklake_aiw(stage_name: str, half_extent_m: float, lane_length_m: float, lane_width_m: float) -> str:
    half_lane = lane_length_m / 2.0
    usable_half = max(20.0, min(half_extent_m - 15.0, half_lane - 10.0))
    loop_half_width = min(max(lane_width_m * 3.0, 30.0), max(10.0, half_extent_m - 25.0))
    spawn_z = -min(usable_half - 15.0, 70.0)
    spawn_y = 0.55
    pit_y = 0.0
    grid_count = 104
    grid_columns = 8
    grid_x_spacing = max(4.0, lane_width_m * 0.42)
    grid_z_spacing = max(4.5, lane_width_m * 0.42)
    pit_count = 52
    pit_columns = 4
    pit_x_spacing = max(4.0, lane_width_m * 0.42)
    pit_z_spacing = max(5.0, lane_width_m * 0.50)

    grid_lines = []
    for index in range(grid_count):
        row = index // grid_columns
        column = index % grid_columns
        x = (column - (grid_columns - 1) / 2.0) * grid_x_spacing
        z = spawn_z + row * grid_z_spacing
        grid_lines.extend([
            f"GridIndex={index}",
            f"Pos=({x:.3f},{spawn_y:.3f},{z:.3f})",
            "Ori=(0.000,0.000,0.000)",
        ])

    pits = []
    pit_positions = []
    pit_x_origin = -loop_half_width + 6.0
    for team in range(pit_count):
        row = team // pit_columns
        column = team % pit_columns
        x = pit_x_origin + column * pit_x_spacing
        z = spawn_z + row * pit_z_spacing
        pit_positions.append((x, pit_y, z))
        pits.extend([
            f"TeamIndex={team}",
            f"PitPos=({x:.3f},{pit_y:.3f},{z:.3f})",
            "PitOri=(0.000,0.000,0.000)",
            f"GarPos=(0,{x - 3.0:.3f},{pit_y:.3f},{z - 1.5:.3f})",
            "GarOri=(0,0.000,0.000,0.000)",
            f"GarPos=(1,{x - 3.0:.3f},{pit_y:.3f},{z:.3f})",
            "GarOri=(1,0.000,0.000,0.000)",
            f"GarPos=(2,{x - 3.0:.3f},{pit_y:.3f},{z + 1.5:.3f})",
            "GarOri=(2,0.000,0.000,0.000)",
        ])

    waypoint_spacing = max(10.0, min(100.0, usable_half / 20.0))
    points = rectangular_waypoints(loop_half_width, usable_half, spacing=waypoint_spacing)
    pit_lane_points: List[Tuple[float, float, float]] = []
    pit_lane_local_by_team: dict[int, int] = {}
    for row in range(math.ceil(pit_count / pit_columns)):
        columns = range(pit_columns) if row % 2 == 0 else range(pit_columns - 1, -1, -1)
        for column in columns:
            team = row * pit_columns + column
            if team >= pit_count:
                continue
            x, y, z = pit_positions[team]
            pit_lane_local_by_team[team] = len(pit_lane_points)
            pit_lane_points.append((x + 1.5, y, z + 2.0))

    pit_lane_start_index = len(points)
    pit_entry_index = nearest_waypoint_index(points, pit_lane_points[0])
    pit_exit_index = nearest_waypoint_index(points, pit_lane_points[-1])
    branch_links = {pit_entry_index: pit_lane_start_index}
    special_branch_start_index = pit_lane_start_index + len(pit_lane_points)
    pit_lane_links = {
        pit_lane_local_by_team[team]: special_branch_start_index + team * 2
        for team in range(pit_count)
    }
    special_waypoint_lines: List[str] = []
    for team, (x, y, z) in enumerate(pit_positions):
        pit_lane_global_index = pit_lane_start_index + pit_lane_local_by_team[team]
        branch_start_index = special_branch_start_index + team * 2
        special_waypoint_lines.extend(
            blacklake_waypoint_lines(
                [(x, y, z), (x - 3.0, y, z)],
                lane_width_m,
                loop_half_width,
                usable_half,
                start_index=branch_start_index,
                circular=False,
                branch_id=team + 2,
                pitlane=1,
                first_prev_index=pit_lane_global_index,
                last_next_index=pit_lane_global_index,
            )
        )
    waypoint_lines = [
        *blacklake_waypoint_lines(
            points,
            lane_width_m,
            loop_half_width,
            usable_half,
            branch_links=branch_links,
        ),
        *blacklake_waypoint_lines(
            pit_lane_points,
            lane_width_m,
            loop_half_width,
            usable_half,
            start_index=pit_lane_start_index,
            circular=False,
            branch_id=1,
            pitlane=1,
            first_prev_index=pit_entry_index,
            last_next_index=pit_exit_index,
            branch_links=pit_lane_links,
        ),
        *special_waypoint_lines,
    ]

    return "\n".join([
        "//[[gMa1.002f (c)2015    ]] [[            ]]",
        "[Features]",
        "pitlanes=1",
        f"startinggrid={grid_count}",
        f"pitspots={pit_count}",
        "garagespots=3",
        "auxspots=8",
        "acceptabledriverlinenoise=1.000000",
        "StartingStretch=20.000000",
        "definepath=FASTEST",
        "pathtime=60.0000",
        "definepath=LEFT",
        "pathtime=60.0000",
        "definepath=RIGHT",
        "pathtime=60.0000",
        "",
        "[GRID]",
        *grid_lines,
        "",
        "[ALTGRID]",
        *grid_lines,
        "",
        "[TELEPORT]",
        *grid_lines,
        "",
        "[PITS]",
        *pits,
        "",
        "[AUX]",
        *aux_lines(spawn_y),
        "",
        "[Waypoint]",
        "trackstate=4507",
        "drivinglines=1",
        f"autogengridf=(0.0,{lane_width_m:.2f})",
        f"teleportwp=({max(0, len(points) // 4)})",
        "pitlanepaths=(2,3)",
        f"number_waypoints={len(points) + len(pit_lane_points) + pit_count * 2}",
        f"lap_length={rectangular_lap_length(loop_half_width, usable_half):.6f}",
        f"sector_1_length={rectangular_lap_length(loop_half_width, usable_half) / 3.0:.6f}",
        f"sector_2_length={2.0 * rectangular_lap_length(loop_half_width, usable_half) / 3.0:.6f}",
        "LeftHandedPits=1",
        "FuelUse=10000.000000",
        "AIBrakingStiffness=(1.0000,1.0000,0.9000)",
        "slowwhenpushed=1.00",
        "DelayPitCrewLoad=0",
        f"LaneSpacing={lane_width_m:.2f}",
        "WorstAdjust=(0.8000)",
        "MidAdjust=(1.0000)",
        "BestAdjust=(1.2000)",
        "AIRange=(0.1000)",
        "AISpec=(0.0000,0.0000,1.0000,0.0000)",
        *waypoint_lines,
        "",
    ])


def rectangular_waypoints(half_width: float, half_length: float, spacing: float) -> List[Tuple[float, float, float]]:
    corners = [
        (-half_width, 0.0, -half_length),
        (half_width, 0.0, -half_length),
        (half_width, 0.0, half_length),
        (-half_width, 0.0, half_length),
    ]
    points: List[Tuple[float, float, float]] = []
    for start, end in zip(corners, corners[1:] + corners[:1]):
        sx, sy, sz = start
        ex, ey, ez = end
        length = math.hypot(ex - sx, ez - sz)
        steps = max(1, int(length / spacing))
        for step in range(steps):
            alpha = step / steps
            points.append((sx + (ex - sx) * alpha, sy + (ey - sy) * alpha, sz + (ez - sz) * alpha))
    return points


def straight_waypoints(x: float, z0: float, z1: float, spacing: float) -> List[Tuple[float, float, float]]:
    length = abs(z1 - z0)
    steps = max(2, int(length / spacing) + 1)
    points: List[Tuple[float, float, float]] = []
    for step in range(steps):
        alpha = step / (steps - 1)
        points.append((x, 0.0, z0 + (z1 - z0) * alpha))
    return points


def aux_lines(spawn_y: float) -> List[str]:
    positions = [
        (-18.0, 0.0),
        (-12.0, 0.0),
        (-6.0, 0.0),
        (0.0, 0.0),
        (6.0, 0.0),
        (12.0, 0.0),
        (18.0, 0.0),
        (24.0, 0.0),
    ]
    lines: List[str] = []
    for index, (x, z) in enumerate(positions):
        lines.extend([
            f"LocationIndex={index}",
            f"Pos=({x:.3f},{spawn_y:.3f},{z:.3f})",
            "Ori=(0.000,0.000,0.000)",
        ])
    return lines


def nearest_waypoint_index(
    points: Sequence[Tuple[float, float, float]],
    target: Tuple[float, float, float],
) -> int:
    target_x, _target_y, target_z = target
    return min(
        range(len(points)),
        key=lambda index: math.hypot(points[index][0] - target_x, points[index][2] - target_z),
    )


def rectangular_lap_length(half_width: float, half_length: float) -> float:
    return 4.0 * (half_width + half_length)


def blacklake_waypoint_lines(
    points: Sequence[Tuple[float, float, float]],
    lane_width_m: float,
    loop_half_width: float,
    loop_half_length: float,
    *,
    start_index: int = 0,
    circular: bool = True,
    branch_id: int = 0,
    pitlane: int = 0,
    first_prev_index: int | None = None,
    last_next_index: int | None = None,
    branch_links: dict[int, int] | None = None,
) -> List[str]:
    if not points:
        return []

    lines: List[str] = []
    distance = 0.0
    total_length = rectangular_lap_length(loop_half_width, loop_half_length)
    branch_links = branch_links or {}
    path_offsets = [
        (0, 0.0),
        (1, -lane_width_m * 0.35),
        (2, lane_width_m * 0.35),
    ]
    for index, (x, y, z) in enumerate(points):
        global_index = start_index + index
        if circular:
            prev_index = start_index + ((index - 1) % len(points))
            next_index = start_index + ((index + 1) % len(points))
            nx, _ny, nz = points[(index + 1) % len(points)]
        else:
            prev_index = first_prev_index if index == 0 and first_prev_index is not None else global_index - 1
            next_index = last_next_index if index == len(points) - 1 and last_next_index is not None else global_index + 1
            if index == len(points) - 1 and len(points) > 1:
                px, _py, pz = points[index - 1]
                nx, nz = x + (x - px), z + (z - pz)
            else:
                next_local_index = min(index + 1, len(points) - 1)
                nx, _ny, nz = points[next_local_index]
        if index > 0:
            px, _py, pz = points[index - 1]
            distance += math.hypot(x - px, z - pz)

        dx = nx - x
        dz = nz - z
        length = math.hypot(dx, dz) or 1.0
        tx = dx / length
        tz = dz / length
        perp_x = -tz
        perp_z = tx
        yaw = math.atan2(tx, tz)
        sector = 0 if distance < total_length / 3.0 else 1 if distance < 2.0 * total_length / 3.0 else 2
        branch_pointer = branch_links.get(index, -1)
        test_speed = 0.0 if pitlane else 55.0
        edge_width = lane_width_m * (0.75 if pitlane else 1.0)

        lines.extend([
            f"wp_pos=({x:.4f},{y:.4f},{z:.4f})",
            f"wp_perp=({perp_x:.4f},0.0000,{perp_z:.4f})",
            "wp_normal=(0.0000,1.0000,0.0000)",
        ])
        for path_id, offset in path_offsets:
            path_speed = test_speed if not pitlane else -1.0
            lines.extend([
                f"wp_pathinfo2=({path_id},{offset:.4f},0.0000,{path_speed:.4f})",
                f"wp_oriantation=({path_id},0.0000,{yaw:.4f},0.0000)",
                f"wp_pathflags=({path_id},0)",
            ])

        lines.extend([
            f"wp_width=({edge_width:.3f},{edge_width:.3f},{loop_half_width:.3f},{loop_half_width:.3f})",
            f"wp_dwidth=({loop_half_width:.3f},{loop_half_width:.3f},0.000,0.000)",
            "wp_lockedAlpha=(0)",
            f"wp_test_speed=({test_speed:.6f})",
            "wp_reverb=(0)",
            f"wp_score=({sector},{distance:.3f})",
            "wp_wpse=(0,0)",
            f"wp_branchID=({branch_id})",
            f"wp_bitfields=({1 if pitlane else 0})",
            f"wp_pitlane=({pitlane})",
            f"WP_PTRS=({prev_index},{next_index},{branch_pointer},{branch_id})",
        ])
    return lines


def blacklake_scn(stage_name: str) -> str:
    stage_folder = f"BLACKLAKE_{stage_name.upper()}"
    return f"""SearchPath=.
SearchPath=BLACKLAKE
SearchPath=BLACKLAKE\\{stage_folder}
SearchPath=BLACKLAKE\\ASSETS\\GMT
SearchPath=BLACKLAKE\\ASSETS\\MAPS
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

Instance=BlackLake_Reference
{{
  MeshFile=BlackLake_Reference.gmt CollTarget=True HATTarget=False
}}

//-------------------------------------------------------
//------------------MANDATORY OBJECTS--------------------
//-------------------------------------------------------

Instance=xsector1
{{
  Render=False
  MeshFile=xsector1.gmt CollTarget=True HATTarget=False
  Response=VEHICLE,TIMING
}}

Instance=xsector2
{{
  Render=False
  MeshFile=xsector2.gmt CollTarget=True HATTarget=False
  Response=VEHICLE,TIMING
}}

Instance=xfinish
{{
  Render=False
  MeshFile=xfinish.gmt CollTarget=True HATTarget=False
  Response=VEHICLE,TIMING
}}

Instance=xpitin
{{
  Render=False
  MeshFile=xpitin.gmt CollTarget=True HATTarget=False
  Response=VEHICLE,PITSTOP
}}

Instance=xpitout
{{
  Render=False
  MeshFile=xpitout.gmt CollTarget=True HATTarget=False
  Response=VEHICLE,PITSTOP
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
  IncludeIns=BlackLake_Reference
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
  IncludeIns=BlackLake_Reference
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
- `BlackLake_{stage_name}.gdb`
- `BlackLake_{stage_name}.scn`
- `BlackLake_{stage_name}.AIW`
- `BlackLake_{stage_name}.wet`

What is still required before rFactor 2 can load and drive it:
- export or copy `BlackLake_Surface.gmt`
- export or copy `BlackLake_Markings.gmt`
- export or copy `BlackLake_Reference.gmt`
- export or copy mandatory timing trigger GMTs: `xfinish.gmt`, `xsector1.gmt`,
  `xsector2.gmt`, `xpitin.gmt`, `xpitout.gmt`
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
