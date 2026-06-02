#!/usr/bin/env python3
"""Build ETRTO R.8/R.11 rim overlay artifacts from the Tyre Designer JS."""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import base64
import struct
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = Path(__file__).resolve()
HTML_PATH = REPO_ROOT / "tyres" / "matlab" / "apps" / "tyre_designer" / "assets" / "tyre_designer.html"
ETRTO_PDF = REPO_ROOT / "input" / "ETRTO-Standards-Manual2017.pdf"
REF_DIR = REPO_ROOT / "tyres" / "analysis" / "_etrto_rim_reference"
DISPLAY_HTML = REPO_ROOT / "tyres" / "analysis" / "tyre_designer_display_rim_overlay.html"
DISPLAY_PNG = REPO_ROOT / "tyres" / "analysis" / "tyre_designer_display_rim_overlay.png"
SWEEP_JSON = REF_DIR / "etrto_rim_sweep_verification.json"
POINTS_JSON = REF_DIR / "rim_fit_points.json"
R8_DIAGRAM_PNG = REF_DIR / "etrto_R8_diagram.png"
R11_DIAGRAM_PNG = REF_DIR / "etrto_R11_diagram.png"
R8_BITMAP_OVERLAY_SVG = REF_DIR / "etrto_R8_bitmap_overlay.svg"
R8_BITMAP_OVERLAY_PNG = REF_DIR / "etrto_R8_bitmap_overlay.png"
R11_BITMAP_OVERLAY_SVG = REF_DIR / "etrto_R11_bitmap_overlay.svg"
R11_BITMAP_OVERLAY_PNG = REF_DIR / "etrto_R11_bitmap_overlay.png"
BITMAP_ALIGNMENT_JSON = REF_DIR / "etrto_bitmap_alignment_metrics.json"

# These fixed image transforms place true millimetre geometry from the Tyre
# Designer over the embedded ETRTO R.8/R.11 detail drawings. The drawings are
# schematic, so the hard pass/fail evidence remains the numeric R.8/R.11
# verification; these overlays are the visual "can lie over the detail image"
# check requested for the GUI.
R8_RIGHT_RIM_TO_SCAN = (
    5.171974522292992,
    -6.560693641618492,
    -830.982658959536,
    0.06369426751592351,
    6.5028901734104,
    2082.4277456647387,
)
R11_RIGHT_H_HUMP_TO_SCAN = (
    19.822525455872373,
    -38.510807877460834,
    -12429.526625403254,
    -0.13214753626777664,
    16.534519130398824,
    4921.733356000534,
)


def relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def extract_script(html_text: str) -> str:
    match = re.search(r"<script>\s*([\s\S]*?)\s*</script>", html_text)
    if not match:
        raise RuntimeError(f"missing script block in {relative(HTML_PATH)}")
    return match.group(1)


def run_node_payload(script: str) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node executable not found")

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
{script}

function finiteRows(rows) {{
  return (rows || [])
    .filter(row => Number.isFinite(Number(row.xMm)) && Number.isFinite(Number(row.yMm)))
    .map(row => ({{ xMm: Number(row.xMm), yMm: Number(row.yMm) }}));
}}

function serializeRim(rim) {{
  return {{
    contour: rim.contour,
    dimensions: rim.dimensions,
    verification: rim.verification,
    outerRows: finiteRows(rim.outerRows),
    humps: (rim.humps || []).map(finiteRows),
    beadSeats: (rim.beadSeats || []).map(finiteRows),
    beadContacts: (rim.beadContacts || []).map(finiteRows),
    flangeLips: (rim.flangeLips || []).map(finiteRows),
    dropCenter: finiteRows(rim.dropCenter),
  }};
}}

