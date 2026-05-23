#!/usr/bin/env python3
"""Static smoke checks for the lightweight MATLAB tyre_designer UI."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "matlab" / "apps" / "tyre_designer"
HTML_PATH = APP_DIR / "assets" / "tyre_designer.html"
IMPL_PATH = APP_DIR / "tyre_designer_app.m"
ENTRY_PATH = REPO_ROOT / "matlab" / "tyre_designer.m"


def run_check() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    impl = IMPL_PATH.read_text(encoding="utf-8")
    entry = ENTRY_PATH.read_text(encoding="utf-8")
    function_names = set(re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", html))
    errors: list[str] = []

    for path in [HTML_PATH, IMPL_PATH, ENTRY_PATH]:
        if not path.is_file():
            errors.append(f"missing file: {path.relative_to(REPO_ROOT)}")

    for marker in [
        "function setup(htmlComponent)",
        'id="tyre-select"',
        'command: "loadTgm"',
        "drawGeometry",
        "drawRubber",
        "drawLayers",
        "rubberCrossSection",
        "plyCrossSection",
        "nodeThicknessM",
        "treadXMm",
        "Node thickness",
        "drawLineCallouts",
        "layoutCallouts",
        "nearestLayerRow",
    ]:
        if marker not in html:
            errors.append(f"missing HTML marker: {marker}")

    for function_name in [
        "drawGeometry",
        "drawRubber",
        "drawLayers",
        "drawLineCallouts",
        "layoutCallouts",
        "makeFrame",
        "drawAxes",
    ]:
        if function_name not in function_names:
            errors.append(f"missing JS function: {function_name}")

    for marker in [
        "sqlite(dbPath, \"readonly\")",
        "from tyres order by display_name",
        "tyre_designer_read_tgm(inputPath)",
        "tyre_designer_plot_data(model)",
        "tyre_designer_project_root()",
        "encoded.rubberCrossSection",
    ]:
        if marker not in impl:
            errors.append(f"missing MATLAB marker: {marker}")

    for forbidden in [
        "localLoadInputModel",
        "rf2TgmGenExtractInputsImpl",
        "localLoadMaterialLibrary",
        "rf2TgmGenMaterialLibraryImpl",
        "localLoadChartReport",
    ]:
        if forbidden in impl:
            errors.append(f"tyre_designer still depends on slow ODS path: {forbidden}")

    if "function varargout = tyre_designer(varargin)" not in entry:
        errors.append("missing clean tyre_designer entrypoint")
    if '"apps", "tyre_designer"' not in entry:
        errors.append("entrypoint does not target apps/tyre_designer")
    forbidden_names = [
        "rf2TgmGeometry",
        "rf2TyreDesigner",
        "tgm_geometry",
        "tgm_generator",
        "rf2TgmAppPath",
    ]
    for forbidden_name in forbidden_names:
        if forbidden_name in impl or forbidden_name in entry:
            errors.append(f"legacy app reference remains: {forbidden_name}")

    return {
        "passed": not errors,
        "html": str(HTML_PATH.relative_to(REPO_ROOT)),
        "matlab_impl": str(IMPL_PATH.relative_to(REPO_ROOT)),
        "entrypoint": str(ENTRY_PATH.relative_to(REPO_ROOT)),
        "errors": errors,
    }


def main() -> int:
    report = run_check()
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
