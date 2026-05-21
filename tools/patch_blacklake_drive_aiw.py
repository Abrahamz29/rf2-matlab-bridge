import argparse
import re
from pathlib import Path


GRID_SECTIONS = {"GRID", "ALTGRID", "TELEPORT"}


def fmt_pose(x: float, y: float, z: float) -> str:
    return f"({x:.3f},{y:.3f},{z:.3f})"


def grid_pose(index: int, section: str) -> tuple[float, float, float, float]:
    columns = 5
    row = index // columns
    col = index % columns
    x = (col - (columns - 1) / 2.0) * 6.0

    if section == "ALTGRID":
        z_base = -26.0
    elif section == "TELEPORT":
        z_base = -42.0
    else:
        z_base = -58.0

    z = z_base + row * 10.0
    y = 0.550
    yaw = 0.000
    return x, y, z, yaw


def pit_pose(team_index: int) -> tuple[float, float, float, float]:
    columns = 5
    row = team_index // columns
    col = team_index % columns
    x = -24.0 + col * 12.0
    y = 0.550
    z = 18.0 + row * 12.0
    yaw = 0.000
    return x, y, z, yaw


def garage_pose(team_index: int, garage_index: int) -> tuple[float, float, float, float]:
    x, y, z, yaw = pit_pose(team_index)
    x += (garage_index - 1) * 3.5
    z += 6.0
    return x, y, z, yaw


def patch_aiw(text: str, max_entries: int) -> str:
    output: list[str] = []
    section = ""
    current_grid_index: int | None = None
    current_team_index: int | None = None
    skip_grid_entry = False
    skip_pit_team = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        section_match = re.match(r"^\[([^\]]+)\]", line)
        if section_match:
            section = section_match.group(1).upper()
            current_grid_index = None
            current_team_index = None
            skip_grid_entry = False
            skip_pit_team = False
            output.append(line)
            continue

        if line.startswith("startinggrid="):
            output.append(f"startinggrid={max_entries}")
            continue

        if section in GRID_SECTIONS:
            grid_match = re.match(r"^GridIndex=(\d+)", line)
            if grid_match:
                current_grid_index = int(grid_match.group(1))
                skip_grid_entry = current_grid_index >= max_entries
                if not skip_grid_entry:
                    output.append(f"GridIndex={current_grid_index}")
                continue

            if skip_grid_entry:
                continue

            if line.startswith("Pos=(") and current_grid_index is not None:
                x, y, z, _ = grid_pose(current_grid_index, section)
                output.append(f"Pos={fmt_pose(x, y, z)}")
                continue

            if line.startswith("Ori=(") and current_grid_index is not None:
                _, _, _, yaw = grid_pose(current_grid_index, section)
                output.append(f"Ori=(0.000,{yaw:.3f},0.000)")
                continue

            output.append(line)
            continue

        if section == "PITS":
            team_match = re.match(r"^TeamIndex=(\d+)", line)
            if team_match:
                current_team_index = int(team_match.group(1))
                skip_pit_team = current_team_index >= max_entries
                if not skip_pit_team:
                    output.append(f"TeamIndex={current_team_index}")
                continue

            if skip_pit_team:
                continue

            if line.startswith("PitPos=(") and current_team_index is not None:
                x, y, z, _ = pit_pose(current_team_index)
                output.append(f"PitPos={fmt_pose(x, y, z)}")
                continue

            if line.startswith("PitOri=(") and current_team_index is not None:
                _, _, _, yaw = pit_pose(current_team_index)
                output.append(f"PitOri=(0.000,{yaw:.3f},0.000)")
                continue

            garage_match = re.match(r"^GarPos=\((\d+),", line)
            if garage_match and current_team_index is not None:
                garage_index = int(garage_match.group(1))
                x, y, z, _ = garage_pose(current_team_index, garage_index)
                output.append(f"GarPos=({garage_index},{x:.3f},{y:.3f},{z:.3f})")
                continue

            garage_ori_match = re.match(r"^GarOri=\((\d+),", line)
            if garage_ori_match and current_team_index is not None:
                garage_index = int(garage_ori_match.group(1))
                _, _, _, yaw = garage_pose(current_team_index, garage_index)
                output.append(f"GarOri=({garage_index},0.000,{yaw:.3f},0.000)")
                continue

            output.append(line)
            continue

        output.append(line)

    return "\n".join(output) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Patch an rFactor 2 AIW so the drive-test spawn data sits on BlackLake."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--max-entries", type=int, default=20)
    args = parser.parse_args()

    if args.max_entries < 1:
        raise SystemExit("--max-entries must be at least 1")

    source = args.path.read_text(encoding="ascii", errors="strict")
    patched = patch_aiw(source, args.max_entries)
    args.path.write_text(patched, encoding="ascii", newline="\n")


if __name__ == "__main__":
    main()
