#!/usr/bin/env python3
"""Analyze TGM Gen ODS fields needed for text outputs and mark field usage.

By default the analysis traces the final tyre-model target:
- TGM text from Export column A up to About!D31 + 1.

It also traces the optional TBC output so the marked ODS can distinguish:
- unchanged cells that influence the final .tgm
- light blue cells that influence only the .tbc
- red cells that influence neither .tgm nor .tbc

It combines a static formula dependency walk, a dynamic recursive-evaluator
trace, ODS content-validations/dropdown sources, and Basic macro references.
The generated ODS copy marks non-formula project/input-like fields that are not
needed by any output in red.
"""

from __future__ import annotations

import argparse
import copy
import csv
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZipInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ODS = REPO_ROOT / "tools" / "downloads" / "studio397" / "TGM Gen V0.33 - GY F1 1975 Front.ods"
DEFAULT_OUT_DIR = REPO_ROOT / "tmp" / "tgm_gen_field_analysis"
DEFAULT_SHEETS = [
    "General",
    "Geometry",
    "Construction",
    "Compound",
    "Realtime",
    "WLF",
    "ContactProps",
    "LoadSens",
    "Materials",
    "TBC",
]
UNUSED_RED = "#ff4d4d"
TBC_ONLY_BLUE = "#b7e3ff"


