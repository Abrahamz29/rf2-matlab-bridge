import argparse
import importlib
import math
import shutil
import sys
from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADDON_PARENT = PROJECT_ROOT / "tools" / "downloads" / "blacklake_export" / "rf2_blender_exporter"
STAGE_ROOT = PROJECT_ROOT / "tracks" / "blacklake" / "source"
MODDEV_LOCATIONS = Path(r"C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\ModDev\Locations")

STAGES = {
    "250m": {"half_extent_m": 125.0, "lane_length_m": 220.0, "lane_width_m": 12.0},
    "500m": {"half_extent_m": 250.0, "lane_length_m": 440.0, "lane_width_m": 12.0},
    "1000m": {"half_extent_m": 500.0, "lane_length_m": 900.0, "lane_width_m": 12.0},
    "2000m": {"half_extent_m": 1000.0, "lane_length_m": 1800.0, "lane_width_m": 14.0},
    "5000m": {"half_extent_m": 2500.0, "lane_length_m": 4600.0, "lane_width_m": 16.0},
    "12000m": {"half_extent_m": 6000.0, "lane_length_m": 11000.0, "lane_width_m": 18.0},
}


def register_rf2_addon() -> None:
    sys.path.insert(0, str(ADDON_PARENT))
    module = importlib.import_module("io_rfactor2_gmt_WIP-64_bit")
    module.register()


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def add_rf2_template(file_name: str):
    before = set(bpy.context.scene.objects)
    bpy.ops.mesh.add_rf2_object()
    new_objects = [obj for obj in bpy.context.scene.objects if obj not in before]
    parents = [obj for obj in new_objects if obj.type == "EMPTY"]
    meshes = [obj for obj in new_objects if obj.type == "MESH"]
    if not parents or not meshes:
        raise RuntimeError("rF2 template object was not created correctly")

    parent = parents[0]
    mesh_obj = meshes[0]
    parent.name = f"{file_name}_Parent"
    parent["File_Name"] = file_name
    parent["LOD_In"] = 0.0
    parent["LOD_Out"] = 20000.0
    mesh_obj.name = file_name
    mesh_obj.data.name = f"{file_name}_Mesh"
    return parent, mesh_obj


def set_mesh(mesh_obj, vertices, faces) -> None:
    material = mesh_obj.data.materials[0] if mesh_obj.data.materials else None
    mesh = bpy.data.meshes.new(f"{mesh_obj.name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    if material is not None:
        mesh.materials.append(material)
        for poly in mesh.polygons:
            poly.material_index = 0
    mesh.uv_layers.new(name="Diffuse #1 UV Layer")
    for layer_name, color in [
        ("Diffuse Color", (1.0, 1.0, 1.0, 1.0)),
        ("Diffuse Alpha", (1.0, 1.0, 1.0, 1.0)),
        ("Specular Color", (0.75, 0.75, 0.75, 1.0)),
        ("Specular Alpha", (1.0, 1.0, 1.0, 1.0)),
    ]:
        layer = mesh.vertex_colors.new(name=layer_name)
        for loop_color in layer.data:
            loop_color.color = color
    mesh_obj.data = mesh
    bpy.context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)
    bpy.ops.object.shade_flat()


def make_grid_surface(half_extent: float, cells_per_side: int = 20):
    step = (2.0 * half_extent) / cells_per_side
    vertices = []
    for z_idx in range(cells_per_side + 1):
        z = -half_extent + z_idx * step
        for x_idx in range(cells_per_side + 1):
            x = -half_extent + x_idx * step
            vertices.append((x, 0.0, z))

    faces = []
    row = cells_per_side + 1
    for z_idx in range(cells_per_side):
        for x_idx in range(cells_per_side):
            a = z_idx * row + x_idx
            faces.append((a, a + 1, a + row + 1, a + row))
    return vertices, faces


def add_quad(vertices, faces, x0, z0, x1, z1, y=0.015):
    index = len(vertices)
    vertices.extend([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)])
    faces.append((index, index + 1, index + 2, index + 3))


