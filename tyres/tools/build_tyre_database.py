"""Build a local rFactor 2 tyre inventory, construction, and behaviour database."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RF2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\rFactor 2")
DEFAULT_DB = Path("tyres/database/rf2_tyre_database.sqlite")
DEFAULT_TGM_CACHE = Path("tyres/cache/tgm")
DEFAULT_RESULTS_ROOT = Path("tyres/scenarios/ttool/results")


EXPECTED_TUPLE_WIDTHS = {
    "Geometry": 3,
    "InnerGeometryOverride": 2,
    "RingAndRim": 2,
    "PlyParams": 3,
    "BulkMaterial": 7,
    "TreadMaterial": 7,
    "PlyMaterial": 7,
}

EXPECTED_TUPLE_RANGES = {
    "Geometry": [(-1, 1), (-1, 1), (-1, 1)],
    "InnerGeometryOverride": [(-1, 1), (-1, 1)],
    "RingAndRim": [(-math.inf, math.inf), (-math.inf, math.inf)],
    "PlyParams": [(-360, 360), (0, 1), (-10, 10)],
    "BulkMaterial": [(100, 1000), (100, 20000), (1000, 1e13), (-1, 1), (0, 10), (50, 10000), (0, 100)],
    "TreadMaterial": [(100, 1000), (100, 20000), (1000, 1e13), (-1, 1), (0, 10), (50, 10000), (0, 100)],
    "PlyMaterial": [(100, 1000), (100, 20000), (1000, 1e13), (-1, 1), (0, 10), (50, 10000), (0, 100)],
}

MATERIAL_KEYS = {"BulkMaterial", "TreadMaterial", "PlyMaterial"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def relative_or_absolute(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def parse_scalar(value: str):
    value = value.strip()
    if value == "":
        return ""
    try:
        if "," in value and "." not in value:
            return float(value.replace(",", "."))
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def parse_tgm_value(raw: str, key: str):
    value = raw.split("//", 1)[0].strip()
    if value.startswith("(") and value.endswith(")"):
        parts = [part.strip() for part in value[1:-1].split(",") if part.strip()]
        width = EXPECTED_TUPLE_WIDTHS.get(key, 0)
        if width > 0:
            parsed = parse_tuple_parts(parts, width, EXPECTED_TUPLE_RANGES.get(key, []))
            if parsed is not None:
                return parsed
        return [parse_scalar(part) for part in parts]
    return parse_scalar(value)


def parse_tuple_parts(parts: list[str], width: int, ranges: list[tuple[float, float]]):
    best_score = math.inf
    best_values = None
    part_count = len(parts)

    def search(part_index: int, field_index: int, values: list[float], score: float) -> None:
        nonlocal best_score, best_values
        remaining_parts = part_count - part_index
        remaining_fields = width - field_index
        if remaining_parts < remaining_fields or remaining_parts > remaining_fields * 2:
            return
        if field_index == width:
            if part_index == part_count and score < best_score:
                best_score = score
                best_values = values[:]
            return

        for group_length in (1, 2):
            if part_index + group_length > part_count:
                continue
            candidate, ok, candidate_score = parse_tuple_candidate(parts[part_index : part_index + group_length])
            if not ok:
                continue
            next_values = values[:]
            next_values[field_index] = candidate
            search(
                part_index + group_length,
                field_index + 1,
                next_values,
                score + candidate_score + range_score(candidate, ranges[field_index] if field_index < len(ranges) else None),
            )

    search(0, 0, [math.nan] * width, 0)
    return best_values


def parse_tuple_candidate(parts: list[str]) -> tuple[float, bool, float]:
    if len(parts) == 1:
        value = parse_scalar(parts[0])
        return (float(value), True, 0) if isinstance(value, (int, float)) else (math.nan, False, math.inf)

    if len(parts) != 2 or not can_be_decimal_comma(parts[0], parts[1]):
        return math.nan, False, math.inf

    try:
        value = float(f"{parts[0].strip()}.{parts[1].strip()}")
    except ValueError:
        return math.nan, False, math.inf
    score = 0.2 if re.search(r"[eE]", parts[1]) else -0.1
    return value, True, score


def can_be_decimal_comma(left: str, right: str) -> bool:
    return bool(re.fullmatch(r"[+-]?\d+", left.strip())) and bool(re.fullmatch(r"\d+(?:[eE][+-]?\d+)?", right.strip()))


def range_score(value: float, valid_range: tuple[float, float] | None) -> float:
    if valid_range is None or math.isnan(value):
        return 0
    low, high = valid_range
    if math.isinf(low) or math.isinf(high) or low <= value <= high:
        return 0
    return 1000 + min(abs(value - low), abs(value - high))


def parse_tgm_records(path: Path) -> list[dict]:
    records = []
    section = ""
    current_node = None
    node_counter = 0

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_number, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("["):
                section = stripped.split("]", 1)[0].strip("[")
                current_node = None
                if section == "Node":
                    match = re.search(r"\[Node\]\s*//\s*(\d+)", stripped)
                    if match:
                        current_node = int(match.group(1))
                    else:
                        node_counter += 1
                        current_node = node_counter
                continue
            if section in {"LookupV2", "PatchV1"} or "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            key = key.strip()
            raw_value = raw_value.split("//", 1)[0].strip()
            records.append(
                {
                    "line_number": line_number,
                    "section": section,
                    "node_index": current_node,
                    "key": key,
                    "raw_value": raw_value,
                    "value": parse_tgm_value(raw_value, key),
                }
            )

    return records


def parse_tgm(path: Path) -> dict[str, dict[str, list]]:
    parsed: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for record in parse_tgm_records(path):
        parsed[record["section"]][record["key"]].append(record["value"])
    return {section: dict(values) for section, values in parsed.items()}


def discover_loose_tgms(rf2_root: Path) -> list[Path]:
    return sorted(
        path
        for path in rf2_root.rglob("*.tgm")
        if path.is_file()
        and "tools\\cache" not in str(path).lower()
        and "tyres\\cache" not in str(path).lower()
    )


def discover_archive_candidates(rf2_root: Path, include_workshop: bool) -> list[dict]:
    vehicle_root = rf2_root / "Installed" / "Vehicles"
    workshop_root = rf2_root.parent.parent / "workshop" / "content" / "365960"
    roots: list[tuple[Path, str]] = []
    if vehicle_root.exists():
        roots.append((vehicle_root, "*.mas"))
    if include_workshop and workshop_root.exists():
        roots.append((workshop_root, "*.rfcmp"))

    candidates = []
    for root, glob in roots:
        for archive_path, names in rg_tgm_hints(root, glob).items():
            archive = Path(archive_path)
            if not archive.exists():
                continue
            stat = archive.stat()
            for name in names:
                candidates.append(
                    {
                        "archive_path": str(archive),
                        "file_name_hint": Path(name).name,
                        "source_kind": archive.suffix.lower().lstrip("."),
                        "encrypted": int("encrypted" in archive.name.lower()),
                        "archive_bytes": stat.st_size,
                        "archive_mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                        "vehicle_name": infer_vehicle_name(archive),
                    }
                )
    return candidates


def rg_tgm_hints(root: Path, glob: str) -> dict[str, set[str]]:
    command = [
        "rg",
        "-a",
        "-o",
        r"[A-Za-z0-9_ .()+\-/]{1,96}\.tgm",
        str(root),
        "-g",
        glob,
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    except OSError:
        return {}

    hints: dict[str, set[str]] = defaultdict(set)
    for line in completed.stdout.splitlines():
        if ".mas:" not in line and ".rfcmp:" not in line:
            continue
        if ".mas:" in line:
            archive_path, name = line.split(".mas:", 1)
            archive_path = archive_path + ".mas"
        else:
            archive_path, name = line.split(".rfcmp:", 1)
            archive_path = archive_path + ".rfcmp"
        clean_name = name.strip().replace("/", "\\")
        if clean_name:
            hints[archive_path].add(clean_name)
    return hints


def discover_archive_candidates_slow(rf2_root: Path, include_workshop: bool) -> list[dict]:
    vehicle_root = rf2_root / "Installed" / "Vehicles"
    workshop_root = rf2_root.parent.parent / "workshop" / "content" / "365960"
    archives = []
    if vehicle_root.exists():
        archives.extend(vehicle_root.rglob("*.mas"))
    if include_workshop and workshop_root.exists():
        archives.extend(workshop_root.rglob("*.rfcmp"))

    tgm_pattern = re.compile(rb"([A-Za-z0-9_ .()+\-/]{1,96}\.tgm)", re.IGNORECASE)
    candidates = []
    for archive in sorted(set(archives)):
        try:
            data = archive.read_bytes()
        except OSError:
            continue
        names = sorted({m.group(1).decode("latin-1", "ignore").replace("/", "\\") for m in tgm_pattern.finditer(data)})
        for name in names:
            candidates.append(
                {
                    "archive_path": str(archive),
                    "file_name_hint": Path(name).name,
                    "source_kind": archive.suffix.lower().lstrip("."),
                    "encrypted": int("encrypted" in archive.name.lower()),
                    "archive_bytes": archive.stat().st_size,
                    "archive_mtime": datetime.fromtimestamp(archive.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                    "vehicle_name": infer_vehicle_name(archive),
                }
            )
    return candidates


def infer_vehicle_name(path: Path) -> str:
    parts = path.parts
    for marker in ["Vehicles", "365960"]:
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return ""


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE tyres (
            id INTEGER PRIMARY KEY,
            sha256 TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            local_copy_path TEXT NOT NULL,
            length_bytes INTEGER NOT NULL,
            source_count INTEGER NOT NULL,
            created_utc TEXT NOT NULL
        );

        CREATE TABLE tyre_sources (
            id INTEGER PRIMARY KEY,
            tyre_id INTEGER NOT NULL REFERENCES tyres(id),
            source_path TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            vehicle_name TEXT,
            last_write_utc TEXT,
            length_bytes INTEGER
        );

        CREATE TABLE tyre_parameters (
            id INTEGER PRIMARY KEY,
            tyre_id INTEGER NOT NULL REFERENCES tyres(id),
            section TEXT NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT NOT NULL
        );

        CREATE TABLE tyre_property_values (
            id INTEGER PRIMARY KEY,
            tyre_id INTEGER NOT NULL REFERENCES tyres(id) ON DELETE CASCADE,
            line_number INTEGER NOT NULL,
            section TEXT NOT NULL,
            node_index INTEGER,
            key TEXT NOT NULL,
            raw_value TEXT NOT NULL,
            value_json TEXT NOT NULL
        );

        CREATE INDEX idx_tyre_property_values_tyre_section_key
            ON tyre_property_values (tyre_id, section, key);

        CREATE INDEX idx_tyre_property_values_tyre_node
            ON tyre_property_values (tyre_id, node_index);

        CREATE TABLE tyre_construction_summary (
            tyre_id INTEGER PRIMARY KEY REFERENCES tyres(id) ON DELETE CASCADE,
            declared_num_layers INTEGER,
            declared_num_sections INTEGER,
            declared_num_nodes INTEGER,
            actual_node_count INTEGER NOT NULL,
            max_ply_layers INTEGER NOT NULL,
            ply_layer_count INTEGER NOT NULL,
            material_row_count INTEGER NOT NULL
        );

        CREATE TABLE tyre_nodes (
            id INTEGER PRIMARY KEY,
            tyre_id INTEGER NOT NULL REFERENCES tyres(id) ON DELETE CASCADE,
            node_index INTEGER NOT NULL,
            geometry_x_m REAL,
            geometry_y_m REAL,
            thickness_m REAL,
            tread_depth_m REAL,
            ring_and_rim_first REAL,
            ring_and_rim_second REAL,
            geometry_json TEXT,
            ring_and_rim_json TEXT,
            UNIQUE (tyre_id, node_index)
        );

        CREATE TABLE tyre_ply_layers (
            id INTEGER PRIMARY KEY,
            tyre_id INTEGER NOT NULL REFERENCES tyres(id) ON DELETE CASCADE,
            node_index INTEGER NOT NULL,
            ply_index INTEGER NOT NULL,
            angle_deg REAL,
            thickness_m REAL,
            connect_flag REAL,
            source_line_number INTEGER,
            raw_value TEXT,
            value_json TEXT,
            UNIQUE (tyre_id, node_index, ply_index)
        );

        CREATE TABLE tyre_material_rows (
            id INTEGER PRIMARY KEY,
            tyre_id INTEGER NOT NULL REFERENCES tyres(id) ON DELETE CASCADE,
            node_index INTEGER NOT NULL,
            material_kind TEXT NOT NULL,
            material_index INTEGER NOT NULL,
            ply_index INTEGER,
            sample_index INTEGER NOT NULL,
            source_line_number INTEGER,
            temperature_k REAL,
            density_kg_m3 REAL,
            youngs_modulus_pa REAL,
            poisson_ratio REAL,
            compression_multiplier REAL,
            specific_heat_j_kg_k REAL,
            conductivity_w_m_k REAL,
            raw_value TEXT,
            value_json TEXT
        );

        CREATE INDEX idx_tyre_material_rows_tyre_node_kind
            ON tyre_material_rows (tyre_id, node_index, material_kind, material_index);

        CREATE TABLE archive_candidates (
            id INTEGER PRIMARY KEY,
            archive_path TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            vehicle_name TEXT,
            file_name_hint TEXT NOT NULL,
            encrypted INTEGER NOT NULL,
            archive_bytes INTEGER,
            archive_mtime TEXT
        );

        CREATE TABLE ttool_runs (
            id INTEGER PRIMARY KEY,
            run_name TEXT NOT NULL,
            result_path TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            created_utc TEXT NOT NULL
        );

        CREATE TABLE ttool_samples (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES ttool_runs(id),
            realtime_test_index REAL,
            test_case_index INTEGER,
            sample_fraction REAL,
            vertical_force_n REAL,
            long_force_n REAL,
            lat_force_n REAL,
            aligning_torque_nm REAL,
            load_n REAL,
            slip_angle_deg REAL,
            slip_ratio_pct REAL,
            camber_deg REAL,
            pressure_kpa REAL,
            temperature_c REAL,
            long_vel_mps REAL,
            lat_vel_mps REAL,
            rotation_rad_s REAL,
            rotation_mps REAL,
            nominal_radius_m REAL,
            dynamic_unloaded_radius_m REAL,
            deflection_m REAL
        );

        CREATE TABLE behaviour_summaries (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES ttool_runs(id),
            test_case_index INTEGER NOT NULL,
            sample_count INTEGER NOT NULL,
            mean_vertical_force_n REAL,
            mean_long_force_n REAL,
            mean_lat_force_n REAL,
            peak_abs_vertical_force_n REAL,
            peak_abs_long_force_n REAL,
            peak_abs_lat_force_n REAL,
            mean_slip_angle_deg REAL,
            mean_slip_ratio_pct REAL,
            mean_pressure_kpa REAL,
            mean_temperature_c REAL
        );
        """
    )
    return conn


