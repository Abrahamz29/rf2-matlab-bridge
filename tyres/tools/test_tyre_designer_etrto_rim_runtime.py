#!/usr/bin/env python3
"""Runtime checks for the Tyre Designer ETRTO R.8/R.11 rim contour."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = REPO_ROOT / "tyres" / "matlab" / "apps" / "tyre_designer" / "assets" / "tyre_designer.html"


def run_check() -> dict:
    errors: list[str] = []
    if not HTML_PATH.is_file():
        return {"passed": False, "html": str(HTML_PATH), "errors": [f"missing file: {HTML_PATH}"]}

    node = shutil.which("node")
    if not node:
        return {"passed": False, "html": str(HTML_PATH.relative_to(REPO_ROOT)), "errors": ["node executable not found"]}

    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(r"<script>\s*([\s\S]*?)\s*</script>", html)
    if not match:
        return {"passed": False, "html": str(HTML_PATH.relative_to(REPO_ROOT)), "errors": ["missing script block"]}

    js = f"""
globalThis.window = {{ addEventListener() {{}}, removeEventListener() {{}} }};
globalThis.document = {{
  getElementById() {{ return null; }},
  querySelectorAll() {{ return []; }},
  querySelector() {{ return null; }},
  addEventListener() {{}},
  removeEventListener() {{}},
  body: {{ dataset: {{}}, style: {{}} }},
  documentElement: {{ style: {{}} }},
}};
globalThis.localStorage = {{
  getItem() {{ return null; }},
  setItem() {{}},
  removeItem() {{}},
}};
{match.group(1)}

const standardCases = [];
const rimWidths = [10.5, 11.5, 12.5];
const rimDiameters = [17, 21, 24];
for (const rimWidthIn of rimWidths) {{
  for (const rimDiameterIn of rimDiameters) {{
    const model = generateTyreContour({{ rimWidthIn, rimDiameterIn }});
    const rim = generateEtrtoRimProfile(model);
    standardCases.push({{
      rimWidthIn,
      rimDiameterIn,
      passed: !!rim.verification?.passed,
      errors: rim.verification?.errors || [],
      verification: rim.verification,
      finite: rim.outerRows.every(row => Number.isFinite(row.xMm) && Number.isFinite(row.yMm)),
      humpCount: rim.humps.length,
    }});
  }}
}}

const diagnosticModel = generateTyreContour({{
  rimWidthIn: 11.5,
  rimDiameterIn: 21,
  rimFlangeWidthMm: 15,
  rimFlangeHeightMm: 17.9,
  rimBeadSeatLengthMm: 30,
  rimWellDepthMm: 35,
  rimLedgeLengthMm: 40,
  rimDropCenterSpanMm: 18,
  rimFlangeRadiusR1Mm: 24,
  rimBeadSeatRadiusR2Mm: 1.5,
  rimWellAngleDeg: 35,
}});
const diagnosticRim = generateEtrtoRimProfile(diagnosticModel);

const overrideModel = generateTyreContour({{
  rimWidthIn: 11.5,
  rimDiameterIn: 21,
  rimFlangeWidthMm: 15,
  rimHumpRadiusR3Mm: 9,
  rimHumpRadiusR8Mm: 11.5,
}});
const overrideDisplayedRim = generateEtrtoRimProfile(overrideModel);
const overrideReferenceRim = generatorDisplayEtrtoReferenceRim(overrideModel);
const overrideDisplayedMaxY = Math.max(...overrideDisplayedRim.humps.flat().map(row => Math.abs(row.yMm)));
const overrideReferenceMaxY = Math.max(...overrideReferenceRim.humps.flat().map(row => Math.abs(row.yMm)));
const overrideReferenceCheck = {{
  displayedR3Mm: overrideDisplayedRim.dimensions.humpR3Mm,
  displayedR8Mm: overrideDisplayedRim.dimensions.humpR8Mm,
  referenceMaxY: overrideReferenceMaxY,
  displayedMaxY: overrideDisplayedMaxY,
  hasReferenceRows: overrideReferenceRim.outerRows.length > 0 && overrideReferenceRim.humps.length === 2,
  separatesOverride: Math.abs(overrideDisplayedMaxY - overrideReferenceMaxY) > 1,
}};

const maxErrors = standardCases.reduce((acc, row) => {{
  for (const [key, value] of Object.entries(row.verification || {{}})) {{
    if (typeof value === "number" && Number.isFinite(value)) {{
      acc[key] = Math.max(acc[key] || 0, Math.abs(value));
    }}
  }}
  return acc;
}}, {{}});

