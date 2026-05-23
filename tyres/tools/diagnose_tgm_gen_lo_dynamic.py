"""Diagnose dynamic LibreOffice recalculation for the TGM Gen ODS replacement.

This tool edits selected ODS input cells in headless LibreOffice, lets Calc
recalculate the workbook, exports the ODS reference text, then applies the same
edits to the JSON project model and checks that the generator still writes the
same .tgm/.tbc content. LookupV2/PatchV1 are excluded from the TGM comparison.

The installed LibreOffice build may not be an authoritative golden reference for
this old workbook. In that case the report is still useful: it shows whether
Calc itself produced formula errors such as #WERT! after recalculation.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tgm_gen_ods as tgm


DEFAULT_ODS = Path("tyres/downloads/studio397/TGM Gen V0.33 - GY F1 1975 Front.ods")
DEFAULT_OUT_DIR = Path("tmp/tgm_gen_lo_dynamic")
DEFAULT_SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
DEFAULT_LO_PYTHON = Path(r"C:\Program Files\LibreOffice\program\python.exe")


@dataclass
class CellEdit:
    sheet: str
    address: str
    value: str


def ensure_uno_runtime() -> None:
    try:
        import uno  # noqa: F401
        return
    except ImportError:
        pass
    lo_python = Path(os.environ.get("LIBREOFFICE_PYTHON", DEFAULT_LO_PYTHON))
    if not lo_python.exists():
        raise RuntimeError("LibreOffice Python with UNO support was not found.")
    completed = subprocess.run([str(lo_python), str(Path(__file__).resolve()), *sys.argv[1:]], check=False)
    raise SystemExit(completed.returncode)


def parse_edit(text: str) -> CellEdit:
    if "=" not in text or "!" not in text:
        raise argparse.ArgumentTypeError("Expected SHEET!CELL=value, for example General!B3=278")
    location, value = text.split("=", 1)
    sheet, address = location.split("!", 1)
    if not sheet or not address:
        raise argparse.ArgumentTypeError("Expected SHEET!CELL=value")
    return CellEdit(sheet=sheet, address=address, value=value)


def prop(name: str, value: Any) -> Any:
    import uno

    item = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    item.Name = name
    item.Value = value
    return item


def file_url(path: Path) -> str:
    import uno

    return uno.systemPathToFileUrl(str(path.resolve()))


def connect_uno(port: int, timeout_s: float = 30.0) -> Any:
    import uno

    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local_ctx)
    url = f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return resolver.resolve(url)
        except Exception as exc:  # UNO raises generic bridge exceptions here.
            last_error = exc
            time.sleep(0.4)
    raise RuntimeError(f"Could not connect to LibreOffice UNO on port {port}: {last_error}")


def start_soffice(soffice: Path, profile_dir: Path, port: int) -> subprocess.Popen:
    profile_dir.mkdir(parents=True, exist_ok=True)
    accept = f"socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
    command = [
        str(soffice),
        "--headless",
        "--nologo",
        "--nodefault",
        "--norestore",
        "--nofirststartwizard",
        "--nolockcheck",
        f"-env:UserInstallation={file_url(profile_dir)}",
        f"--accept={accept}",
    ]
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def set_cell_value(sheet: Any, address: str, value: str) -> None:
    cell = sheet.getCellRangeByName(address)
    try:
        numeric = float(value)
    except ValueError:
        cell.String = value
    else:
        cell.Value = numeric


def recalculate_with_libreoffice(ods: Path, out_path: Path, edits: list[CellEdit], soffice: Path, out_dir: Path) -> None:
    if not soffice.exists():
        raise FileNotFoundError(f"LibreOffice soffice.exe not found: {soffice}")
    profile_dir = out_dir / "lo-profile"
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    source_ods = out_dir / "source.ods"
    source_ods.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ods, source_ods)
    port = random.randint(23000, 24999)
    process = start_soffice(soffice, profile_dir, port)
    try:
        ctx = connect_uno(port)
        service_manager = ctx.ServiceManager
        desktop = service_manager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(
            file_url(source_ods),
            "_blank",
            0,
            (
                prop("Hidden", True),
                prop("ReadOnly", False),
                prop("MacroExecutionMode", 4),
                prop("UpdateDocMode", 3),
            ),
        )
        if doc is None:
            raise RuntimeError(f"LibreOffice could not open {ods}")
        try:
            sheets = doc.getSheets()
            for edit in edits:
                set_cell_value(sheets.getByName(edit.sheet), edit.address, edit.value)
            doc.calculateAll()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            doc.storeAsURL(file_url(out_path), (prop("FilterName", "calc8"), prop("Overwrite", True)))
        finally:
            doc.close(True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def apply_project_edits(project: dict, edits: list[CellEdit]) -> dict:
    edit_map = {(edit.sheet, edit.address.upper()): edit.value for edit in edits}
    applied = 0
    for record in project.get("inputs", []):
        key = (str(record.get("sheet", "")), str(record.get("address", "")).upper())
        if key in edit_map:
            value = edit_map[key]
            record["value"] = value
            record["parsed"] = value
            record["display"] = value
            applied += 1
    if applied != len(edit_map):
        missing = sorted(f"{sheet}!{address}" for (sheet, address) in edit_map if not any(
            str(record.get("sheet", "")) == sheet and str(record.get("address", "")).upper() == address
            for record in project.get("inputs", [])
        ))
        raise KeyError(f"Project input edits not found: {missing}")
    return project


def run_dynamic_golden(ods: Path, out_dir: Path, edits: list[CellEdit], mode: str, soffice: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    recalculated_ods = out_dir / "recalculated.ods"
    recalculate_with_libreoffice(ods, recalculated_ods, edits, soffice, out_dir)

    reference_dir = out_dir / "reference"
    generated_dir = out_dir / "generated"
    reference = tgm.export_reference(recalculated_ods, reference_dir)

    project = tgm.extract_input_model(ods)
    project = apply_project_edits(project, edits)
    project_path = out_dir / "inputs_edited.json"
    project_path.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8")
    generated = tgm.generate_exports(ods, generated_dir, mode=mode, fallback_on_error=False, project_path=project_path)

    tgm_compare = tgm.compare_files(reference_dir / "reference_from_ods.tgm", generated_dir / "generated.tgm", strip_lookup=True)
    tbc_compare = tgm.compare_files(reference_dir / "reference_from_ods.tbc", generated_dir / "generated.tbc", strip_lookup=False)
    return {
        "ods": str(ods),
        "recalculated_ods": str(recalculated_ods),
        "out_dir": str(out_dir),
        "mode": mode,
        "edits": [edit.__dict__ for edit in edits],
        "project_path": str(project_path),
        "reference": reference["exports"],
        "generated": generated["outputs"],
        "override_count": generated["override_count"],
        "fallback_count": generated["fallback_count"],
        "tgm": tgm_compare,
        "tbc": tbc_compare,
        "passed": bool(tgm_compare["equal"] and tbc_compare["equal"] and generated["fallback_count"] == 0),
    }


def main() -> int:
    ensure_uno_runtime()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--mode", choices=["recursive", "cached"], default="recursive")
    parser.add_argument("--soffice", type=Path, default=Path(os.environ.get("LIBREOFFICE_SOFFICE", DEFAULT_SOFFICE)))
    parser.add_argument("--set", dest="edits", action="append", type=parse_edit, default=None)
    parser.add_argument("--strict", action="store_true", help="Return a non-zero exit code when the comparison fails.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    edits = args.edits or [CellEdit("General", "B3", "278")]
    report = run_dynamic_golden(args.ods, args.out_dir, edits, args.mode, args.soffice)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"edits: {report['edits']}")
        print(f"tgm_equal_without_lookup_patch: {report['tgm']['equal']}")
        print(f"tbc_equal: {report['tbc']['equal']}")
        print(f"fallback: {report['fallback_count']}")
        print(f"passed: {report['passed']}")
    return 0 if report["passed"] or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())