def json_value(value) -> str:
    return json.dumps(value, ensure_ascii=True)


def db_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    return None


def value_at(value, index: int):
    if isinstance(value, list) and index < len(value):
        return db_number(value[index])
    return None


def first_record_value(records: list[dict], section: str, key: str):
    for record in records:
        if record["section"] == section and record["key"] == key:
            return record["value"]
    return None


def first_numeric_record_value(records: list[dict], section: str, key: str):
    return db_number(first_record_value(records, section, key))


def insert_tgm_property_values(conn: sqlite3.Connection, tyre_id: int, records: list[dict]) -> None:
    for record in records:
        if record["section"] == "LookupData" and record["key"] == "Bin":
            # The aggregate tyre_parameters table retains generated lookup bins.
            # Duplicating every bin line here bloats the construction-oriented table.
            continue
        conn.execute(
            """
            INSERT INTO tyre_property_values
                (tyre_id, line_number, section, node_index, key, raw_value, value_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tyre_id,
                record["line_number"],
                record["section"],
                record["node_index"],
                record["key"],
                record["raw_value"],
                json_value(record["value"]),
            ),
        )


def insert_tgm_construction(conn: sqlite3.Connection, tyre_id: int, records: list[dict]) -> None:
    node_records: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        if record["section"] == "Node" and record["node_index"] is not None:
            node_records[int(record["node_index"])].append(record)

    ply_layer_count = 0
    material_row_count = 0
    max_ply_layers = 0

    for node_index, rows in sorted(node_records.items()):
        geometry = next((record["value"] for record in rows if record["key"] == "Geometry"), None)
        tread_depth = next((record["value"] for record in rows if record["key"] == "TreadDepth"), None)
        ring_and_rim = next((record["value"] for record in rows if record["key"] == "RingAndRim"), None)
        conn.execute(
            """
            INSERT INTO tyre_nodes (
                tyre_id, node_index, geometry_x_m, geometry_y_m, thickness_m,
                tread_depth_m, ring_and_rim_first, ring_and_rim_second,
                geometry_json, ring_and_rim_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tyre_id,
                node_index,
                value_at(geometry, 0),
                value_at(geometry, 1),
                value_at(geometry, 2),
                db_number(tread_depth),
                value_at(ring_and_rim, 0),
                value_at(ring_and_rim, 1),
                json_value(geometry),
                json_value(ring_and_rim),
            ),
        )

        current_ply_index = 0
        material_state: dict[str, dict[str, float | int | None]] = defaultdict(
            lambda: {"material_index": 0, "sample_index": 0, "previous_temperature": None}
        )
        ply_sample_counts: dict[int, int] = defaultdict(int)

        for record in rows:
            key = record["key"]
            value = record["value"]
            if key == "PlyParams":
                current_ply_index += 1
                ply_layer_count += 1
                max_ply_layers = max(max_ply_layers, current_ply_index)
                conn.execute(
                    """
                    INSERT INTO tyre_ply_layers (
                        tyre_id, node_index, ply_index, angle_deg, thickness_m,
                        connect_flag, source_line_number, raw_value, value_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tyre_id,
                        node_index,
                        current_ply_index,
                        value_at(value, 0),
                        value_at(value, 1),
                        value_at(value, 2),
                        record["line_number"],
                        record["raw_value"],
                        json_value(value),
                    ),
                )
                continue

            if key not in MATERIAL_KEYS:
                continue

            temperature = value_at(value, 0)
            ply_index = None
            if key == "PlyMaterial" and current_ply_index > 0:
                material_index = current_ply_index
                ply_index = current_ply_index
                ply_sample_counts[current_ply_index] += 1
                sample_index = ply_sample_counts[current_ply_index]
            else:
                state = material_state[key]
                previous_temperature = state["previous_temperature"]
                if state["material_index"] == 0 or (
                    previous_temperature is not None and temperature is not None and temperature <= previous_temperature
                ):
                    state["material_index"] = int(state["material_index"]) + 1
                    state["sample_index"] = 0
                state["sample_index"] = int(state["sample_index"]) + 1
                state["previous_temperature"] = temperature
                material_index = int(state["material_index"])
                sample_index = int(state["sample_index"])

            material_row_count += 1
            conn.execute(
                """
                INSERT INTO tyre_material_rows (
                    tyre_id, node_index, material_kind, material_index, ply_index,
                    sample_index, source_line_number, temperature_k, density_kg_m3,
                    youngs_modulus_pa, poisson_ratio, compression_multiplier,
                    specific_heat_j_kg_k, conductivity_w_m_k, raw_value, value_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tyre_id,
                    node_index,
                    key,
                    material_index,
                    ply_index,
                    sample_index,
                    record["line_number"],
                    temperature,
                    value_at(value, 1),
                    value_at(value, 2),
                    value_at(value, 3),
                    value_at(value, 4),
                    value_at(value, 5),
                    value_at(value, 6),
                    record["raw_value"],
                    json_value(value),
                ),
            )

    conn.execute(
        """
        INSERT INTO tyre_construction_summary (
            tyre_id, declared_num_layers, declared_num_sections, declared_num_nodes,
            actual_node_count, max_ply_layers, ply_layer_count, material_row_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tyre_id,
            first_numeric_record_value(records, "QuasiStaticAnalysis", "NumLayers"),
            first_numeric_record_value(records, "QuasiStaticAnalysis", "NumSections"),
            first_numeric_record_value(records, "QuasiStaticAnalysis", "NumNodes"),
            len(node_records),
            max_ply_layers,
            ply_layer_count,
            material_row_count,
        ),
    )


def insert_tyre_inventory(
    conn: sqlite3.Connection,
    project_root: Path,
    rf2_root: Path,
    cache_dir: Path,
    extra_tgm_paths: list[Path],
) -> tuple[int, int]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    sources_by_hash: dict[str, list[Path]] = defaultdict(list)
    loose_tgms = discover_loose_tgms(rf2_root)
    loose_tgms.extend(path for path in extra_tgm_paths if path.is_file())

    for path in loose_tgms:
        sources_by_hash[sha256_file(path)].append(path)

    for digest, sources in sorted(sources_by_hash.items(), key=lambda item: item[1][0].name.lower()):
        primary = sorted(sources, key=lambda p: (0 if "\\pTool\\" in str(p) else 1, str(p)))[0]
        copied_name = f"{primary.stem}__{digest[:12]}{primary.suffix}"
        copied_path = cache_dir / copied_name
        shutil.copy2(primary, copied_path)

        cur = conn.execute(
            """
            INSERT INTO tyres
                (sha256, file_name, display_name, local_copy_path, length_bytes, source_count, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                digest,
                primary.name,
                primary.stem,
                relative_or_absolute(copied_path, project_root),
                primary.stat().st_size,
                len(sources),
                utc_now(),
            ),
        )
        tyre_id = cur.lastrowid

        for source in sorted(sources):
            conn.execute(
                """
                INSERT INTO tyre_sources
                    (tyre_id, source_path, source_kind, vehicle_name, last_write_utc, length_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tyre_id,
                    str(source),
                    "loose_tgm",
                    infer_vehicle_name(source),
                    datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                    source.stat().st_size,
                ),
            )

        records = parse_tgm_records(primary)
        insert_tgm_property_values(conn, tyre_id, records)
        insert_tgm_construction(conn, tyre_id, records)

        parsed: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for record in records:
            parsed[record["section"]][record["key"]].append(record["value"])
        for section, values in parsed.items():
            for key, value_list in values.items():
                conn.execute(
                    "INSERT INTO tyre_parameters (tyre_id, section, key, value_json) VALUES (?, ?, ?, ?)",
                    (tyre_id, section, key, json_value(value_list)),
                )

    return len(sources_by_hash), sum(len(v) for v in sources_by_hash.values())


def insert_archive_candidates(conn: sqlite3.Connection, rf2_root: Path, include_workshop: bool) -> int:
    candidates = discover_archive_candidates(rf2_root, include_workshop)
    for item in candidates:
        conn.execute(
            """
            INSERT INTO archive_candidates
                (archive_path, source_kind, vehicle_name, file_name_hint, encrypted, archive_bytes, archive_mtime)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["archive_path"],
                item["source_kind"],
                item["vehicle_name"],
                item["file_name_hint"],
                item["encrypted"],
                item["archive_bytes"],
                item["archive_mtime"],
            ),
        )
    return len(candidates)