def load_tgm_module():
    script_path = REPO_ROOT / "tools" / "tgm_gen_ods.py"
    spec = importlib.util.spec_from_file_location("tgm_gen_ods", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["tgm_gen_ods"] = module
    spec.loader.exec_module(module)
    return module


tgm = load_tgm_module()
NS = tgm.NS
Q = tgm.Q
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


@dataclass(frozen=True)
class CellKey:
    sheet: str
    row: int
    col: int

    @property
    def address(self) -> str:
        return tgm.row_col_to_a1(self.row, self.col)

    @property
    def label(self) -> str:
        return f"{self.sheet}!{self.address}"


class TrackingEvaluator(tgm.RecursiveFormulaEvaluator):
    def __init__(self, cells, named_ranges):
        super().__init__(cells, named_ranges, overrides=None, fallback_on_error=False)
        self.accessed: set[CellKey] = set()

    def ref(self, sheet: str, address: str) -> Any:
        row, col = tgm.a1_to_row_col(address)
        self.accessed.add(CellKey(sheet, row, col))
        return super().ref(sheet, address)


def key_tuple(key: CellKey) -> tuple[str, int, int]:
    return (key.sheet, key.row, key.col)


def cell_key_from_tuple(key: tuple[str, int, int]) -> CellKey:
    return CellKey(key[0], int(key[1]), int(key[2]))


def expand_address_meta(meta: dict[str, Any]) -> set[CellKey]:
    if meta.get("parseError") or not meta.get("sheet"):
        return set()
    sheet = str(meta["sheet"])
    if meta.get("type") == "cell":
        return {CellKey(sheet, int(meta["row"]), int(meta["col"]))}
    if meta.get("type") == "range":
        start_row = int(meta["startRow"])
        end_row = int(meta["endRow"])
        start_col = int(meta["startCol"])
        end_col = int(meta["endCol"])
        return {
            CellKey(sheet, row, col)
            for row in range(min(start_row, end_row), max(start_row, end_row) + 1)
            for col in range(min(start_col, end_col), max(start_col, end_col) + 1)
        }
    return set()


def expand_ref(ref: dict[str, Any]) -> set[CellKey]:
    try:
        if ref.get("type") == "cell":
            row, col = tgm.a1_to_row_col(ref["address"])
            return {CellKey(ref["sheet"], row, col)}
        if ref.get("type") == "range":
            start_row, start_col = tgm.a1_to_row_col(ref["start"])
            end_row, end_col = tgm.a1_to_row_col(ref["end"])
            return {
                CellKey(ref["sheet"], row, col)
                for row in range(min(start_row, end_row), max(start_row, end_row) + 1)
                for col in range(min(start_col, end_col), max(start_col, end_col) + 1)
            }
    except (KeyError, ValueError):
        return set()
    return set()


def export_targets(ods: Path, cells: dict[tuple[str, int, int], Any], target_mode: str) -> tuple[set[CellKey], dict[str, Any]]:
    root = tgm.read_xml(ods, "content.xml")
    first_sheet = next(iter(tgm.iter_tables(root)))
    final_row_value = tgm.get_cell_display(first_sheet, 31, 4)
    if final_row_value == "":
        raise RuntimeError("Could not read About!D31 export final row")
    export_row_count = int(float(final_row_value)) + 1

    targets = {CellKey("Export", row, 1) for row in range(1, export_row_count + 1)}
    tbc_rows = sorted(row for sheet, row, col in cells if sheet == "TBC" and col == 15)
    if target_mode == "tgm-tbc":
        targets.update(CellKey("TBC", row, 15) for row in tbc_rows)
    targets.add(CellKey("About", 31, 4))

    return targets, {
        "target_mode": target_mode,
        "export_row_count": export_row_count,
        "tgm_output_cells": export_row_count,
        "tbc_output_cells": len(tbc_rows) if target_mode == "tgm-tbc" else 0,
        "available_tbc_output_cells": len(tbc_rows),
        "target_count": len(targets),
    }


def static_dependency_walk(
    cells: dict[tuple[str, int, int], Any],
    named_ranges: dict[str, dict[str, str]],
    targets: set[CellKey],
) -> set[CellKey]:
    required: set[CellKey] = set(targets)
    queue = list(targets)
    seen_formulas: set[CellKey] = set()

    while queue:
        key = queue.pop()
        if key in seen_formulas:
            continue
        seen_formulas.add(key)
        cell = cells.get(key_tuple(key))
        if cell is None or not cell.formula:
            continue
        refs = tgm.refs_in_formula(cell.formula, cell.sheet)
        formula_text = cell.formula.replace("$", "")
        for name, named_range in named_ranges.items():
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", formula_text):
                refs.append({"type": "range", **named_range})
        for ref in refs:
            for dep in expand_ref(ref):
                if dep not in required:
                    required.add(dep)
                    if key_tuple(dep) in cells:
                        queue.append(dep)
    return required


def dynamic_dependency_trace(ods: Path, cells: dict[tuple[str, int, int], Any], targets: set[CellKey]) -> set[CellKey]:
    evaluator = TrackingEvaluator(cells, tgm.load_named_ranges(ods))
    for key in sorted(targets, key=lambda item: (item.sheet, item.row, item.col)):
        cell = cells.get(key_tuple(key))
        if cell is None:
            continue
        try:
            evaluator.evaluate(cell)
        except Exception as exc:  # noqa: BLE001 - report includes failures if official parity ever regresses.
            raise RuntimeError(f"Could not evaluate {key.label}: {exc}") from exc
    return evaluator.accessed | set(targets)


def required_for_targets(
    ods: Path,
    cells: dict[tuple[str, int, int], Any],
    named_ranges: dict[str, dict[str, str]],
    targets: set[CellKey],
    validations: dict[str, dict[str, Any]],
    validation_assignments: dict[CellKey, str],
    macro_refs: set[CellKey],
) -> tuple[set[CellKey], dict[str, int]]:
    static_required = static_dependency_walk(cells, named_ranges, targets)
    dynamic_required = dynamic_dependency_trace(ods, cells, targets)
    required = set(static_required) | set(dynamic_required) | set(macro_refs)
    validation_sources = validation_sources_for_required_inputs(required, validations, validation_assignments)
    material_dropdown_sources = material_dropdown_block_sources(named_ranges)
    required |= validation_sources | material_dropdown_sources
    return required, {
        "static_required_cells": len(static_required),
        "dynamic_required_cells": len(dynamic_required),
        "validation_source_cells": len(validation_sources),
        "material_dropdown_block_cells": len(material_dropdown_sources),
        "macro_referenced_cells": len(macro_refs),
        "union_required_cells": len(required),
    }


def load_validations_and_cell_assignments(ods: Path) -> tuple[dict[str, dict[str, Any]], dict[CellKey, str]]:
    root = tgm.read_xml(ods, "content.xml")
    validations: dict[str, dict[str, Any]] = {}
    for validation in root.findall(".//table:content-validation", NS):
        name = tgm.attr(validation, "table", "name")
        condition = tgm.attr(validation, "table", "condition")
        if not name:
            continue
        sources: set[CellKey] = set()
        for match in re.finditer(r"\[\$?([A-Za-z0-9_ ]+)\.\$?([A-Z]+)\$?(\d+):\$?([A-Za-z0-9_ ]+)\.\$?([A-Z]+)\$?(\d+)\]", condition):
            sheet = match.group(1)
            start = f"{match.group(2)}{match.group(3)}"
            end = f"{match.group(5)}{match.group(6)}"
            sources.update(expand_address_meta(tgm.address_report(f"{sheet}.{start}:{end}")))
        validations[name] = {
            "name": name,
            "condition": condition,
            "source_count": len(sources),
            "sources": sorted((source.label for source in sources)),
        }

    assignments: dict[CellKey, str] = {}
    for table in tgm.iter_tables(root):
        sheet = tgm.table_name(table)
        row_index = 1
        for row in table.findall("table:table-row", NS):
            row_repeat = int(tgm.attr(row, "table", "number-rows-repeated", "1"))
            raw_col = 1
            for element in row.findall("table:table-cell", NS):
                repeat = int(tgm.attr(element, "table", "number-columns-repeated", "1"))
                validation_name = tgm.attr(element, "table", "content-validation-name")
                if validation_name:
                    for row_offset in range(row_repeat):
                        for col_offset in range(repeat):
                            assignments[CellKey(sheet, row_index + row_offset, raw_col + col_offset)] = validation_name
                raw_col += repeat
            row_index += row_repeat
    return validations, assignments


def validation_sources_for_required_inputs(required: set[CellKey], validations: dict[str, dict[str, Any]], assignments: dict[CellKey, str]) -> set[CellKey]:
    sources: set[CellKey] = set()
    for key in required:
        validation_name = assignments.get(key)
        if not validation_name:
            continue
        for source_label in validations.get(validation_name, {}).get("sources", []):
            sheet, address = source_label.split("!", 1)
            row, col = tgm.a1_to_row_col(address)
            sources.add(CellKey(sheet, row, col))
    return sources


def material_dropdown_block_sources(named_ranges: dict[str, dict[str, str]]) -> set[CellKey]:
    """Keep full material data blocks because materials are selected by dropdown."""
    sources: set[CellKey] = set()
    material_rows_by_name = {
        int(block["name_row"]): sorted(int(row) for row in block["property_rows"].values())
        for block in tgm.MATERIAL_BLOCKS
    }
    for name, named_range in named_ranges.items():
        if not name.startswith("MaterialList") or named_range.get("sheet") != "Materials":
            continue
        start_row, start_col = tgm.a1_to_row_col(named_range["start"])
        end_row, end_col = tgm.a1_to_row_col(named_range["end"])
        rows = [start_row, *material_rows_by_name.get(start_row, [])]
        for row in rows:
            for col in range(min(start_col, end_col), max(start_col, end_col) + 1):
                sources.add(CellKey("Materials", row, col))
    return sources


def macro_report(ods: Path) -> tuple[dict[str, Any], set[CellKey]]:
    root = tgm.read_xml(ods, "content.xml")
    sheet_order = [tgm.table_name(table) for table in tgm.iter_tables(root)]
    refs: set[CellKey] = set()
    modules: list[dict[str, Any]] = []
    with ZipFile(ods) as zf:
        for name in sorted(n for n in zf.namelist() if n.startswith("Basic/Standard/") and n.endswith(".xml")):
            text = zf.read(name).decode("utf-8", "ignore")
            plain = "".join(ET.fromstring(text).itertext())
            plain = unescape(plain)
            module = {
                "path": name,
                "name": Path(name).stem,
                "cell_refs": [],
                "ranges": [],
                "sheet_names": sorted(set(re.findall(r'sheetName\s*=\s*"([^"]+)"', plain, flags=re.I))),
            }
            for match in re.finditer(r"(?:thisComponent\.)?sheets\((\d+)\)\.getCellRangebyName\(\"(\$?[A-Z]+\$?\d+)\"\)", plain, flags=re.I):
                sheet_index = int(match.group(1))
                if 0 <= sheet_index < len(sheet_order):
                    row, col = tgm.a1_to_row_col(match.group(2).replace("$", ""))
                    key = CellKey(sheet_order[sheet_index], row, col)
                    refs.add(key)
                    module["cell_refs"].append(key.label)
            for match in re.finditer(r'getCellRangebyName\("([^"]+)"\)', plain):
                module["ranges"].append(match.group(1))
            for match in re.finditer(r'\.Value\s*=\s*"([^"]+)"', plain):
                value = match.group(1)
                if re.fullmatch(r"\$?[A-Z]+\$?\d+(?::\$?[A-Z]+\$?\d+)?", value):
                    module["ranges"].append(value)
            modules.append(module)

    return {"sheet_order": sheet_order, "modules": modules, "referenced_cells": sorted(key.label for key in refs)}, refs


def classify_fields(
    ods: Path,
    cells: dict[tuple[str, int, int], Any],
    required: set[CellKey],
    tgm_required: set[CellKey],
    tbc_only_required: set[CellKey],
    validations: dict[str, dict[str, Any]],
    validation_assignments: dict[CellKey, str],
) -> tuple[list[dict[str, Any]], set[CellKey], set[CellKey]]:
    styles = tgm.load_cell_styles(ods)
    rows: list[dict[str, Any]] = []
    mark_red: set[CellKey] = set()
    mark_blue: set[CellKey] = set()
    for cell in sorted(cells.values(), key=lambda item: (item.sheet, item.row, item.col)):
        if cell.sheet not in DEFAULT_SHEETS or cell.formula:
            continue
        if cell.display == "" and cell.value == "":
            continue
        key = CellKey(cell.sheet, cell.row, cell.col)
        style = styles.get(cell.style_name, {})
        classification = tgm.classify_input_cell(cell, style)
        validation_name = validation_assignments.get(key, "")
        is_input_like = bool(classification["isPossibleInput"] or validation_name)
        is_required = key in required
        is_tgm_required = key in tgm_required
        is_tbc_only = key in tbc_only_required
        if is_input_like and is_tbc_only:
            mark_blue.add(key)
        elif is_input_like and not is_required:
            mark_red.add(key)
        if not is_input_like:
            usage_class = "non_input"
        elif is_tbc_only:
            usage_class = "tbc_only"
        elif is_tgm_required:
            usage_class = "tgm"
        elif is_required:
            usage_class = "output"
        else:
            usage_class = "unused"
        rows.append(
            {
                "sheet": cell.sheet,
                "address": cell.address,
                "display": cell.display,
                "value": cell.value,
                "style": cell.style_name,
                "background": style.get("backgroundColor", ""),
                "role": classification["inputRole"],
                "confidence": classification["editableConfidence"],
                "validation": validation_name,
                "validation_condition": validations.get(validation_name, {}).get("condition", "") if validation_name else "",
                "input_like": is_input_like,
                "needed_for_output": is_required,
                "needed_for_tgm": is_tgm_required,
                "tbc_only": is_tbc_only,
                "usage_class": usage_class,
                "mark_red": key in mark_red,
                "mark_blue": key in mark_blue,
            }
        )
    return rows, mark_red, mark_blue


def summarize(rows: list[dict[str, Any]], required: set[CellKey], targets: set[CellKey], macro_refs: set[CellKey]) -> dict[str, Any]:
    by_sheet: dict[str, dict[str, int]] = {}
    for row in rows:
        sheet = row["sheet"]
        item = by_sheet.setdefault(
            sheet,
            {
                "fields": 0,
                "input_like": 0,
                "needed": 0,
                "needed_for_tgm": 0,
                "tbc_only_marked_blue": 0,
                "unused_marked_red": 0,
            },
        )
        item["fields"] += 1
        item["input_like"] += int(bool(row["input_like"]))
        item["needed"] += int(bool(row["needed_for_output"]))
        item["needed_for_tgm"] += int(bool(row["needed_for_tgm"]))
        item["tbc_only_marked_blue"] += int(bool(row["mark_blue"]))
        item["unused_marked_red"] += int(bool(row["mark_red"]))
    return {
        "required_cell_count": len(required),
        "target_cell_count": len(targets),
        "macro_referenced_cell_count": len(macro_refs),
        "field_count": len(rows),
        "input_like_field_count": sum(1 for row in rows if row["input_like"]),
        "needed_field_count": sum(1 for row in rows if row["needed_for_output"]),
        "needed_for_tgm_field_count": sum(1 for row in rows if row["needed_for_tgm"]),
        "tbc_only_input_like_marked_blue_count": sum(1 for row in rows if row["mark_blue"]),
        "unused_input_like_marked_red_count": sum(1 for row in rows if row["mark_red"]),
        "by_sheet": dict(sorted(by_sheet.items())),
    }


def ensure_mark_style(root: ET.Element, original_style: str, style_map: dict[str, str], prefix: str, color: str) -> str:
    if original_style in style_map:
        return style_map[original_style]
    automatic = root.find(".//office:automatic-styles", NS)
    if automatic is None:
        raise RuntimeError("ODS content.xml has no office:automatic-styles")

    source = None
    if original_style:
        for style in automatic.findall("style:style", NS):
            if tgm.attr(style, "style", "name") == original_style and tgm.attr(style, "style", "family") == "table-cell":
                source = style
                break

    new_name = f"{prefix}_{len(style_map) + 1}"
    if source is None:
        new_style = ET.Element(Q["style"] + "style", {Q["style"] + "name": new_name, Q["style"] + "family": "table-cell"})
        props = ET.SubElement(new_style, Q["style"] + "table-cell-properties")
    else:
        new_style = copy.deepcopy(source)
        new_style.set(Q["style"] + "name", new_name)
        props = new_style.find("style:table-cell-properties", NS)
        if props is None:
            props = ET.SubElement(new_style, Q["style"] + "table-cell-properties")
    props.set(Q["fo"] + "background-color", color)
    automatic.append(new_style)
    style_map[original_style] = new_name
    return new_name


def split_cell_for_targets(row: ET.Element, cell_element: ET.Element, start_col: int, target_cols: list[int]) -> dict[int, ET.Element]:
    repeat = int(tgm.attr(cell_element, "table", "number-columns-repeated", "1"))
    target_cols = sorted(col for col in target_cols if start_col <= col < start_col + repeat)
    if not target_cols:
        return {}
    if repeat == 1:
        return {target_cols[0]: cell_element}

    insert_index = list(row).index(cell_element)
    row.remove(cell_element)
    pieces: list[ET.Element] = []
    targets: dict[int, ET.Element] = {}
    cursor = start_col
    for target_col in target_cols:
        if target_col > cursor:
            before = copy.deepcopy(cell_element)
            before.set(Q["table"] + "number-columns-repeated", str(target_col - cursor))
            pieces.append(before)
            cursor = target_col
        target = copy.deepcopy(cell_element)
        target.attrib.pop(Q["table"] + "number-columns-repeated", None)
        pieces.append(target)
        targets[target_col] = target
        cursor += 1
    end_col = start_col + repeat
    if cursor < end_col:
        after = copy.deepcopy(cell_element)
        after.set(Q["table"] + "number-columns-repeated", str(end_col - cursor))
        pieces.append(after)
    for offset, piece in enumerate(pieces):
        row.insert(insert_index + offset, piece)
    return targets


def mark_ods_copy(source: Path, destination: Path, mark_red: set[CellKey], mark_blue: set[CellKey]) -> dict[str, Any]:
    content = None
    with ZipFile(source, "r") as zin:
        content = zin.read("content.xml")
    root = ET.fromstring(content)
    style_maps: dict[str, dict[str, str]] = {"red": {}, "blue": {}}
    marked = {"red": 0, "blue": 0}
    skipped_repeated_rows = 0

    marks_by_sheet: dict[str, dict[int, dict[int, str]]] = {}
    for key in mark_red:
        marks_by_sheet.setdefault(key.sheet, {}).setdefault(key.row, {})[key.col] = "red"
    for key in mark_blue:
        marks_by_sheet.setdefault(key.sheet, {}).setdefault(key.row, {})[key.col] = "blue"

    for table in tgm.iter_tables(root):
        sheet = tgm.table_name(table)
        if sheet not in marks_by_sheet:
            continue
        row_index = 1
        for row in table.findall("table:table-row", NS):
            row_repeat = int(tgm.attr(row, "table", "number-rows-repeated", "1"))
            target_rows = [row_index + offset for offset in range(row_repeat) if row_index + offset in marks_by_sheet[sheet]]
            if row_repeat > 1 and target_rows:
                skipped_repeated_rows += len(target_rows)
                row_index += row_repeat
                continue
            if not target_rows:
                row_index += row_repeat
                continue
            target_cols = marks_by_sheet[sheet][row_index]
            col_index = 1
            for cell_element in list(row.findall("table:table-cell", NS)):
                repeat = int(tgm.attr(cell_element, "table", "number-columns-repeated", "1"))
                overlap = [col for col in target_cols if col_index <= col < col_index + repeat]
                if overlap:
                    targets = split_cell_for_targets(row, cell_element, col_index, overlap)
                    for target_col, target_element in targets.items():
                        color_name = target_cols[target_col]
                        original_style = tgm.attr(target_element, "table", "style-name")
                        if color_name == "blue":
                            style_name = ensure_mark_style(
                                root,
                                original_style,
                                style_maps["blue"],
                                "codex_tbc_only_blue",
                                TBC_ONLY_BLUE,
                            )
                        else:
                            style_name = ensure_mark_style(root, original_style, style_maps["red"], "codex_unused_red", UNUSED_RED)
                        target_element.set(Q["table"] + "style-name", style_name)
                        marked[color_name] += 1
                col_index += repeat
            row_index += row_repeat

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(source, "r") as zin, ZipFile(destination, "w") as zout:
        for info in zin.infolist():
            data = xml_bytes if info.filename == "content.xml" else zin.read(info.filename)
            new_info = ZipInfo(info.filename, info.date_time)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            new_info.comment = info.comment
            zout.writestr(new_info, data)
    return {
        "marked_cells": marked["red"] + marked["blue"],
        "red_marked_cells": marked["red"],
        "blue_marked_cells": marked["blue"],
        "skipped_repeated_rows": skipped_repeated_rows,
        "red_style_count": len(style_maps["red"]),
        "blue_style_count": len(style_maps["blue"]),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "sheet",
        "address",
        "display",
        "value",
        "role",
        "confidence",
        "validation",
        "input_like",
        "needed_for_output",
        "needed_for_tgm",
        "tbc_only",
        "usage_class",
        "mark_red",
        "mark_blue",
        "background",
        "style",
        "validation_condition",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def analyze(ods: Path, out_dir: Path, target_mode: str = "tgm") -> dict[str, Any]:
    cells = tgm.load_formula_cells(ods)
    named_ranges = tgm.load_named_ranges(ods)
    validations, validation_assignments = load_validations_and_cell_assignments(ods)
    macro_data, macro_refs = macro_report(ods)

    targets_tgm, target_report_tgm = export_targets(ods, cells, "tgm")
    targets_combined, target_report_combined = export_targets(ods, cells, "tgm-tbc")
    tgm_required, tgm_dependency_counts = required_for_targets(
        ods,
        cells,
        named_ranges,
        targets_tgm,
        validations,
        validation_assignments,
        macro_refs,
    )
    combined_required, combined_dependency_counts = required_for_targets(
        ods,
        cells,
        named_ranges,
        targets_combined,
        validations,
        validation_assignments,
        macro_refs,
    )
    tbc_only_required = combined_required - tgm_required
    if target_mode == "tgm-tbc":
        targets = targets_combined
        target_report = target_report_combined
        required = combined_required
        selected_dependency_counts = combined_dependency_counts
    else:
        targets = targets_tgm
        target_report = target_report_tgm
        required = tgm_required
        selected_dependency_counts = tgm_dependency_counts

    rows, mark_red, mark_blue = classify_fields(ods, cells, required, tgm_required, tbc_only_required, validations, validation_assignments)
    marked_ods = out_dir / (ods.stem + f" - field-usage-red-blue-{target_mode}.ods")
    mark_report = mark_ods_copy(ods, marked_ods, mark_red, mark_blue)

    field_csv = out_dir / f"field_usage_{target_mode}.csv"
    write_csv(field_csv, rows)
    summary = summarize(rows, required, targets, macro_refs)
    report = {
        "ods": str(ods),
        "target_mode": target_mode,
        "marked_ods": str(marked_ods),
        "field_csv": str(field_csv),
        "targets": target_report,
        "summary": summary,
        "dependency_counts": selected_dependency_counts,
        "required_sets": {
            "tgm_required_cells": len(tgm_required),
            "tgm_tbc_required_cells": len(combined_required),
            "tbc_only_required_cells": len(tbc_only_required),
            "tbc_only_input_like_fields": sum(1 for row in rows if row["input_like"] and row["tbc_only"]),
            "tgm_targets": target_report_tgm,
            "tgm_tbc_targets": target_report_combined,
            "tgm_dependency_counts": tgm_dependency_counts,
            "tgm_tbc_dependency_counts": combined_dependency_counts,
        },
        "validations": {
            "definition_count": len(validations),
            "assigned_cell_count": len(validation_assignments),
            "source_validation_count": sum(1 for item in validations.values() if item["source_count"] > 0),
        },
        "macros": macro_data,
        "marking": mark_report,
        "notes": [
            f"Light blue ({TBC_ONLY_BLUE}) marking is applied to non-formula input-like/project fields that are required only by the TBC output.",
            f"Red ({UNUSED_RED}) marking is applied to non-formula input-like/project fields on the main input sheets that are not required by TGM or TBC outputs.",
            "Formula cells are not colored red; they are internal calculation logic, not user input fields.",
            "Dropdown source ranges from output-relevant validated cells are preserved as required.",
            "LookupV2/PatchV1 generation remains outside this ODS output trace.",
            "Use --target tgm-tbc when the selected required set should include TBC output cells as output-relevant.",
        ],
    }
    report_path = out_dir / f"field_analysis_report_{target_mode}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--target", choices=["tgm", "tgm-tbc"], default="tgm", help="Output dependency target to preserve.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = analyze(args.ods, args.out_dir, target_mode=args.target)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Marked ODS: {report['marked_ods']}")
        print(f"Report: {report['report_path']}")
        print(f"TBC-only input-like fields marked blue: {report['summary']['tbc_only_input_like_marked_blue_count']}")
        print(f"Unused input-like fields marked red: {report['summary']['unused_input_like_marked_red_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