function rimCase(params) {{
  const model = generateTyreContour(params);
  const rim = generateEtrtoRimProfile(model);
  return {{
    rimWidthIn: Number(params.rimWidthIn),
    rimDiameterIn: Number(params.rimDiameterIn),
    overrideKeys: Object.keys(params).filter(key => !["rimWidthIn", "rimDiameterIn"].includes(key)),
    passed: !!rim.verification?.passed,
    errors: rim.verification?.errors || [],
    verification: rim.verification,
    finite: rim.outerRows.every(row => Number.isFinite(row.xMm) && Number.isFinite(row.yMm)),
    humpCount: rim.humps.length,
  }};
}}

const rimWidths = [10.5, 11.5, 12.5];
const rimDiameters = [17, 21, 24];
const standardCases = [];
for (const rimWidthIn of rimWidths) {{
  for (const rimDiameterIn of rimDiameters) {{
    standardCases.push(rimCase({{ rimWidthIn, rimDiameterIn }}));
  }}
}}

const overrideSets = [
  {{ rimHumpDistanceEMm: 35, rimHumpRadiusR3Mm: 9, rimHumpRadiusR8Mm: 11.5 }},
  {{
    rimFlangeWidthMm: 15,
    rimFlangeHeightMm: 17.9,
    rimBeadSeatLengthMm: 30,
    rimWellDepthMm: 35,
    rimLedgeLengthMm: 40,
    rimDropCenterSpanMm: 18,
    rimFlangeRadiusR1Mm: 24,
    rimBeadSeatRadiusR2Mm: 1.5,
    rimWellAngleDeg: 35,
  }},
  {{
    rimHumpDistanceEMm: 35,
    rimHumpRadiusR3Mm: 9,
    rimHumpRadiusR8Mm: 11.5,
    rimFlangeWidthMm: 15,
    rimWellDepthMm: 35,
    rimLedgeLengthMm: 40,
    rimDropCenterSpanMm: 18,
  }},
];
const overrideCases = [];
for (const rimWidthIn of rimWidths) {{
  for (const rimDiameterIn of rimDiameters) {{
    for (const overrides of overrideSets) {{
      overrideCases.push(rimCase({{ rimWidthIn, rimDiameterIn, ...overrides }}));
    }}
  }}
}}

const displayModel = generateTyreContour({{ rimWidthIn: 11.5, rimDiameterIn: 21 }});
const displayRim = generateEtrtoRimProfile(displayModel);
const displayBasicR8Rim = generateEtrtoRimProfile(displayModel, {{ includeHump: false }});
const referenceDims = etrtoPassengerJHRimDimensions(displayModel.metrics.rimWidthIn, displayModel.metrics.rimDiameterIn);
const referenceRim = generateEtrtoRimProfile({{
  metrics: {{
    ...referenceDims,
    rimRadiusMm: displayModel.metrics.rimRadiusMm,
    rimHalfWidthMm: displayModel.metrics.rimHalfWidthMm,
    rimWidthIn: displayModel.metrics.rimWidthIn,
    rimDiameterIn: displayModel.metrics.rimDiameterIn,
    beadFollowPct: displayModel.metrics.beadFollowPct,
  }},
}});