def to_float(row: dict, key: str):
    value = row.get(key, "")
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def insert_ttool_results(conn: sqlite3.Connection, project_root: Path, results_root: Path) -> tuple[int, int]:
    csv_files = sorted(results_root.rglob("CustomRealtimeTable.csv")) if results_root.exists() else []
    run_count = 0
    sample_count = 0

    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

        cur = conn.execute(
            "INSERT INTO ttool_runs (run_name, result_path, row_count, created_utc) VALUES (?, ?, ?, ?)",
            (csv_path.parent.name, relative_or_absolute(csv_path, project_root), len(rows), utc_now()),
        )
        run_id = cur.lastrowid
        run_count += 1

        grouped: dict[int, list[dict]] = defaultdict(list)
        for row in rows:
            idx = to_float(row, "Realtime Test Index")
            case_idx = int(idx) if idx is not None else None
            fraction = idx - case_idx if idx is not None and case_idx is not None else None
            sample = {
                "realtime_test_index": idx,
                "test_case_index": case_idx,
                "sample_fraction": fraction,
                "vertical_force_n": to_float(row, "Vertical Force (N)"),
                "long_force_n": to_float(row, "Long Force (N)"),
                "lat_force_n": to_float(row, "Lat Force (N)"),
                "aligning_torque_nm": to_float(row, "Aligning Torque (Nm)"),
                "load_n": to_float(row, "Load (N)"),
                "slip_angle_deg": to_float(row, "Slip Angle (deg)"),
                "slip_ratio_pct": to_float(row, "Slip Ratio (%)"),
                "camber_deg": to_float(row, "Camber (deg)"),
                "pressure_kpa": to_float(row, "Gauge Pressure (kPa)"),
                "temperature_c": to_float(row, "Temperature (C)"),
                "long_vel_mps": to_float(row, "Long Vel (m/s)"),
                "lat_vel_mps": to_float(row, "Lat Vel (m/s)"),
                "rotation_rad_s": to_float(row, "Rotation (rad/s)"),
                "rotation_mps": to_float(row, "Rotation (m/s)"),
                "nominal_radius_m": to_float(row, "Nominal Radius (m)"),
                "dynamic_unloaded_radius_m": to_float(row, "Dynamic Unloaded Radius (m)"),
                "deflection_m": to_float(row, "Deflection (m)"),
            }
            conn.execute(
                """
                INSERT INTO ttool_samples (
                    run_id, realtime_test_index, test_case_index, sample_fraction,
                    vertical_force_n, long_force_n, lat_force_n, aligning_torque_nm,
                    load_n, slip_angle_deg, slip_ratio_pct, camber_deg, pressure_kpa,
                    temperature_c, long_vel_mps, lat_vel_mps, rotation_rad_s,
                    rotation_mps, nominal_radius_m, dynamic_unloaded_radius_m, deflection_m
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, *sample.values()),
            )
            sample_count += 1
            if case_idx is not None:
                grouped[case_idx].append(sample)

        for case_idx, samples in sorted(grouped.items()):
            conn.execute(
                """
                INSERT INTO behaviour_summaries (
                    run_id, test_case_index, sample_count, mean_vertical_force_n,
                    mean_long_force_n, mean_lat_force_n, peak_abs_vertical_force_n,
                    peak_abs_long_force_n, peak_abs_lat_force_n, mean_slip_angle_deg,
                    mean_slip_ratio_pct, mean_pressure_kpa, mean_temperature_c
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    case_idx,
                    len(samples),
                    mean(samples, "vertical_force_n"),
                    mean(samples, "long_force_n"),
                    mean(samples, "lat_force_n"),
                    peak_abs(samples, "vertical_force_n"),
                    peak_abs(samples, "long_force_n"),
                    peak_abs(samples, "lat_force_n"),
                    mean(samples, "slip_angle_deg"),
                    mean(samples, "slip_ratio_pct"),
                    mean(samples, "pressure_kpa"),
                    mean(samples, "temperature_c"),
                ),
            )

    return run_count, sample_count


