"""Smoke tests for the tyre database builder."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tyres.tools import build_tyre_database as builder  # noqa: E402


def assert_close(actual: float, expected: float, tolerance: float = 1e-12) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def main() -> int:
    sample_tgm = ROOT / "tyres" / "input" / "tgm" / "G_9.2-20.0-13x10_Soft_Slick_1975.tgm"
    records = builder.parse_tgm_records(sample_tgm)
    first_geometry = next(record["value"] for record in records if record["section"] == "Node" and record["key"] == "Geometry")
    first_bulk = next(record["value"] for record in records if record["section"] == "Node" and record["key"] == "BulkMaterial")

    assert_close(first_geometry[0], 0.127325)
    assert_close(first_geometry[1], -0.170918)
    assert_close(first_geometry[2], 0.0129)
    assert_close(first_bulk[0], 273.15)
    assert_close(first_bulk[2], 15_000_000.0)
    assert_close(first_bulk[3], 0.47)

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "tyres.sqlite"
        conn = builder.init_db(db_path)
        try:
            cur = conn.execute(
                """
                INSERT INTO tyres
                    (sha256, file_name, display_name, local_copy_path, length_bytes, source_count, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("test", sample_tgm.name, sample_tgm.stem, str(sample_tgm), sample_tgm.stat().st_size, 1, builder.utc_now()),
            )
            tyre_id = cur.lastrowid
            builder.insert_tgm_property_values(conn, tyre_id, records)
            builder.insert_tgm_construction(conn, tyre_id, records)
            conn.commit()

            summary = conn.execute(
                """
                SELECT declared_num_layers, declared_num_sections, declared_num_nodes,
                       actual_node_count, max_ply_layers, ply_layer_count, material_row_count
                FROM tyre_construction_summary
                WHERE tyre_id = ?
                """,
                (tyre_id,),
            ).fetchone()
            if summary != (2, 238, 75, 75, 7, 406, 1112):
                raise AssertionError(f"unexpected construction summary: {summary!r}")

            node = conn.execute(
                """
                SELECT geometry_x_m, geometry_y_m, thickness_m, tread_depth_m, ring_and_rim_second
                FROM tyre_nodes
                WHERE tyre_id = ? AND node_index = 1
                """,
                (tyre_id,),
            ).fetchone()
            expected_node = (0.127325, -0.170918, 0.0129, 0.00143, 2_300_000_000.0)
            for actual, expected in zip(node, expected_node):
                assert_close(actual, expected)

            first_ply_material = conn.execute(
                """
                SELECT material_index, ply_index, sample_index, temperature_k, density_kg_m3,
                       youngs_modulus_pa, poisson_ratio, compression_multiplier,
                       specific_heat_j_kg_k, conductivity_w_m_k
                FROM tyre_material_rows
                WHERE tyre_id = ? AND node_index = 1 AND material_kind = 'PlyMaterial'
                ORDER BY source_line_number
                LIMIT 1
                """,
                (tyre_id,),
            ).fetchone()
            expected_ply_material = (1, 1, 1, 273.15, 7907.0, 34_000_000_000.0, 0.3, 0.4, 465.0, 26.0)
            for actual, expected in zip(first_ply_material, expected_ply_material):
                assert_close(actual, expected)

            schema_tables = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }
            for table_name in {
                "material_categories",
                "materials",
                "material_points",
                "tyre_material_mixes",
                "tyre_material_mix_assignments",
            }:
                if table_name not in schema_tables:
                    raise AssertionError(f"missing schema table: {table_name}")
        finally:
            conn.close()

    print("tyre database builder smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