console.log(JSON.stringify({{
  standardCases,
  overrideCases,
  display: {{
    metrics: {{
      rimWidthIn: displayModel.metrics.rimWidthIn,
      rimDiameterIn: displayModel.metrics.rimDiameterIn,
      rimRadiusMm: displayModel.metrics.rimRadiusMm,
      rimHalfWidthMm: displayModel.metrics.rimHalfWidthMm,
    }},
    rim: serializeRim(displayRim),
    basicR8Rim: serializeRim(displayBasicR8Rim),
    referenceRim: serializeRim(referenceRim),
  }},
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
        raise RuntimeError(f"node returned {result.returncode}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def numeric_max_errors(cases: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for case in cases:
        for key, value in (case.get("verification") or {}).items():
            if isinstance(value, (int, float)):
                result[key] = max(result.get(key, 0.0), abs(float(value)))
    return result


def write_sweep(payload: dict[str, Any], source_hash: str) -> None:
    standard_cases = payload["standardCases"]
    override_cases = payload["overrideCases"]
    sweep = {
        "generatedBy": relative(BUILDER_PATH),
        "sourceHtml": relative(HTML_PATH),
        "sourceHtmlSha256": source_hash,
        "standard": {
            "caseCount": len(standard_cases),
            "failures": [
                case for case in standard_cases
                if not case.get("passed") or not case.get("finite") or case.get("humpCount") != 2
            ],
            "maxErrors": numeric_max_errors(standard_cases),
        },
        "overrides": {
            "caseCount": len(override_cases),
            "failures": [
                case for case in override_cases
                if not case.get("passed") or case.get("errors")
            ],
            "maxErrors": numeric_max_errors(override_cases),
        },
    }
    REF_DIR.mkdir(parents=True, exist_ok=True)
    SWEEP_JSON.write_text(json.dumps(sweep, indent=2) + "\n", encoding="utf-8")


def svg_point(row: dict[str, float]) -> tuple[float, float]:
    return float(row["yMm"]), -float(row["xMm"])


def transformed_svg_point(row: dict[str, float], transform: tuple[float, float, float, float, float, float]) -> tuple[float, float]:
    x, y = svg_point(row)
    a, b, c, d, e, f = transform
    return a * x + b * y + c, d * x + e * y + f


def polyline_points(rows: list[dict[str, float]]) -> str:
    return " ".join(f"{x:.4f},{y:.4f}" for x, y in (svg_point(row) for row in rows))


def transformed_polyline_points(rows: list[dict[str, float]], transform: tuple[float, float, float, float, float, float]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in (transformed_svg_point(row, transform) for row in rows))


def bitmap_black_pixels(diagram_png: Path, roi: tuple[int, int, int, int], threshold: int = 70) -> tuple[set[tuple[int, int]], int, int]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to inspect bitmap overlay residuals") from exc

    pix = fitz.Pixmap(str(diagram_png))
    width, height, channels = pix.width, pix.height, pix.n
    samples = pix.samples
    x0, y0, x1, y1 = roi
    pixels: set[tuple[int, int]] = set()
    for y in range(max(0, y0), min(height - 1, y1) + 1):
        base = y * width * channels
        for x in range(max(0, x0), min(width - 1, x1) + 1):
            offset = base + x * channels
            if channels == 1:
                is_black = samples[offset] < threshold
            else:
                r, g, b = samples[offset], samples[offset + 1], samples[offset + 2]
                is_black = r < threshold and g < threshold and b < threshold
            if is_black:
                pixels.add((x, y))
    return pixels, width, height


def nearest_black_distance_stats(
    rows: list[dict[str, float]],
    transform: tuple[float, float, float, float, float, float],
    diagram_png: Path,
    roi: tuple[int, int, int, int],
    *,
    search_radius_px: int = 120,
) -> dict[str, Any]:
    black, width, height = bitmap_black_pixels(diagram_png, roi)
    distances: list[float] = []
    misses = 0
    for row in rows:
        x, y = transformed_svg_point(row, transform)
        xi, yi = round(x), round(y)
        best: float | None = None
        for yy in range(max(0, yi - search_radius_px), min(height - 1, yi + search_radius_px) + 1):
            for xx in range(max(0, xi - search_radius_px), min(width - 1, xi + search_radius_px) + 1):
                if (xx, yy) not in black:
                    continue
                distance = math.hypot(xx - x, yy - y)
                if best is None or distance < best:
                    best = distance
        if best is None:
            misses += 1
        else:
            distances.append(best)
    sorted_distances = sorted(distances)
    p90_index = int(0.9 * (len(sorted_distances) - 1)) if sorted_distances else 0
    return {
        "pointCount": len(rows),
        "hitCount": len(distances),
        "missCount": misses,
        "meanPx": sum(distances) / len(distances) if distances else None,
        "p90Px": sorted_distances[p90_index] if sorted_distances else None,
        "maxPx": max(distances) if distances else None,
        "roi": list(roi),
        "searchRadiusPx": search_radius_px,
    }


def path_elements(rim: dict[str, Any], *, reference: bool = False) -> list[str]:
    if reference:
        elements = [
            f'<polyline points="{polyline_points(rim["outerRows"])}" fill="none" stroke="#72b7ff" '
            'stroke-width="1.0" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="2 2" />'
        ]
        for rows in rim["humps"]:
            elements.append(
                f'<polyline points="{polyline_points(rows)}" fill="none" stroke="#72b7ff" '
                'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="2 2" />'
            )
        return elements

    elements = [
        f'<polyline points="{polyline_points(rim["outerRows"])}" fill="none" stroke="#b8c2cc" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />'
    ]
    for rows in rim["humps"]:
        elements.append(
            f'<polyline points="{polyline_points(rows)}" fill="none" stroke="#f0b85a" '
            'stroke-width="2.6" stroke-linecap="round" />'
        )
    for rows in rim["beadSeats"]:
        elements.append(
            f'<polyline points="{polyline_points(rows)}" fill="none" stroke="#dce6ef" '
            'stroke-width="1.7" stroke-linecap="round" />'
        )
    for rows in rim["beadContacts"]:
        elements.append(
            f'<polyline points="{polyline_points(rows)}" fill="none" stroke="#72b7ff" '
            'stroke-width="2.2" stroke-linecap="round" stroke-dasharray="4 3" />'
        )
    for rows in rim["flangeLips"]:
        elements.append(
            f'<polyline points="{polyline_points(rows)}" fill="none" stroke="#9aa7b3" '
            'stroke-width="1.4" stroke-linecap="round" />'
        )
    elements.append(
        f'<polyline points="{polyline_points(rim["dropCenter"])}" fill="none" stroke="#60717f" '
        'stroke-width="1.2" stroke-linecap="round" />'
    )
    return elements


def bounds_for_rows(row_groups: list[list[dict[str, float]]]) -> tuple[float, float, float, float]:
    points = [svg_point(row) for rows in row_groups for row in rows]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def table_rows(verification: dict[str, Any]) -> str:
    rows = []
    for key, value in verification.items():
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, (int, float)):
            text = f"{float(value):.6e}"
        else:
            text = json.dumps(value)
        rows.append(f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(text)}</td></tr>")
    return "\n".join(rows)


def build_display_html(payload: dict[str, Any], source_hash: str) -> str:
    display = payload["display"]
    rim = display["rim"]
    reference = display["referenceRim"]
    row_groups = [
        rim["outerRows"],
        reference["outerRows"],
        *rim["humps"],
        *reference["humps"],
    ]
    min_x, min_y, max_x, max_y = bounds_for_rows(row_groups)
    pad_x = 18
    pad_y = 18
    view_box = f"{min_x - pad_x:.1f} {min_y - pad_y:.1f} {(max_x - min_x) + 2 * pad_x:.1f} {(max_y - min_y) + 2 * pad_y:.1f}"
    metrics = display["metrics"]
    rim_radius_y = -float(metrics["rimRadiusMm"])
    rim_half = float(metrics["rimHalfWidthMm"])

    svg_body = "\n  ".join([
        f'<line x1="{min_x - pad_x:.1f}" y1="{rim_radius_y:.4f}" x2="{max_x + pad_x:.1f}" y2="{rim_radius_y:.4f}" stroke="#5f7386" stroke-width="0.35" stroke-dasharray="2 2" />',
        f'<line x1="{-rim_half:.4f}" y1="{min_y - pad_y:.1f}" x2="{-rim_half:.4f}" y2="{max_y + pad_y:.1f}" stroke="#5f7386" stroke-width="0.35" stroke-dasharray="2 2" />',
        f'<line x1="{rim_half:.4f}" y1="{min_y - pad_y:.1f}" x2="{rim_half:.4f}" y2="{max_y + pad_y:.1f}" stroke="#5f7386" stroke-width="0.35" stroke-dasharray="2 2" />',
        *path_elements(rim),
        *path_elements(reference, reference=True),
    ])
    table = table_rows(rim["verification"])
    return f"""<!doctype html>
<html lang="en" data-source-html-sha256="{source_hash}">
<head>
<meta charset="utf-8">
<title>Tyre Designer Display Rim Overlay</title>
<style>
  :root {{ color-scheme: dark; --bg:#0b0f12; --panel:#101820; --line:#293846; --text:#e7eef5; --muted:#9fb5c8; }}
  body {{ margin:0; padding:24px; background:var(--bg); color:var(--text); font:14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
  .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; max-width:1180px; }}
  svg {{ display:block; width:100%; height:auto; background:#06090c; border:1px solid #1d2a35; border-radius:6px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:12px; font-size:12px; }}
  th,td {{ border-bottom:1px solid var(--line); padding:5px 6px; text-align:left; }}
  th {{ color:#c7d7e5; width:40%; }}
  p {{ color:var(--muted); max-width:980px; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:14px; margin-top:10px; color:var(--muted); font-size:12px; }}
  .swatch {{ display:inline-block; width:22px; height:3px; border-radius:2px; margin-right:6px; vertical-align:middle; }}
</style>
</head>
<body>
<section class="panel">
<h1>Tyre Designer Display Rim Overlay</h1>
<p>This renders the same ETRTO J/H rim layers used by the Tyre Designer plot and overlays an independently reconstructed dimension reference from R.8/R.11 in dashed blue. Coordinates are true millimetres: horizontal is lateral Y, vertical is radial -X.</p>
<p>Generated by <code>{html.escape(relative(BUILDER_PATH))}</code> from <code>{html.escape(relative(HTML_PATH))}</code>, source SHA-256 <code>{source_hash}</code>.</p>
<svg viewBox="{view_box}" role="img" aria-label="Tyre Designer displayed rim overlay">
  {svg_body}
</svg>
<div class="legend">
  <span><span class="swatch" style="background:#b8c2cc"></span>Designer outer rim</span>
  <span><span class="swatch" style="background:#f0b85a"></span>Designer H hump</span>
  <span><span class="swatch" style="background:#72b7ff"></span>ETRTO R.8/R.11 reference</span>
  <span><span class="swatch" style="background:#72b7ff"></span>Bead contact</span>
</div>
<table>
{table}
</table>
</section>
</body>
</html>
"""


def write_png_from_html(display_html: str) -> None:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to render the overlay PNG") from exc

    match = re.search(r"(<svg[\s\S]*?</svg>)", display_html)
    if not match:
        raise RuntimeError("generated display HTML does not contain an SVG")
    doc = fitz.open("svg", match.group(1).encode("utf-8"))
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pix.save(DISPLAY_PNG)


def render_svg_to_png(svg_text: str, path: Path) -> None:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to render the bitmap overlay PNGs") from exc

    doc = fitz.open("svg", svg_text.encode("utf-8"))
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pix.save(path)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError(f"not a PNG: {relative(path)}")
    return struct.unpack(">II", data[16:24])


def png_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def write_embedded_etrto_diagram(page_index: int, output: Path) -> None:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to extract the embedded ETRTO diagrams") from exc

    if not ETRTO_PDF.is_file():
        raise RuntimeError(f"missing ETRTO PDF: {relative(ETRTO_PDF)}")
    doc = fitz.open(str(ETRTO_PDF))
    images = doc[page_index].get_images(full=True)
    if not images:
        raise RuntimeError(f"missing embedded diagram image on ETRTO page index {page_index}")
    image = doc.extract_image(images[0][0])
    pix = fitz.Pixmap(image["image"])
    samples = bytearray(pix.samples)
    if pix.alpha:
        for offset in range(0, len(samples), pix.n):
            for channel in range(pix.n - 1):
                samples[offset + channel] = 255 - samples[offset + channel]
    else:
        for index, value in enumerate(samples):
            samples[index] = 255 - value
    output.parent.mkdir(parents=True, exist_ok=True)
    fitz.Pixmap(pix.colorspace, pix.width, pix.height, bytes(samples), pix.alpha).save(output)


def write_embedded_etrto_diagrams() -> None:
    # PDF page indexes are zero-based: R.8 is page 281, R.11 is page 284.
    write_embedded_etrto_diagram(281, R8_DIAGRAM_PNG)
    write_embedded_etrto_diagram(284, R11_DIAGRAM_PNG)


def write_display_artifacts(payload: dict[str, Any], source_hash: str) -> None:
    html_text = build_display_html(payload, source_hash)
    DISPLAY_HTML.write_text(html_text, encoding="utf-8")
    write_png_from_html(html_text)


def write_points(payload: dict[str, Any], source_hash: str) -> None:
    points = {
        "generatedBy": relative(BUILDER_PATH),
        "sourceHtml": relative(HTML_PATH),
        "sourceHtmlSha256": source_hash,
        "display": payload["display"],
    }
    REF_DIR.mkdir(parents=True, exist_ok=True)
    POINTS_JSON.write_text(json.dumps(points, indent=2) + "\n", encoding="utf-8")


def right_side_rows(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    return [row for row in rows if float(row.get("yMm", 0.0)) >= -1e-9]


def positive_hump_rows(rim: dict[str, Any]) -> list[dict[str, float]]:
    humps = rim.get("humps") or []
    if not humps:
        return []
    return max(
        humps,
        key=lambda rows: sum(float(row.get("yMm", 0.0)) for row in rows) / max(len(rows), 1),
    )


def positive_feature_rows(rim: dict[str, Any], key: str) -> list[dict[str, float]]:
    groups = rim.get(key) or []
    if not groups:
        return []
    return max(
        groups,
        key=lambda rows: sum(float(row.get("yMm", 0.0)) for row in rows) / max(len(rows), 1),
    )


def join_polyline_rows(*parts: list[dict[str, float]]) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    for rows in parts:
        for row in rows:
            if not result:
                result.append(row)
                continue
            prev = result[-1]
            if abs(float(prev["xMm"]) - float(row["xMm"])) > 1e-9 or abs(float(prev["yMm"]) - float(row["yMm"])) > 1e-9:
                result.append(row)
    return result


def positive_hump_detail_rows(rim: dict[str, Any]) -> list[dict[str, float]]:
    return join_polyline_rows(positive_hump_rows(rim), positive_feature_rows(rim, "beadSeats"))


def bitmap_overlay_svg(
    *,
    title: str,
    source_hash: str,
    diagram_png: Path,
    geometry_elements: list[str],
    notes: str,
) -> str:
    width, height = png_size(diagram_png)
    body = "\n  ".join(geometry_elements)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" data-source-html-sha256="{source_hash}">
  <metadata>{html.escape(json.dumps({
        "title": title,
        "generatedBy": relative(BUILDER_PATH),
        "sourceHtml": relative(HTML_PATH),
        "sourceHtmlSha256": source_hash,
        "diagram": relative(diagram_png),
        "notes": notes,
    }, sort_keys=True))}</metadata>
  <title>{html.escape(title)}</title>
  <desc>{html.escape(notes)}</desc>
  <image href="{png_data_uri(diagram_png)}" x="0" y="0" width="{width}" height="{height}" opacity="0.82"/>
  {body}
</svg>
"""


def write_bitmap_scan_overlays(payload: dict[str, Any], source_hash: str) -> dict[str, Any]:
    display = payload["display"]
    rim = display["rim"]
    basic_r8_rim = display["basicR8Rim"]
    reference = display["referenceRim"]

    r8_rows = basic_r8_rim["outerRows"]
    r8_reference_rows = basic_r8_rim["outerRows"]
    r8_stats = nearest_black_distance_stats(
        r8_rows,
        R8_RIGHT_RIM_TO_SCAN,
        R8_DIAGRAM_PNG,
        (0, 0, 2265, 780),
    )
    r8_svg = bitmap_overlay_svg(
        title="ETRTO R.8 Bitmap Overlay - Tyre Designer Rim",
        source_hash=source_hash,
        diagram_png=R8_DIAGRAM_PNG,
        notes="Current Tyre Designer full R.8 basic rim contour over the embedded ETRTO R.8 detail image. H-hump geometry is checked separately against R.11, because R.8 shows the non-hump basic contour.",
        geometry_elements=[
            f'<polyline points="{transformed_polyline_points(r8_reference_rows, R8_RIGHT_RIM_TO_SCAN)}" fill="none" stroke="#8ce3df" stroke-width="8.5" stroke-dasharray="20 12" stroke-linecap="round" stroke-linejoin="round"><title>ETRTO R.8 nominal reference contour</title></polyline>',
            f'<polyline points="{transformed_polyline_points(r8_rows, R8_RIGHT_RIM_TO_SCAN)}" fill="none" stroke="#ff5d5d" stroke-width="10.5" stroke-linecap="round" stroke-linejoin="round"><title>Current Tyre Designer full R.8 basic rim contour without H hump</title></polyline>',
        ],
    )
    R8_BITMAP_OVERLAY_SVG.write_text(r8_svg, encoding="utf-8")
    render_svg_to_png(r8_svg, R8_BITMAP_OVERLAY_PNG)

    r11_hump = positive_hump_detail_rows(rim)
    r11_reference_hump = positive_hump_detail_rows(reference)
    r11_stats = nearest_black_distance_stats(
        r11_hump,
        R11_RIGHT_H_HUMP_TO_SCAN,
        R11_DIAGRAM_PNG,
        (120, 330, 850, 580),
    )
    r11_svg = bitmap_overlay_svg(
        title="ETRTO R.11 Bitmap Overlay - Tyre Designer H Hump",
        source_hash=source_hash,
        diagram_png=R11_DIAGRAM_PNG,
        notes="Current Tyre Designer H-hump radius geometry and adjacent bead-seat line over the embedded ETRTO R.11 detail image. The red curve is the displayed H hump; dashed blue is the nominal ETRTO reference.",
        geometry_elements=[
            f'<polyline points="{transformed_polyline_points(r11_reference_hump, R11_RIGHT_H_HUMP_TO_SCAN)}" fill="none" stroke="#72b7ff" stroke-width="13.0" stroke-dasharray="28 16" stroke-linecap="round" stroke-linejoin="round"><title>ETRTO R.11 nominal H-hump reference</title></polyline>',
            f'<polyline points="{transformed_polyline_points(r11_hump, R11_RIGHT_H_HUMP_TO_SCAN)}" fill="none" stroke="#ff5d5d" stroke-width="16.0" stroke-linecap="round" stroke-linejoin="round"><title>Current Tyre Designer H hump radius and bead-seat continuation</title></polyline>',
        ],
    )
    R11_BITMAP_OVERLAY_SVG.write_text(r11_svg, encoding="utf-8")
    render_svg_to_png(r11_svg, R11_BITMAP_OVERLAY_PNG)
    metrics = {
        "generatedBy": relative(BUILDER_PATH),
        "sourceHtml": relative(HTML_PATH),
        "sourceHtmlSha256": source_hash,
        "notes": "Pixel residuals measure the current affine visual placement against black pixels in the scanned ETRTO detail crops. The scans are schematic, so these are diagnostics, not dimension gates.",
        "r8": {
            "diagram": relative(R8_DIAGRAM_PNG),
            "overlay": relative(R8_BITMAP_OVERLAY_PNG),
            "geometry": "R.8 basic rim contour without H hump",
            "transform": list(R8_RIGHT_RIM_TO_SCAN),
            "distancePx": r8_stats,
        },
        "r11": {
            "diagram": relative(R11_DIAGRAM_PNG),
            "overlay": relative(R11_BITMAP_OVERLAY_PNG),
            "geometry": "R.11 H hump radius and bead-seat continuation",
            "transform": list(R11_RIGHT_H_HUMP_TO_SCAN),
            "distancePx": r11_stats,
        },
    }
    BITMAP_ALIGNMENT_JSON.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def write_overlay_index(source_hash: str, bitmap_metrics: dict[str, Any] | None = None) -> None:
    OVERLAY_INDEX = REPO_ROOT / "tyres" / "analysis" / "etrto_rim_overlay_check.html"
    r8_stats = ((bitmap_metrics or {}).get("r8") or {}).get("distancePx") or {}
    r11_stats = ((bitmap_metrics or {}).get("r11") or {}).get("distancePx") or {}
    r8_residual = f"mean {float(r8_stats.get('meanPx') or 0):.2f} px, p90 {float(r8_stats.get('p90Px') or 0):.2f} px, misses {r8_stats.get('missCount', '?')}"
    r11_residual = f"mean {float(r11_stats.get('meanPx') or 0):.2f} px, p90 {float(r11_stats.get('p90Px') or 0):.2f} px, misses {r11_stats.get('missCount', '?')}"
    OVERLAY_INDEX.write_text(f"""<!doctype html>
<html lang="en" data-source-html-sha256="{source_hash}">
<head>
<meta charset="utf-8">
<title>ETRTO Rim Overlay Check</title>
<style>
  body {{ margin:0; padding:24px; background:#0b0f12; color:#e7eef5; font:14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
  section {{ max-width:1240px; margin:0 auto 18px; padding:14px; border:1px solid #293846; border-radius:8px; background:#101820; }}
  img {{ display:block; width:100%; height:auto; border:1px solid #1d2a35; border-radius:6px; background:#05080a; }}
  p {{ color:#9fb5c8; }}
</style>
</head>
<body>
<section>
  <h1>ETRTO Rim Overlay Check</h1>
  <p>Generated by <code>{html.escape(relative(BUILDER_PATH))}</code> from current Tyre Designer HTML SHA-256 <code>{source_hash}</code>.</p>
  <p>R.8 checks the basic J/H rim contour. R.11 checks the H-hump radius detail. The scan drawings are schematic; the hard dimensional gate is the numeric verifier.</p>
</section>
<section>
  <h2>R.8 Basic Rim Detail</h2>
  <p>Bitmap residual: {html.escape(r8_residual)}.</p>
  <img src="_etrto_rim_reference/etrto_R8_bitmap_overlay.png" alt="ETRTO R.8 bitmap overlay">
</section>
<section>
  <h2>R.11 H-Hump Detail</h2>
  <p>Bitmap residual: {html.escape(r11_residual)}.</p>
  <img src="_etrto_rim_reference/etrto_R11_bitmap_overlay.png" alt="ETRTO R.11 H-hump bitmap overlay">
</section>
</body>
</html>
""", encoding="utf-8")


def run() -> dict[str, Any]:
    html_text = HTML_PATH.read_text(encoding="utf-8")
    source_hash = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
    payload = run_node_payload(extract_script(html_text))
    write_sweep(payload, source_hash)
    write_points(payload, source_hash)
    write_display_artifacts(payload, source_hash)
    bitmap_metrics = write_bitmap_scan_overlays(payload, source_hash)
    write_overlay_index(source_hash, bitmap_metrics)
    return {
        "passed": True,
        "sourceHtml": relative(HTML_PATH),
        "sourceHtmlSha256": source_hash,
        "displayOverlay": relative(DISPLAY_HTML),
        "displayOverlayPng": relative(DISPLAY_PNG),
        "r8BitmapOverlay": relative(R8_BITMAP_OVERLAY_SVG),
        "r8BitmapOverlayPng": relative(R8_BITMAP_OVERLAY_PNG),
        "r11BitmapOverlay": relative(R11_BITMAP_OVERLAY_SVG),
        "r11BitmapOverlayPng": relative(R11_BITMAP_OVERLAY_PNG),
        "bitmapAlignment": relative(BITMAP_ALIGNMENT_JSON),
        "sweep": relative(SWEEP_JSON),
        "points": relative(POINTS_JSON),
    }


def main() -> int:
    print(json.dumps(run(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
