"""Build a local rFactor 2 tyre inventory and behaviour SQLite database."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RF2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\rFactor 2")
DEFAULT_DB = Path("scenarios/tyre/database/rf2_tyre_database.sqlite")
DEFAULT_TGM_CACHE = Path("tools/cache/tyres/tgm")
DEFAULT_RESULTS_ROOT = Path("scenarios/tyre/ttool/results")


TGM_PARAM_KEYS = {
    "QuasiStaticAnalysis": {
        "NumLayers",
        "NumSections",
        "RimVolume",
        "RealtimeCamberLimit",
        "GaugePressure",
        "CarcassTemperature",
        "RotationSquared",
        "NumNodes",
        "VolumeLoad",
        "LoadCamber",
        "LoadInclination",
        "LoadDeflection",
        "TotalMass",
        "TotalInertiaStandard",
        "RingMass",
        "RingInertiaStandard",
    },
    "Realtime": {
        "StaticBaseCoefficient",
        "SlidingBaseCoefficient",
        "TemporaryBristleSpring",
        "TemporaryBristleDamper",
        "MarbleEffectOnEffectiveLoad",
        "TerrainWeightOnContactTemperature",
        "WLFParameters",
        "StaticRoughnessEffect",
        "GrooveEffects",
        "DampnessEffects",
        "StaticCurve",
        "SlidingAdhesionCurve",
        "SlidingMicroDeformationCurve",
        "SlidingMacroDeformationCurve",
        "RubberPressureSensitivityPower",
        "SizeMultiplier",
        "ThermalDepthAtSurface",
        "ThermalDepthBelowSurface",
        "BristleLength",
        "InternalGasHeatTransfer",
        "ExternalGasHeatTransfer",
        "GroundContactConductance",
        "TireRadiationEmissivity",
        "InternalGasSpecificHeatAtConstantVolume",
        "TemporaryAbrasion",
    },
    "LookupData": {"Version", "Checksum", "Bin"},
    "Node": {"Geometry", "TreadDepth", "RingAndRim", "PlyParams"},
}


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


def clean_tgm_value(raw: str):
    value = raw.split("//", 1)[0].strip()
    if value.startswith("(") and value.endswith(")"):
        items = [parse_scalar(part.strip()) for part in value[1:-1].split(",") if part.strip()]
        return items
    return parse_scalar(value)


def parse_scalar(value: str):
    if value == "":
        return ""
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def parse_tgm(path: Path) -> dict[str, dict[str, list]]:
    parsed: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    section = ""

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("["):
                section = stripped.split("]", 1)[0].strip("[")
                continue
            if "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            key = key.strip()
            if key in TGM_PARAM_KEYS.get(section, set()):
                parsed[section][key].append(clean_tgm_value(raw_value))

    return {section: dict(values) for section, values in parsed.items()}


def discover_loose_tgms(rf2_root: Path) -> list[Path]:
    return sorted(
        path
        for path in rf2_root.rglob("*.tgm")
        if path.is_file() and "tools\\cache" not in str(path).lower()
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


def insert_tyre_inventory(conn: sqlite3.Connection, project_root: Path, rf2_root: Path, cache_dir: Path) -> tuple[int, int]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    sources_by_hash: dict[str, list[Path]] = defaultdict(list)
    for path in discover_loose_tgms(rf2_root):
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

        parsed = parse_tgm(primary)
        for section, values in parsed.items():
            for key, value_list in values.items():
                conn.execute(
                    "INSERT INTO tyre_parameters (tyre_id, section, key, value_json) VALUES (?, ?, ?, ?)",
                    (tyre_id, section, key, json.dumps(value_list, ensure_ascii=True)),
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
        unique_tyres, loose_sources = insert_tyre_inventory(conn, project_root, args.rf2_root, args.tgm_cache)
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
