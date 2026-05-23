#!/usr/bin/env python3
"""Static smoke checks for the MATLAB uihtml TGM Generator frontend."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "tyres" / "matlab" / "apps" / "tgm_generator"
HTML_PATH = APP_DIR / "assets" / "rf2_tgm_generator.html"
APP_PATH = APP_DIR / "rf2TgmGeneratorAppImpl.m"

EXPECTED_BUTTON_COMMANDS = {
    "inputs-button": "loadOdsInputs",
    "save-project-button": "saveProjectInputs",
    "load-project-button": "loadProjectInputs",
    "chart-data-button": "loadOdsChartData",
    "generate-inputs-button": "generateFromInputs",
    "acceptance-button": "runAcceptance",
    "formula-button": "runFormulaReport",
    "prepare-ttool-button": "prepareTTool",
    "reload-button": "loadTgm",
    "ping-button": "ping",
}

EXPECTED_TABS = {
    "overview",
    "geometry",
    "construction",
    "materials",
    "materiallibrary",
    "realtime",
    "wlf",
    "contactprops",
    "loadsens",
    "tgmexport",
    "tbcexport",
    "validation",
    "crosssection",
    "materialcurves",
    "plystack",
    "behaviour",
    "odscharts",
    "input-general",
    "input-geometry",
    "input-construction",
    "input-compound",
    "input-realtime",
    "input-wlf",
    "input-contactprops",
    "input-loadsens",
    "input-materials",
    "input-tbc",
}

EXPECTED_INLINE_FUNCTIONS = {
    "activateInputSheet",
    "changeInputPage",
    "updateInputValue",
    "setInputFilter",
    "setEditableOnlyFilter",
}

EXPECTED_AXIS_LABELS = {
    "Lateral coordinate Y [mm]",
    "Radial coordinate X [mm]",
    "Temperature [K]",
    "Young's modulus [MPa]",
    "Young's modulus [Pa, log]",
    "Node index [-]",
    "Ply angle [deg]",
    "Ply thickness [m]",
    "Slip angle [deg]",
    "Lateral force Fy [N]",
    "Slip ratio [%]",
    "Longitudinal force Fx [N]",
    "Realtime test index [-]",
    "Force [N]",
    "Domain",
    "Value",
}


def _matlab_cases(app_text: str) -> set[str]:
    return set(re.findall(r'case\s+"([^"]+)"', app_text))


def _function_names(html_text: str) -> set[str]:
    return set(re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", html_text))


def run_check() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    matlab_cases = _matlab_cases(app)
    function_names = _function_names(html)
    errors: list[str] = []

    if "function setup(htmlComponent)" not in html:
        errors.append("uihtml setup(htmlComponent) entrypoint is missing")

    if "html.DataChangedFcn" not in app:
        errors.append("MATLAB app does not assign DataChangedFcn")

    if 'id="tyre-select"' not in html:
        errors.append("missing tyre dropdown id: tyre-select")
    if 'getElementById("tyre-select")' not in html:
        errors.append("missing tyre dropdown binding")
    if "function renderTyreSelect" not in html:
        errors.append("missing tyre dropdown render helper")
    if "state.tyres = localListKnownTyres(inputPath)" not in app:
        errors.append("MATLAB state does not expose known tyres")
    if "localListKnownTyres" not in app:
        errors.append("MATLAB known-tyre inventory helper missing")

    for button_id, command in EXPECTED_BUTTON_COMMANDS.items():
        if f'id="{button_id}"' not in html:
            errors.append(f"missing toolbar button id: {button_id}")
        if f'getElementById("{button_id}")' not in html:
            errors.append(f"missing click binding for button: {button_id}")
        if f'command: "{command}"' not in html:
            errors.append(f"button {button_id} does not send command {command}")
        if command not in matlab_cases:
            errors.append(f"MATLAB handler case missing for command: {command}")

    tabs = set(re.findall(r'data-view="([^"]+)"', html))
    for tab in sorted(EXPECTED_TABS - tabs):
        errors.append(f"missing tab data-view: {tab}")

    for label in sorted(EXPECTED_AXIS_LABELS):
        if label not in html:
            errors.append(f"missing plot axis label: {label}")

    for function_name in [
        "makePlotFrame",
        "drawAxes",
        "drawLegend",
        "drawPlyThickness",
        "drawPlyCrossSection",
        "drawRubberCrossSection",
    ]:
        if function_name not in function_names:
            errors.append(f"plot helper function missing: {function_name}")

    if "state.plotData?.plyCrossSection || []" not in html:
        errors.append("cross-section plot does not receive plyCrossSection data")
    if "state.plotData?.rubberCrossSection || []" not in html:
        errors.append("cross-section plot does not receive rubberCrossSection data")
    if "encoded.rubberCrossSection = localTableToRecords(plotData.rubberCrossSection)" not in app:
        errors.append("MATLAB state does not expose rubberCrossSection data")

    for function_name in [
        "buildInputPresentation",
        "renderInputSheetGrid",
        "renderSheetCell",
        "sheetCellStyle",
        "columnName",
        "nearestLeftLabel",
        "nearestAboveLabel",
        "nearestSectionLabel",
        "sheetContextLabel",
    ]:
        if function_name not in function_names:
            errors.append(f"input presentation helper missing: {function_name}")

    for class_name in [
        "sheet-layout",
        "sheet-grid",
        "sheet-cell",
        "sheet-col-header",
        "sheet-row-header",
        "sheet-cell-context",
    ]:
        if class_name not in html:
            errors.append(f"spreadsheet input layout class missing: {class_name}")

    if "<th>Context</th><th>Parameter</th>" in html:
        errors.append("input UI still renders the old linear context/parameter table")
    if "<th>${sheet} Cell</th>" in html:
        errors.append("input table still leads with raw cell addresses")
    if "`${item.sheet}!${item.address}`" not in html or 'title="${escapeAttr(title)}"' not in html:
        errors.append("input cell address is not preserved in sheet-cell tooltip")
    if "renderInputSheetGrid(sheet, visibleRows, columns, visibleInputs)" not in html:
        errors.append("input block does not render the ODS-like sheet grid")
    if "columnName(col)" not in html:
        errors.append("spreadsheet input grid does not render Excel-style column labels")

    if "equalScale: true" not in html:
        errors.append("cross-section plot does not request equalScale: true")
    expected_geometry_call = (
        'makePlotFrame(svg, xs, ys, "Radial coordinate X [mm]", '
        '"Lateral coordinate Y [mm]", { equalScale: true'
    )
    if expected_geometry_call not in html:
        errors.append("cross-section plot does not use swapped X/Y labels")
    if "xMm: Number(p.x) * 1000" not in html:
        errors.append("cross-section x-axis does not convert Geometry.x to millimetres")
    if "yMm: Number(p.y) * 1000" not in html:
        errors.append("cross-section y-axis does not convert Geometry.y to millimetres")

    for function_name in sorted(EXPECTED_INLINE_FUNCTIONS):
        if function_name not in function_names:
            errors.append(f"inline handler function missing: {function_name}")

    onclick_calls = set(re.findall(r'on(?:click|input|change)="([A-Za-z_][A-Za-z0-9_]*)\(', html))
    for call in sorted(onclick_calls - function_names):
        errors.append(f"inline handler references undefined function: {call}")

    return {
        "passed": not errors,
        "html": str(HTML_PATH.relative_to(REPO_ROOT)),
        "matlab_app": str(APP_PATH.relative_to(REPO_ROOT)),
        "button_count": len(EXPECTED_BUTTON_COMMANDS),
        "tab_count": len(tabs),
        "matlab_command_count": len(matlab_cases),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Write machine-readable JSON.")
    args = parser.parse_args(argv)
    report = run_check()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"UI static smoke: {'passed' if report['passed'] else 'failed'}")
        print(f"Buttons: {report['button_count']}")
        print(f"Tabs: {report['tab_count']}")
        for error in report["errors"]:
            print(f"- {error}", file=sys.stderr)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