def make_ring(vertices, faces, radius, width, segments, y=0.015):
    for idx in range(segments):
        a0 = (2.0 * math.pi * idx) / segments
        a1 = (2.0 * math.pi * (idx + 1)) / segments
        inner = radius - width / 2.0
        outer = radius + width / 2.0
        index = len(vertices)
        vertices.extend(
            [
                (inner * math.cos(a0), y, inner * math.sin(a0)),
                (outer * math.cos(a0), y, outer * math.sin(a0)),
                (outer * math.cos(a1), y, outer * math.sin(a1)),
                (inner * math.cos(a1), y, inner * math.sin(a1)),
            ]
        )
        faces.append((index, index + 1, index + 2, index + 3))


def make_markings(half_extent: float, lane_length: float, lane_width: float):
    vertices = []
    faces = []
    stripe = 0.15
    gap = lane_width / 2.0
    end_margin = min(half_extent - 5.0, lane_length / 2.0)

    add_quad(vertices, faces, -stripe / 2.0, -end_margin, stripe / 2.0, end_margin)
    add_quad(vertices, faces, -end_margin, -stripe / 2.0, end_margin, stripe / 2.0)
    add_quad(vertices, faces, -gap - stripe, -end_margin, -gap, end_margin)
    add_quad(vertices, faces, gap, -end_margin, gap + stripe, end_margin)

    launch_half = lane_width / 2.0
    launch_len = min(40.0, end_margin / 3.0)
    add_quad(vertices, faces, -launch_half, -launch_len, launch_half, -launch_len + stripe)
    add_quad(vertices, faces, -launch_half, launch_len - stripe, launch_half, launch_len)
    add_quad(vertices, faces, -launch_half, -launch_len, -launch_half + stripe, launch_len)
    add_quad(vertices, faces, launch_half - stripe, -launch_len, launch_half, launch_len)

    make_ring(vertices, faces, 40.0, 0.25, 64)
    make_ring(vertices, faces, 80.0, 0.25, 96)
    return vertices, faces


def set_material(mesh_obj, name: str, diffuse):
    mat = mesh_obj.data.materials[0]
    mat.name = name
    mat.diffuse_color = diffuse
    mat["Diffuse_Color"] = diffuse
    mat["Ambient_Color"] = diffuse
    mat["DiffuseM"] = 1


def export_selected(file_name: str, work_dir: Path) -> Path:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if obj.name.startswith(file_name):
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        if obj.parent and obj.parent.name.startswith(file_name):
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

    cwd = Path.cwd()
    try:
        import os

        os.chdir(work_dir)
        bpy.ops.export_scene.gmt_override(filepath=str(work_dir / f"{file_name}.gmt"))
    finally:
        os.chdir(cwd)
    return work_dir / f"{file_name}.gmt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=sorted(STAGES), default="250m")
    parser.add_argument("--install-moddev", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])

    stage = STAGES[args.stage]
    out_dir = STAGE_ROOT / args.stage / "gmt"
    out_dir.mkdir(parents=True, exist_ok=True)

    register_rf2_addon()
    clear_scene()

    _, surface = add_rf2_template("BlackLake_Surface")
    set_mesh(surface, *make_grid_surface(stage["half_extent_m"]))
    set_material(surface, "BlackLakeAsphalt", (0.08, 0.08, 0.08, 1.0))
    surface_gmt = export_selected("BlackLake_Surface", out_dir)

    clear_scene()
    _, markings = add_rf2_template("BlackLake_Markings")
    set_mesh(markings, *make_markings(stage["half_extent_m"], stage["lane_length_m"], stage["lane_width_m"]))
    set_material(markings, "BlackLakePaint", (0.92, 0.92, 0.92, 1.0))
    markings_gmt = export_selected("BlackLake_Markings", out_dir)

    print(f"EXPORTED {surface_gmt}")
    print(f"EXPORTED {markings_gmt}")

    if args.install_moddev:
        layout_dir = MODDEV_LOCATIONS / "BlackLake" / f"BlackLake_{args.stage}"
        layout_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(surface_gmt, layout_dir / surface_gmt.name)
        shutil.copy2(markings_gmt, layout_dir / markings_gmt.name)
        print(f"INSTALLED {layout_dir}")


if __name__ == "__main__":
    main()
