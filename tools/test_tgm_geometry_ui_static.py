#!/usr/bin/env python3
"""Static smoke checks for the lightweight MATLAB TGM Geometry UI."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "matlab" / "apps" / "tgm_generator"
HTML_PATH = APP_DIR / "assets" / "rf2_tgm_geometry.html"
IMPL_PATH = APP_DIR / "rf2TgmGeometryAppImpl.m"
WRAPPER_PATH = REPO_ROOT / "matlab" / "rf2TgmGeometryApp.m"


def run_check() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    impl = IMPL_PATH.read_text(encoding="utf-8")
    wrapper = WRAPPER_PATH.read_text(encoding="utf-8")
    function_names = set(re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", html))
    errors: list[str] = []

    for path in [HTML_PATH, IMPL_PATH, WRAPPER_PATH]:
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
    ]:
        if marker not in html:
            errors.append(f"missing HTML marker: {marker}")

    for function_name in ["drawGeometry", "drawRubber", "drawLayers", "makeFrame", "drawAxes"]:
        if function_name not in function_names:
            errors.append(f"missing JS function: {function_name}")

    for marker in [
        "sqlite(dbPath, \"readonly\")",
        "from tyres order by display_name",
        "rf2ReadTgmImpl(inputPath)",
        "rf2TgmPlotDataImpl(model)",
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
            errors.append(f"Geometry UI still depends on slow ODS path: {forbidden}")

    if "rf2TgmGeometryAppImpl" not in wrapper:
        errors.append("wrapper does not call rf2TgmGeometryAppImpl")

    return {
        "passed": not errors,
        "html": str(HTML_PATH.relative_to(REPO_ROOT)),
        "matlab_impl": str(IMPL_PATH.relative_to(REPO_ROOT)),
        "errors": errors,
    }


def main() -> int:
    report = run_check()
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
