#!/usr/bin/env python3
"""Seed a tyre material mix from the TGM Gen spreadsheet selections."""

from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import unicodedata
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tgm_gen_ods as odsmod
from build_material_recognition_report import (
    absolute_residual,
    interpolate_material_value,
    log_residual,
    normalized_material_points,
    observed_points,
    selected_materials,
    split_material_rows,
)
from build_tyre_database import parse_tgm_records


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "tyres" / "database" / "rf2_tyre_database.sqlite"
DEFAULT_TGM = REPO_ROOT / "tyres" / "input" / "tgm" / "G_9.2-20.0-13x10_Soft_Slick_1975.tgm"
DEFAULT_ODS_CANDIDATES = [
    REPO_ROOT / "input" / "TGM Gen V0.33 - GY F1 1975 Front.ods",
    REPO_ROOT / "tyres" / "downloads" / "studio397" / "TGM Gen V0.33 - GY F1 1975 Front.ods",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Unified tyre SQLite database")
    parser.add_argument("--tgm", type=Path, default=DEFAULT_TGM, help="Generated TGM to assign")
    parser.add_argument("--ods", type=Path, default=None, help="TGM Gen spreadsheet source")
    args = parser.parse_args()

    ods = args.ods or first_existing(DEFAULT_ODS_CANDIDATES)
    if ods is None:
        checked = ", ".join(str(path) for path in DEFAULT_ODS_CANDIDATES)
        raise SystemExit(f"no TGM Gen ODS found; pass --ods. Checked: {checked}")

    db_path = args.db.resolve()
    tgm_path = args.tgm.resolve()
    assignments, summary = build_assignments(db_path, tgm_path, ods.resolve())
    write_assignments(db_path, tgm_path, assignments)

    print(f"seeded {len(assignments)} material cells for {tgm_path.stem}")
    print(f"database: {db_path}")
    print("assignments by stack/material:")
    for (stack, material), count in sorted(summary.items(), key=lambda item: (stack_sort(item[0][0]), item[0][1])):
        print(f"  {stack}: {material} ({count})")
    return 0


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def build_assignments(db_path: Path, tgm_path: Path, ods_path: Path) -> tuple[list[dict[str, Any]], Counter[tuple[str, str]]]:
    cells = odsmod.load_formula_cells(ods_path)
    selected = selected_materials(cells)
    library = odsmod.extract_material_library(ods_path)
    db_materials = load_db_materials(db_path)
    candidates = build_selected_candidates(selected, library["materials"], db_materials)
    groups = parse_tgm_material_groups(tgm_path)

    assignments: list[dict[str, Any]] = []
    summary: Counter[tuple[str, str]] = Counter()
    for group in groups:
        candidate = best_selected_candidate(group, candidates)
        if candidate is None:
            continue
        stack_key = group_stack_key(group)
        material = candidate["db_material"]
        assignment = {
            "cell_key": f"{int(group['node'])}:{stack_key}",
            "node_index": int(group["node"]),
            "stack_key": stack_key,
            "material_id": int(material["id"]),
            "material_name": str(material["name"]),
            "material_category": str(material["category"]),
        }
        assignments.append(assignment)
        summary[(stack_key_label(stack_key), assignment["material_name"])] += 1
    return assignments, summary


def parse_tgm_material_groups(tgm_path: Path) -> list[dict[str, Any]]:
    nodes: dict[int, dict[str, list[list[float]]]] = {}
    for record in parse_tgm_records(tgm_path):
        if record["section"] != "Node" or record["node_index"] is None:
            continue
        key = record["key"]
        if key not in {"TreadMaterial", "BulkMaterial", "PlyMaterial", "PlyParams"}:
            continue
        node = nodes.setdefault(
            int(record["node_index"]),
            {"TreadMaterial": [], "BulkMaterial": [], "PlyMaterial": [], "PlyParams": []},
        )
        node[key].append(record["value"])

    groups: list[dict[str, Any]] = []
    for node_index, node in sorted(nodes.items()):
        for kind in ("TreadMaterial", "BulkMaterial", "PlyMaterial"):
            for index, rows in enumerate(split_material_rows(node[kind]), start=1):
                group: dict[str, Any] = {
                    "node": node_index,
                    "kind": kind,
                    "index": index,
                    "rows": rows,
                }
                if kind == "PlyMaterial" and index <= len(node["PlyParams"]):
                    ply_params = node["PlyParams"][index - 1]
                    group["angleDeg"] = ply_params[0] if len(ply_params) > 0 else None
                    group["thicknessM"] = ply_params[1] if len(ply_params) > 1 else None
                groups.append(group)
    return groups


def load_db_materials(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    try:
        return [
            {"id": row[0], "category": row[1], "name": row[2]}
            for row in conn.execute("select id, category, name from materials order by id")
        ]
    finally:
        conn.close()


def build_selected_candidates(
    selected: list[dict[str, Any]],
    library_materials: list[dict[str, Any]],
    db_materials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    library_by_name = {normalize_name(material["name"]): material for material in library_materials}
    db_by_name = {normalize_name(material["name"]): material for material in db_materials}
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float, float]] = set()
    for row in selected:
        material_name = str(row.get("material", ""))
        library_material = library_by_name.get(normalize_name(material_name))
        db_material = db_by_name.get(normalize_name(material_name))
        if library_material is None or db_material is None:
            raise SystemExit(f"selected material not found in library/database: {material_name}")
        e_multiplier = numeric_multiplier(row.get("eMultiplier"))
        density_multiplier = numeric_multiplier(row.get("densityMultiplier"))
        key = (str(row["kind"]), normalize_name(material_name), e_multiplier, density_multiplier)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "role": row["role"],
                "kind": row["kind"],
                "db_material": db_material,
                "scaled_material": scaled_material(library_material, e_multiplier, density_multiplier),
            }
        )
    return candidates


