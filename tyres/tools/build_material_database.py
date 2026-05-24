#!/usr/bin/env python3
"""Build the tyre material SQLite database from the TGM Gen Materials sheet."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

from tgm_gen_ods import extract_material_library


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ODS_CANDIDATES = [
    REPO_ROOT / "input" / "TGM Gen V0.33 - GY F1 1975 Front.ods",
    REPO_ROOT / "tyres" / "downloads" / "studio397" / "TGM Gen V0.33 - GY F1 1975 Front.ods",
]
DEFAULT_DB = REPO_ROOT / "tyres" / "database" / "rf2_material_database.sqlite"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=None, help="TGM Gen ODS file to read")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database to write")
    args = parser.parse_args()

    ods = args.ods or first_existing(DEFAULT_ODS_CANDIDATES)
    if ods is None:
        candidates = ", ".join(str(path) for path in DEFAULT_ODS_CANDIDATES)
        raise SystemExit(f"no TGM Gen ODS found; pass --ods. Checked: {candidates}")
    ods = ods.resolve()
    db_path = args.db.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    library = extract_material_library(ods)
    write_database(db_path, ods, library)
    print(f"wrote {db_path}")
    print(f"materials: {library['material_count']}, points: {library['point_count']}")
    return 0


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def write_database(db_path: Path, ods: Path, library: dict[str, Any]) -> None:
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("pragma foreign_keys = on")
        create_schema(conn)
        conn.executemany(
            "insert into metadata(key, value) values (?, ?)",
            [
                ("source_ods", str(ods)),
                ("sheet", str(library.get("sheet", "Materials"))),
                ("material_count", str(library.get("material_count", 0))),
                ("point_count", str(library.get("point_count", 0))),
            ],
        )

        category_ids: dict[str, int] = {}
        for category, count in sorted((library.get("category_counts") or {}).items()):
            point_count = int((library.get("category_point_counts") or {}).get(category, 0))
            cursor = conn.execute(
                """
                insert into categories(name, material_count, point_count)
                values (?, ?, ?)
                """,
                (category, int(count), point_count),
            )
            category_ids[str(category)] = int(cursor.lastrowid)

        for material in library.get("materials", []):
            category = str(material.get("category", ""))
            category_id = category_ids.get(category)
            if category_id is None:
                cursor = conn.execute(
                    "insert into categories(name, material_count, point_count) values (?, 0, 0)",
                    (category,),
                )
                category_id = int(cursor.lastrowid)
                category_ids[category] = category_id

            cursor = conn.execute(
                """
                insert into materials(
                    category_id, category, name, title, name_cell, start_col, end_col,
                    point_count, temperature_min_k, temperature_max_k,
                    youngs_modulus_min_pa, youngs_modulus_max_pa
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category_id,
                    category,
                    material.get("name"),
                    material.get("title"),
                    material.get("nameCell"),
                    material.get("startCol"),
                    material.get("endCol"),
                    material.get("pointCount"),
                    material.get("temperatureMinK"),
                    material.get("temperatureMaxK"),
                    material.get("youngsModulusMinPa"),
                    material.get("youngsModulusMaxPa"),
                ),
            )
            material_id = int(cursor.lastrowid)
            for point in material.get("points", []):
                conn.execute(
                    """
                    insert into material_points(
                        material_id, category, material, sample_index, col_index, address,
                        temperature_k, density_kg_m3, youngs_modulus_pa,
                        poissons_ratio, compression_tension_ratio,
                        specific_heat, thermal_conductivity,
                        longitudinal_conductivity, shore_a
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        material_id,
                        point.get("category"),
                        point.get("material"),
                        point.get("sampleIndex"),
                        point.get("col"),
                        point.get("address"),
                        point.get("temperatureK"),
                        point.get("densityKgM3"),
                        point.get("youngsModulusPa"),
                        point.get("poissonsRatio"),
                        point.get("compressionTensionRatio"),
                        point.get("specificHeat"),
                        point.get("thermalConductivity"),
                        point.get("longitudinalConductivity"),
                        point.get("shoreA"),
                    ),
                )

        conn.commit()
    finally:
        conn.close()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table metadata (
            key text primary key,
            value text not null
        );

        create table categories (
            id integer primary key,
            name text not null unique,
            material_count integer not null default 0,
            point_count integer not null default 0
        );

        create table materials (
            id integer primary key,
            category_id integer not null references categories(id),
            category text not null,
            name text not null,
            title text,
            name_cell text,
            start_col integer,
            end_col integer,
            point_count integer not null default 0,
            temperature_min_k real,
            temperature_max_k real,
            youngs_modulus_min_pa real,
            youngs_modulus_max_pa real
        );

        create table material_points (
            id integer primary key,
            material_id integer not null references materials(id) on delete cascade,
            category text not null,
            material text not null,
            sample_index integer,
            col_index integer,
            address text,
            temperature_k real,
            density_kg_m3 real,
            youngs_modulus_pa real,
            poissons_ratio real,
            compression_tension_ratio real,
            specific_heat real,
            thermal_conductivity real,
            longitudinal_conductivity real,
            shore_a real
        );

        create index idx_materials_category on materials(category);
        create index idx_materials_name on materials(name);
        create index idx_material_points_material_id on material_points(material_id);
        create index idx_material_points_temperature on material_points(temperature_k);
        """
    )


if __name__ == "__main__":
    raise SystemExit(main())