def mean(samples: list[dict], key: str):
    values = [sample[key] for sample in samples if sample[key] is not None]
    return sum(values) / len(values) if values else None


def peak_abs(samples: list[dict], key: str):
    values = [sample[key] for sample in samples if sample[key] is not None]
    return max((abs(value) for value in values), default=None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rf2-root", type=Path, default=DEFAULT_RF2_ROOT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--tgm-cache", type=Path, default=DEFAULT_TGM_CACHE)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument(
        "--extra-tgm",
        type=Path,
        action="append",
        default=[],
        help="Additional loose .tgm file to copy into the cache and index. Can be passed multiple times.",
    )
    parser.add_argument(
        "--include-workshop-packages",
        action="store_true",
        help="Also scan workshop .rfcmp packages for TGM name hints. This can be slow.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path.cwd()
    conn = init_db(args.db)
    try:
        unique_tyres, loose_sources = insert_tyre_inventory(
            conn,
            project_root,
            args.rf2_root,
            args.tgm_cache,
            args.extra_tgm,
        )
        archive_candidates = insert_archive_candidates(conn, args.rf2_root, args.include_workshop_packages)
        runs, samples = insert_ttool_results(conn, project_root, args.results_root)
        conn.commit()
    finally:
        conn.close()

    print(f"Database: {args.db}")
    print(f"Unique loose tyres: {unique_tyres}")
    print(f"Loose TGM sources: {loose_sources}")
    print(f"Archive TGM candidates: {archive_candidates}")
    print(f"TTool runs: {runs}")
    print(f"TTool samples: {samples}")
    print(f"TGM cache: {args.tgm_cache}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
