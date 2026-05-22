#!/usr/bin/env python3
"""Static smoke checks for the MATLAB uihtml TGM Generator frontend."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = REPO_ROOT / "matlab" / "assets" / "rf2_tgm_generator.html"
APP_PATH = REPO_ROOT / "matlab" / "rf2TgmGeneratorApp.m"

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
    "Lateral coordinate Y [m]",
    "Radial coordinate X [m]",
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

    for function_name in ["makePlotFrame", "drawAxes", "drawLegend", "drawPlyThickness"]:
        if function_name not in function_names:
            errors.append(f"plot helper function missing: {function_name}")

    for function_name in [
        "buildInputPresentation",
        "nearestLeftLabel",
        "nearestAboveLabel",
        "nearestSectionLabel",
        "sheetContextLabel",
    ]:
        if function_name not in function_names:
            errors.append(f"input presentation helper missing: {function_name}")

    if "<th>Context</th><th>Parameter</th>" not in html:
        errors.append("input table does not lead with context/parameter columns")
    if "<th>${sheet} Cell</th>" in html:
        errors.append("input table still leads with raw cell addresses")
    if 'title="${escapeAttr(`${item.sheet}!${item.address}`)}"' not in html:
        errors.append("input cell address is not preserved as tooltip")

    if "equalScale: true" not in html:
        errors.append("cross-section plot does not request equalScale: true")
    expected_geometry_call = (
        'makePlotFrame(svg, xs, ys, "Radial coordinate X [m]", '
        '"Lateral coordinate Y [m]", { equalScale: true'
    )
    if expected_geometry_call not in html:
        errors.append("cross-section plot does not use swapped X/Y labels")
    if "const xs = points.map(p => Number(p.x));" not in html:
        errors.append("cross-section x-axis does not use Geometry.x")
    if "const ys = points.map(p => Number(p.y));" not in html:
        errors.append("cross-section y-axis does not use Geometry.y")

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