const failures = standardCases.filter(row => !row.passed || !row.finite || row.humpCount !== 2);
const diagnosticErrors = diagnosticRim.verification?.errors || [];
console.log(JSON.stringify({{
  standardCaseCount: standardCases.length,
  failures,
  maxErrors,
  diagnosticErrors,
  diagnosticPassed: !!diagnosticRim.verification?.passed,
  overrideReferenceCheck,
}}, null, 2));
"""

    result = subprocess.run(
        [node, "-"],
        input=js,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return {
            "passed": False,
            "html": str(HTML_PATH.relative_to(REPO_ROOT)),
            "errors": [f"node returned {result.returncode}", result.stderr.strip()],
        }

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "passed": False,
            "html": str(HTML_PATH.relative_to(REPO_ROOT)),
            "errors": [f"could not parse node output: {exc}", result.stdout],
        }

    failures = payload.get("failures") or []
    if failures:
        errors.append(f"standard ETRTO rim cases failed: {json.dumps(failures, indent=2)}")

    max_errors = payload.get("maxErrors") or {}
    limits = {
        "dhRadiusErrorMm": 1e-6,
        "eErrorMm": 1e-6,
        "r3ErrorMm": 1e-6,
        "r8ErrorMm": 1e-6,
        "humpR8ArcCenterSideViolationMm": 1e-6,
        "humpR8CenterSideErrorMm": 1e-6,
        "humpR8SeatRadiusDirectionErrorDeg": 1e-5,
        "humpR8SeatTangentErrorDeg": 1e-5,
        "humpR3R8TangentErrorDeg": 1e-5,
        "humpR3R8DirectedTangentErrorDeg": 1e-5,
        "humpR3ConnectorDirectedTangentErrorDeg": 1e-5,
        "humpConnectorR8DirectedTangentErrorDeg": 1e-5,
        "humpR8SeatDirectedTangentErrorDeg": 1e-5,
        "hErrorMm": 1e-6,
        "qExcessMm": 1e-6,
        "gErrorMm": 1e-6,
        "bErrorMm": 1e-6,
        "r1ErrorMm": 1e-6,
        "r2ErrorMm": 1e-6,
        "r4ErrorMm": 1e-6,
        "r5ErrorMm": 1e-6,
        "betaErrorDeg": 1e-6,
        "lShortfallMm": 1e-6,
        "beadSeatLineErrorMm": 1e-6,
    }
    for key, limit in limits.items():
        value = float(max_errors.get(key, 0))
        if value > limit:
            errors.append(f"{key} exceeds {limit}: {value}")
    if float(max_errors.get("humpMaxSampleTurnDeg", 0)) > 35:
        errors.append(f"humpMaxSampleTurnDeg exceeds 35: {max_errors.get('humpMaxSampleTurnDeg')}")
    if float(max_errors.get("humpR3ArcSweepDeg", 0)) > 180:
        errors.append(f"humpR3ArcSweepDeg exceeds 180: {max_errors.get('humpR3ArcSweepDeg')}")
    if float(max_errors.get("humpR8ArcSweepDeg", 0)) > 135:
        errors.append(f"humpR8ArcSweepDeg exceeds 135: {max_errors.get('humpR8ArcSweepDeg')}")

    diagnostic_errors = set(payload.get("diagnosticErrors") or [])
    if payload.get("diagnosticPassed"):
        errors.append("over-constrained rim override should produce diagnostics")
    for expected in ["R.8 Q max exceeded", "R.8 L ledge length shortfall"]:
        if expected not in diagnostic_errors:
            errors.append(f"missing diagnostic for invalid rim override: {expected}")

    reference_check = payload.get("overrideReferenceCheck") or {}
    if not reference_check.get("hasReferenceRows"):
        errors.append("ETRTO reference overlay should produce outer rim rows and two humps")
    if not reference_check.get("separatesOverride"):
        errors.append("ETRTO reference overlay should ignore rim-contour overrides and remain nominal")

    return {
        "passed": not errors,
        "html": str(HTML_PATH.relative_to(REPO_ROOT)),
        "standardCaseCount": payload.get("standardCaseCount"),
        "maxErrors": max_errors,
        "diagnosticErrors": sorted(diagnostic_errors),
        "overrideReferenceCheck": reference_check,
        "errors": errors,
    }


def main() -> int:
    result = run_check()
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
