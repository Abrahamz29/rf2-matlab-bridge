"""Inspect and reconstruct exports from the official Studio-397 TGM Gen ODS.

This is the first part of the MATLAB TGM Generator port: it treats the ODS as
the golden reference and extracts the generated text outputs without modifying
the workbook.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile


DEFAULT_ODS = Path("tools/downloads/studio397/TGM Gen V0.33 - GY F1 1975 Front.ods")

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "chart": "urn:oasis:names:tc:opendocument:xmlns:chart:1.0",
}

Q = {prefix: f"{{{uri}}}" for prefix, uri in NS.items()}


@dataclass
class Cell:
    text: str = ""
    value: str = ""
    formula: str = ""
    repeat: int = 1

    @property
    def display(self) -> str:
        return self.text if self.text != "" else self.value


def attr(element: ET.Element, namespace: str, name: str, default: str = "") -> str:
    return element.attrib.get(f"{Q[namespace]}{name}", default)


def read_xml(ods: Path, member: str) -> ET.Element:
    with ZipFile(ods) as zf:
        return ET.fromstring(zf.read(member))


def iter_tables(root: ET.Element) -> Iterable[ET.Element]:
    spreadsheet = root.find(".//office:spreadsheet", NS)
    if spreadsheet is None:
        return []
    return spreadsheet.findall("table:table", NS)


def table_name(table: ET.Element) -> str:
    return attr(table, "table", "name")


def cell_text(cell: ET.Element) -> str:
    parts: list[str] = []
    for paragraph in cell.findall(".//text:p", NS):
        parts.append("".join(paragraph.itertext()))
    return "\n".join(parts)


def cell_value(cell: ET.Element) -> str:
    for value_attr in ("string-value", "value", "date-value", "time-value", "boolean-value"):
        value = attr(cell, "office", value_attr)
        if value != "":
            return value
    return ""


def iter_row_cells(row: ET.Element) -> Iterable[tuple[int, Cell]]:
    col = 1
    for cell in row.findall("table:table-cell", NS):
        repeat = int(attr(cell, "table", "number-columns-repeated", "1"))
        yield col, Cell(
            text=cell_text(cell),
            value=cell_value(cell),
            formula=attr(cell, "table", "formula"),
            repeat=repeat,
        )
        col += repeat


def get_cell_display(table: ET.Element, row_index: int, col_index: int) -> str:
    rows = table.findall("table:table-row", NS)
    expanded_row = 1
    target_row: ET.Element | None = None
    for row in rows:
        repeat = int(attr(row, "table", "number-rows-repeated", "1"))
        if expanded_row <= row_index < expanded_row + repeat:
            target_row = row
            break
        expanded_row += repeat
    if target_row is None:
        return ""

    for col, cell in iter_row_cells(target_row):
        if col <= col_index < col + cell.repeat:
            return cell.display
    return ""


def get_table(root: ET.Element, name: str) -> ET.Element:
    for table in iter_tables(root):
        if table_name(table) == name:
            return table
    raise KeyError(f"Sheet not found in ODS: {name}")


def first_column_lines(table: ET.Element, row_count: int) -> list[str]:
    rows = table.findall("table:table-row", NS)
    lines: list[str] = []
    expanded_row = 1
    for row in rows:
        repeat = int(attr(row, "table", "number-rows-repeated", "1"))
        value = ""
        for col, cell in iter_row_cells(row):
            if col == 1:
                value = cell.display
                break
            if col > 1:
                break
        for _ in range(repeat):
            if expanded_row > row_count:
                return lines
            lines.append(value)
            expanded_row += 1
    return lines


def column_lines(table: ET.Element, col_index: int, skip_header: str | None = None) -> list[str]:
    lines: list[str] = []
    expanded_row = 1
    for row in table.findall("table:table-row", NS):
        repeat = int(attr(row, "table", "number-rows-repeated", "1"))
        value = ""
        for col, cell in iter_row_cells(row):
            if col <= col_index < col + cell.repeat:
                value = cell.display
                break
            if col > col_index:
                break
        if value != "":
            for _ in range(repeat):
                lines.append(value)
        expanded_row += repeat
        if expanded_row > 10000 and value == "":
            break
    if skip_header is not None and lines and lines[0] == skip_header:
        return lines[1:]
    return lines


def save_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def export_reference(ods: Path, out_dir: Path) -> dict:
    root = read_xml(ods, "content.xml")
    first_sheet = next(iter(iter_tables(root)))
    export_sheet = get_table(root, "Export")
    tbc_sheet = get_table(root, "TBC")

    final_row_value = get_cell_display(first_sheet, 31, 4)
    if final_row_value == "":
        raise ValueError("Could not read About!D31 lookup final row from ODS")
    export_row_count = int(float(final_row_value)) + 1

    tgm_lines = first_column_lines(export_sheet, export_row_count)
    tbc_lines = column_lines(tbc_sheet, 15, skip_header="Output")

    tgm_path = out_dir / "reference_from_ods.tgm"
    tbc_path = out_dir / "reference_from_ods.tbc"
    save_lines(tgm_path, tgm_lines)
    save_lines(tbc_path, tbc_lines)

    report = inspect_ods(ods)
    report["exports"] = {
        "tgm": {
            "path": str(tgm_path),
            "line_count": len(tgm_lines),
            "source_sheet": "Export",
            "row_count_source": "About!D31 + 1",
        },
        "tbc": {
            "path": str(tbc_path),
            "line_count": len(tbc_lines),
            "source_sheet": "TBC",
            "source_column": "O",
        },
    }
    report_path = out_dir / "tgm_gen_ods_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def strip_generated_lookup_blocks(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped.split("]", 1)[0].strip("[")
            skipping = section in {"LookupV2", "PatchV1"}
        if not skipping:
            kept.append(line.rstrip())
    return "\n".join(kept).strip() + "\n"


def normalize_export_text(text: str, strip_lookup: bool = False) -> str:
    normalized = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    if strip_lookup:
        normalized = strip_generated_lookup_blocks(normalized)
    return normalized.strip() + "\n"


def compare_files(reference: Path, candidate: Path, strip_lookup: bool = False) -> dict:
    ref = normalize_export_text(reference.read_text(encoding="utf-8", errors="ignore"), strip_lookup=strip_lookup)
    cand = normalize_export_text(candidate.read_text(encoding="utf-8", errors="ignore"), strip_lookup=strip_lookup)
    ref_lines = ref.splitlines()
    cand_lines = cand.splitlines()
    first_diff = None
    for index, (left, right) in enumerate(zip(ref_lines, cand_lines), start=1):
        if left != right:
            first_diff = {"line": index, "reference": left, "candidate": right}
            break
    if first_diff is None and len(ref_lines) != len(cand_lines):
        first_diff = {
            "line": min(len(ref_lines), len(cand_lines)) + 1,
            "reference": "<EOF>" if len(ref_lines) < len(cand_lines) else ref_lines[min(len(ref_lines), len(cand_lines))],
            "candidate": "<EOF>" if len(cand_lines) < len(ref_lines) else cand_lines[min(len(ref_lines), len(cand_lines))],
        }
    return {
        "equal": ref == cand,
        "reference_lines": len(ref_lines),
        "candidate_lines": len(cand_lines),
        "first_diff": first_diff,
        "strip_lookup": strip_lookup,
    }


def inspect_ods(ods: Path) -> dict:
    root = read_xml(ods, "content.xml")
    sheet_reports: list[dict] = []
    function_counts: dict[str, int] = {}

    for table in iter_tables(root):
        name = table_name(table)
        row_count = 0
        formula_count = 0
        nonempty_count = 0
        for row in table.findall("table:table-row", NS):
            row_count += int(attr(row, "table", "number-rows-repeated", "1"))
            for _, cell in iter_row_cells(row):
                if cell.formula:
                    formula_count += cell.repeat
                    for match in re.finditer(r"(?<![A-Za-z0-9_\.])([A-Z][A-Z0-9_]*)\s*\(", cell.formula):
                        function_counts[match.group(1)] = function_counts.get(match.group(1), 0) + cell.repeat
                if cell.display != "" or cell.formula:
                    nonempty_count += cell.repeat
        sheet_reports.append(
            {
                "name": name,
                "rows": row_count,
                "formula_count": formula_count,
                "nonempty_or_formula_cells": nonempty_count,
            }
        )

    return {
        "ods": str(ods),
        "sheet_count": len(sheet_reports),
        "sheets": sheet_reports,
        "formula_count": sum(sheet["formula_count"] for sheet in sheet_reports),
        "formula_functions": dict(sorted(function_counts.items())),
        "formula_engine_status": "inventory_only",
        "excluded_generated_sections": ["LookupV2", "PatchV1"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Print ODS formula and sheet inventory")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    export_parser = subparsers.add_parser("export-reference", help="Write reference .tgm/.tbc files reconstructed from ODS outputs")
    export_parser.add_argument("--out-dir", type=Path, default=Path("tmp/tgm_gen_port"))
    export_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    compare_parser = subparsers.add_parser("compare", help="Compare two generated export files")
    compare_parser.add_argument("reference", type=Path)
    compare_parser.add_argument("candidate", type=Path)
    compare_parser.add_argument("--strip-lookup", action="store_true")
    compare_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command in {"inspect", "export-reference"} and not args.ods.exists():
        raise FileNotFoundError(f"ODS not found: {args.ods}")

    if args.command == "inspect":
        report = inspect_ods(args.ods)
    elif args.command == "export-reference":
        report = export_reference(args.ods, args.out_dir)
    else:
        report = compare_files(args.reference, args.candidate, strip_lookup=args.strip_lookup)

    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0 if report.get("equal", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