def best_selected_candidate(group: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for candidate in candidates:
        if candidate["kind"] != group["kind"]:
            continue
        score = fixed_multiplier_match_score(group, candidate["scaled_material"])
        if score is None:
            continue
        item = {**candidate, "score": score}
        if best is None or item["score"] < best["score"]:
            best = item
    return best


def fixed_multiplier_match_score(group: dict[str, Any], material: dict[str, Any]) -> float | None:
    points = normalized_material_points(material)
    observed = observed_points(group)
    fields = [
        ("youngsModulusPa", "youngsModulusPa", 3.0, "log"),
        ("densityKgM3", "densityKgM3", 1.4, "log"),
        ("poissonRatio", "poissonsRatio", 1.7, "abs"),
        ("compressionMultiplier", "compressionTensionRatio", 1.7, "log"),
        ("specificHeatJKgK", "specificHeat", 0.65, "log"),
        ("conductivityWMK", "thermalConductivity", 0.9, "log"),
    ]
    weighted_score = 0.0
    weight_sum = 0.0
    for observed_field, base_field, weight, mode in fields:
        observed_values = []
        base_values = []
        for point in observed:
            observed_value = point.get(observed_field)
            base_value = interpolate_material_value(points, point.get("temperatureK"), base_field)
            if observed_value is not None and base_value is not None:
                observed_values.append(observed_value)
                base_values.append(base_value)
        if not observed_values:
            continue
        if mode == "abs":
            residual = absolute_residual(observed_values, base_values, 0.08)
        else:
            residual = log_residual(observed_values, base_values)
        if residual is None:
            continue
        weighted_score += residual * weight
        weight_sum += weight
    if weight_sum <= 0:
        return None
    return weighted_score / weight_sum


def scaled_material(material: dict[str, Any], e_multiplier: float, density_multiplier: float) -> dict[str, Any]:
    result = deepcopy(material)
    result["points"] = []
    for point in material.get("points", []):
        scaled = dict(point)
        scaled["youngsModulusPa"] = scaled_number(point.get("youngsModulusPa"), e_multiplier)
        scaled["densityKgM3"] = scaled_number(point.get("densityKgM3"), density_multiplier)
        result["points"].append(scaled)
    return result


def scaled_number(value: Any, multiplier: float) -> Any:
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return value


def numeric_multiplier(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    return number if number > 0 else 1.0


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value)).lower()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def group_stack_key(group: dict[str, Any]) -> str:
    kind = str(group["kind"])
    if kind == "TreadMaterial":
        return "tread"
    if kind == "BulkMaterial":
        return "bulk"
    if kind == "PlyMaterial":
        return f"ply:{int(group['index'])}"
    return kind


def stack_key_label(stack_key: str) -> str:
    if stack_key == "tread":
        return "Tread"
    if stack_key == "bulk":
        return "Bulk"
    if stack_key.startswith("ply:"):
        return "L" + stack_key.split(":", 1)[1]
    return stack_key


def stack_sort(stack_label: str) -> tuple[int, int, str]:
    if stack_label == "Tread":
        return (0, 0, stack_label)
    if stack_label == "Bulk":
        return (1, 0, stack_label)
    if stack_label.startswith("L"):
        try:
            return (2, int(stack_label[1:]), stack_label)
        except ValueError:
            pass
    return (3, 0, stack_label)


def write_assignments(db_path: Path, tgm_path: Path, assignments: list[dict[str, Any]]) -> None:
    key = "sha256:" + hashlib.sha256(tgm_path.read_bytes()).hexdigest()
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("pragma foreign_keys = on")
        conn.execute(
            """
            insert or replace into tyre_material_mixes
                (tyre_key, tyre_name, source_path, assignment_count, updated_utc)
            values (?, ?, ?, ?, ?)
            """,
            (key, tgm_path.stem, str(tgm_path), len(assignments), now),
        )
        conn.execute("delete from tyre_material_mix_assignments where tyre_key = ?", (key,))
        conn.executemany(
            """
            insert into tyre_material_mix_assignments
                (tyre_key, cell_key, node_index, stack_key, material_id,
                 material_name, material_category, updated_utc)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    key,
                    item["cell_key"],
                    item["node_index"],
                    item["stack_key"],
                    item["material_id"],
                    item["material_name"],
                    item["material_category"],
                    now,
                )
                for item in assignments
            ],
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
