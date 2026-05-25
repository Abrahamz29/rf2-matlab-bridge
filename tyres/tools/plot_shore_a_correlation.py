#!/usr/bin/env python3
"""Plot Shore A against Young modulus from the tyre material database."""

from __future__ import annotations

import argparse
import html
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "tyres" / "database" / "rf2_material_database.sqlite"
DEFAULT_OUTPUT = REPO_ROOT / "tyres" / "analysis" / "young_modulus_vs_shore_a.svg"
DEFAULT_HTML_OUTPUT = REPO_ROOT / "tyres" / "analysis" / "young_modulus_vs_shore_a.html"


CATEGORY_COLORS = {
    "Bulk Compounds": "#78d3ff",
    "Filler / Bead / Apex Compounds": "#b090ff",
    "Inner Liner": "#7ee27c",
    "Rubber Tread Compounds": "#f0b85a",
    "Tread Sidewall Compounds": "#ff8f5c",
}


@dataclass(frozen=True)
class MaterialPoint:
    category: str
    material: str
    temp_c: float
    shore_a: float
    e_mpa: float


@dataclass(frozen=True)
class FormulaCurve:
    key: str
    label: str
    color: str
    e_mpa: Callable[[float], float]
    dash: str = ""
    default_on: bool = True
    x_min: float = 30.0
    x_max: float = 99.97


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="material SQLite database")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="SVG file to write")
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT, help="interactive HTML file to write")
    args = parser.parse_args()

    points = load_points(args.db)
    if not points:
        raise SystemExit("no valid Shore A / Young modulus points found")

    svg = render_svg(points)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8", newline="\n")
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(svg), encoding="utf-8", newline="\n")
    print(f"wrote {args.output}")
    print(f"wrote {args.html_output}")
    print(f"points: {len(points)}")
    return 0


def load_points(db_path: Path) -> list[MaterialPoint]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            select category, material, temperature_k, shore_a, youngs_modulus_pa
            from material_points
            order by category, material, temperature_k, sample_index
            """
        ).fetchall()
    finally:
        conn.close()

    points: list[MaterialPoint] = []
    for category, material, temp_k, shore_a, e_pa in rows:
        shore = safe_float(shore_a)
        e = safe_float(e_pa)
        temp = safe_float(temp_k)
        if shore is None or e is None or temp is None:
            continue
        if not (shore > 0 and e > 0):
            continue
        points.append(
            MaterialPoint(
                category=str(category or ""),
                material=str(material or ""),
                temp_c=temp - 273.15,
                shore_a=shore,
                e_mpa=e / 1_000_000.0,
            )
        )
    return points


def safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def render_svg(points: list[MaterialPoint]) -> str:
    width = 1400
    height = 900
    left = 105
    top = 95
    plot_width = 1010
    plot_height = 705
    right = left + plot_width
    bottom = top + plot_height
    x_min = 30.0
    x_max = 105.0
    y_min_log = math.log10(0.315)
    y_max_log = math.log10(10000.0)

    shores = [p.shore_a for p in points]
    logs = [math.log10(p.e_mpa) for p in points]
    pearson = correlation(shores, logs)
    spearman = correlation(ranks(shores), ranks(logs))
    intercept, slope = linear_regression(shores, logs)

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def sy_from_log(value: float) -> float:
        return bottom - (value - y_min_log) / (y_max_log - y_min_log) * plot_height

    def sy_mpa(value: float) -> float:
        return sy_from_log(math.log10(value))

    lines: list[str] = [
        f'<svg id="shore-a-plot" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0f1317"/>',
        f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" fill="#0b0f12" stroke="#303944" stroke-width="1.2"/>',
        "<style>"
        "text{font-family:Segoe UI,Arial,sans-serif}"
        ".title{font-size:28px;font-weight:700;fill:#e6edf3}"
        ".sub{font-size:15px;fill:#b9d8f2}"
        ".axis{font-size:15px;fill:#b9d8f2}"
        ".tick{font-size:13px;fill:#9aa7b3}"
        ".legend{font-size:14px;fill:#dceaf7}"
        ".note{font-size:13px;fill:#9aa7b3}"
        ".formula-toggle{cursor:pointer}"
        ".formula-toggle text{user-select:none}"
        ".formula-toggle.is-highlight text{fill:#fff}"
        ".formula-toggle.is-highlight .formula-swatch{stroke-width:4}"
        ".formula-toggle.is-off text{opacity:.45}"
        ".formula-toggle.is-off .formula-check{display:none}"
        ".formula-toggle.is-off .formula-swatch{opacity:.25}"
        ".formula-layer.hidden{display:none}"
        ".formula-layer{cursor:pointer}"
        ".formula-hit{pointer-events:stroke;opacity:0}"
        ".formula-visible{transition:stroke-width .12s ease,stroke-opacity .12s ease,opacity .12s ease}"
        "#shore-a-plot.has-highlight .formula-layer:not(.is-highlight) .formula-visible{opacity:.18}"
        ".formula-layer.is-highlight .formula-visible{stroke-width:5.2;stroke-opacity:1}"
        "</style>",
        "<script><![CDATA["
        "function formulaParts(key){"
        "return {plot:document.getElementById('shore-a-plot'),layer:document.getElementById('formula-'+key),"
        "row:document.querySelector('[data-formula=\"'+key+'\"]'),status:document.getElementById('formula-status')};"
        "}"
        "function setFormulaVisibility(key,visible){"
        "var p=formulaParts(key);"
        "if(!p.layer||!p.row){return;}"
        "p.layer.classList.toggle('hidden',!visible);"
        "p.row.classList.toggle('is-off',!visible);"
        "if(!visible){clearFormulaHighlight(key);}"
        "}"
        "function toggleFormula(key){"
        "var p=formulaParts(key);"
        "if(!p.layer){return;}"
        "setFormulaVisibility(key,p.layer.classList.contains('hidden'));"
        "}"
        "function highlightFormula(key){"
        "var p=formulaParts(key);"
        "if(!p.plot||!p.layer||p.layer.classList.contains('hidden')){return;}"
        "p.plot.classList.add('has-highlight');"
        "p.layer.classList.add('is-highlight');"
        "if(p.row){p.row.classList.add('is-highlight');}"
        "if(p.status){p.status.textContent='Highlighted: '+(p.layer.getAttribute('data-label')||key);}"
        "p.layer.parentNode.appendChild(p.layer);"
        "}"
        "function clearFormulaHighlight(key){"
        "var p=formulaParts(key);"
        "if(p.layer){p.layer.classList.remove('is-highlight');}"
        "if(p.row){p.row.classList.remove('is-highlight');}"
        "if(p.plot&&!p.plot.querySelector('.formula-layer.is-highlight')){p.plot.classList.remove('has-highlight');}"
        "if(p.status&&p.plot&&!p.plot.querySelector('.formula-layer.is-highlight')){p.status.textContent='Hover a curve to highlight it. Click a curve to hide it.';}"
        "}"
        "document.addEventListener('DOMContentLoaded',function(){"
        "document.querySelectorAll('.formula-toggle').forEach(function(row){"
        "var key=row.getAttribute('data-formula');"
        "row.addEventListener('mouseenter',function(){highlightFormula(key);});"
        "row.addEventListener('mouseleave',function(){clearFormulaHighlight(key);});"
        "row.addEventListener('click',function(){toggleFormula(key);});"
        "});"
        "document.querySelectorAll('.formula-layer').forEach(function(layer){"
        "var key=layer.getAttribute('data-formula');"
        "layer.addEventListener('mouseenter',function(){highlightFormula(key);});"
        "layer.addEventListener('mouseleave',function(){clearFormulaHighlight(key);});"
        "layer.addEventListener('click',function(){setFormulaVisibility(key,false);});"
        "});"
        "});"
        "]]></script>",
        '<text class="title" x="105" y="42">Young modulus vs. Shore A</text>',
        (
            '<text class="sub" x="105" y="68">'
            f"TGM Gen material database | n={len(points)} material-temperature points | "
            f"Pearson r(Shore A, log10(E)) = {pearson:.3f} | Spearman rho = {spearman:.3f}"
            "</text>"
        ),
    ]

    for tick in range(30, 101, 10):
        x = sx(float(tick))
        lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#1e2830" stroke-width="1"/>')
        lines.append(f'<text class="tick" x="{x:.1f}" y="824" text-anchor="middle">{tick}</text>')

    y_ticks = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
    for tick in y_ticks:
        y = sy_mpa(float(tick))
        major = tick in {1, 10, 100, 1000, 10000}
        label = compact_number(tick)
        lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" '
            f'stroke="#27323c" stroke-width="{1.1 if major else 0.65}"/>'
        )
        lines.append(f'<text class="tick" x="92" y="{y + 4:.1f}" text-anchor="end">{label}</text>')

    lines.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#617286" stroke-width="1.5"/>',
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#617286" stroke-width="1.5"/>',
            '<text class="axis" x="610.0" y="866" text-anchor="middle">Shore A [-]</text>',
            '<text class="axis" x="28" y="447.5" text-anchor="middle" transform="rotate(-90 28 447.5)">Young modulus E [MPa], log scale</text>',
        ]
    )

    formulas = formula_curves(intercept, slope)
    for formula in formulas:
        curve = curve_points(formula, sx, sy_mpa, x_min, x_max)
        if not curve:
            continue
        dash = f' stroke-dasharray="{formula.dash}"' if formula.dash else ""
        hidden = "" if formula.default_on else " hidden"
        lines.append(
            f'<g id="formula-{formula.key}" class="formula-layer{hidden}" '
            f'data-formula="{formula.key}" data-label="{html.escape(formula.label, quote=True)}">'
            f'<path class="formula-visible" d="{path_from_points(curve)}" fill="none" stroke="{formula.color}" '
            f'stroke-width="2.35" stroke-opacity="0.88"{dash}>'
            f'<title>{html.escape(formula.label)}</title></path>'
            f'<path class="formula-hit" d="{path_from_points(curve)}" fill="none" stroke="#fff" '
            f'stroke-width="16" stroke-linecap="round"/>'
            "</g>"
        )

    lines.append(
        f'<text class="note" x="121" y="120">log10(E MPa) = {intercept:.3f} + {slope:.4f} * Shore A</text>'
    )
    lines.append(
        '<text id="formula-status" class="note" x="121" y="141">Hover a curve to highlight it. Click a curve to hide it.</text>'
    )

    for point in points:
        color = CATEGORY_COLORS.get(point.category, "#b9d8f2")
        title = html.escape(
            f"{point.material} | {point.category} | {point.temp_c:g} C | "
            f"Shore A {point.shore_a:g} | E {point.e_mpa:g} MPa",
            quote=True,
        )
        lines.append(
            f'<circle cx="{sx(point.shore_a):.1f}" cy="{sy_mpa(point.e_mpa):.1f}" r="4.3" '
            f'fill="{color}" fill-opacity="0.74" stroke="#0b0f12" stroke-width="0.8"><title>{title}</title></circle>'
        )

    draw_right_panel(lines, points, intercept, slope, formulas)
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_html(svg: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        "<title>Young modulus vs. Shore A</title>\n"
        "<style>\n"
        ":root{color-scheme:dark;background:#0f1317;color:#e6edf3;font-family:Segoe UI,Arial,sans-serif}\n"
        "body{margin:0;min-height:100vh;background:#0f1317}\n"
        "main{min-height:100vh;display:grid;place-items:center;padding:18px;box-sizing:border-box}\n"
        ".plot-frame{width:min(100%,1400px);border:1px solid #303944;background:#0f1317;box-shadow:0 18px 50px rgba(0,0,0,.35)}\n"
        ".plot-frame svg{display:block;width:100%;height:auto}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        '<main><div class="plot-frame">\n'
        f"{svg}"
        "</div></main>\n"
        "</body>\n"
        "</html>\n"
    )


def draw_right_panel(
    lines: list[str],
    points: list[MaterialPoint],
    intercept: float,
    slope: float,
    formulas: list[FormulaCurve],
) -> None:
    x = 1143
    lines.append(f'<text class="legend" x="{x}" y="114">Categories</text>')
    y = 136
    for category, color in CATEGORY_COLORS.items():
        count = sum(1 for point in points if point.category == category)
        if not count:
            continue
        lines.append(f'<circle cx="{x + 9}" cy="{y}" r="4.8" fill="{color}" fill-opacity="0.9"/>')
        lines.append(
            f'<text class="legend" x="{x + 24}" y="{y + 4}">{html.escape(category)} ({count})</text>'
        )
        y += 24

    y += 34
    lines.append(f'<text class="legend" x="{x}" y="{y}">Formula toggles</text>')
    y += 22
    for formula in formulas:
        row_class = "formula-toggle" if formula.default_on else "formula-toggle is-off"
        dash = f' stroke-dasharray="{formula.dash}"' if formula.dash else ""
        lines.append(f'<g class="{row_class}" data-formula="{formula.key}">')
        lines.append(
            f'<rect x="{x}" y="{y - 10}" width="13" height="13" rx="2" '
            f'fill="#0b0f12" stroke="{formula.color}" stroke-width="1.4"/>'
        )
        lines.append(
            f'<path class="formula-check" d="M {x + 3.1:.1f} {y - 3.8:.1f} '
            f'L {x + 5.8:.1f} {y - 1.0:.1f} L {x + 10.2:.1f} {y - 7.0:.1f}" '
            f'fill="none" stroke="{formula.color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        lines.append(
            f'<line class="formula-swatch" x1="{x + 21}" y1="{y - 3.5:.1f}" x2="{x + 54}" y2="{y - 3.5:.1f}" '
            f'stroke="{formula.color}" stroke-width="2.35"{dash}/>'
        )
        lines.append(f'<text class="legend" x="{x + 62}" y="{y + 1}">{html.escape(formula.label)}</text>')
        lines.append("</g>")
        y += 23
    lines.append(f'<text class="note" x="{x}" y="{y + 8}">Fit: log10(E MPa) = {intercept:.3f} + {slope:.4f} S</text>')

    y += 70
    shore_min = min(point.shore_a for point in points)
    shore_max = max(point.shore_a for point in points)
    e_min = min(point.e_mpa for point in points)
    e_max = max(point.e_mpa for point in points)
    temps = [point.temp_c for point in points]
    lines.append(f'<text class="legend" x="{x}" y="{y}">Ranges</text>')
    lines.append(f'<text class="note" x="{x}" y="{y + 27}">Shore A: {shore_min:.2f}..{shore_max:.0f}</text>')
    lines.append(f'<text class="note" x="{x}" y="{y + 49}">E: {e_min:g}..{e_max:g} MPa</text>')
    lines.append(f'<text class="note" x="{x}" y="{y + 71}">Temperatures: {min(temps):g}..{max(temps):g} C</text>')


def formula_curves(intercept: float, slope: float) -> list[FormulaCurve]:
    return [
        FormulaCurve(
            "database-fit",
            "Database log fit",
            "#e6edf3",
            lambda shore: 10 ** (intercept + slope * shore),
            dash="9 5",
            x_max=105.0,
        ),
        FormulaCurve("gent", "Gent 1958", "#55e6c1", gent_shore_a_to_e_mpa),
        FormulaCurve("error-function", "TGM Gen / BS 903 ERF", "#4dd0e1", error_function_shore_a_to_e_mpa),
        FormulaCurve("ruess", "Ruess", "#ff8f5c", ruess_shore_a_to_e_mpa),
        FormulaCurve("rigbi", "Rigbi", "#f7c948", rigbi_shore_a_to_e_mpa, dash="8 4"),
        FormulaCurve(
            "battermann-kohler",
            "Battermann-Kohler",
            "#9be564",
            battermann_kohler_shore_a_to_e_mpa,
            dash="5 4",
        ),
        FormulaCurve("mix-giacomin", "Mix-Giacomin", "#ff75c3", mix_giacomin_shore_a_to_e_mpa, x_max=99.5),
        FormulaCurve("dow-dma", "Dow DMA fit", "#7aa2f7", dow_dma_shore_a_to_e_mpa, dash="2 4"),
        FormulaCurve("dow-rda", "Dow RDA fit", "#bb9af7", dow_rda_shore_a_to_e_mpa, dash="2 4"),
        FormulaCurve("dow-secant", "Dow 1-25% secant", "#f7768e", dow_secant_shore_a_to_e_mpa, dash="2 4"),
        FormulaCurve("dow-lsr", "Dow LSR secant", "#89ddff", dow_lsr_secant_shore_a_to_e_mpa, dash="10 4 2 4"),
        FormulaCurve("dow-tpsiv-secant", "Dow TPSiV secant", "#c3e88d", dow_tpsiv_secant_shore_a_to_e_mpa, dash="10 4 2 4"),
        FormulaCurve("dow-tpsiv-dma", "Dow TPSiV DMA", "#f78c6c", dow_tpsiv_dma_shore_a_to_e_mpa, dash="10 4 2 4"),
    ]


def curve_points(
    formula: FormulaCurve,
    sx: Callable[[float], float],
    sy_mpa: Callable[[float], float],
    x_min: float,
    x_max: float,
) -> list[tuple[float, float]]:
    start = max(x_min, formula.x_min)
    end = min(x_max, formula.x_max)
    if end <= start:
        return []
    points: list[tuple[float, float]] = []
    for i in range(900):
        shore = start + (end - start) * i / 899
        try:
            e_mpa = formula.e_mpa(shore)
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        if not math.isfinite(e_mpa) or not (0.315 <= e_mpa <= 10000.0):
            continue
        points.append((sx(shore), sy_mpa(e_mpa)))
    return points


def compact_number(value: float) -> str:
    if value >= 1000:
        return f"{value / 1000:g}k"
    return f"{value:g}"


def path_from_points(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    parts = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    parts.extend(f"L {x:.1f} {y:.1f}" for x, y in points[1:])
    return " ".join(parts)


def gent_shore_a_to_e_mpa(shore_a: float) -> float:
    return 0.0981 * (56.0 + 7.62336 * shore_a) / (0.137505 * (254.0 - 2.54 * shore_a))


def error_function_shore_a_to_e_mpa(shore_a: float) -> float:
    inverse = inverse_erf(shore_a / 100.0)
    return (inverse / 3.186e-4) ** 2 / 1_000_000.0


def ruess_shore_a_to_e_mpa(shore_a: float) -> float:
    return 10 ** (0.0235 * shore_a - 0.6403)


def rigbi_shore_a_to_e_mpa(shore_a: float) -> float:
    return math.exp((shore_a - 35.22735) / 18.75487)


def battermann_kohler_shore_a_to_e_mpa(shore_a: float) -> float:
    shear_modulus_mpa = 0.086 * (1.045 ** shore_a)
    return 3.0 * shear_modulus_mpa


def mix_giacomin_shore_a_to_e_mpa(shore_a: float) -> float:
    normalized_shore = shore_a / 100.0
    spring_force_at_zero_n = 0.55
    spring_rate_n_per_shore = 0.075
    protrusion_cm = 0.25
    indenter_radius_cm = 0.0395
    indentation_per_shore_cm = protrusion_cm / 100.0
    mechanical_indentability = (
        spring_rate_n_per_shore * protrusion_cm / (indentation_per_shore_cm * spring_force_at_zero_n)
    )
    modulus_n_per_cm2 = (
        3.0
        * spring_force_at_zero_n
        * (1.0 + mechanical_indentability * normalized_shore)
        / (8.0 * protrusion_cm * indenter_radius_cm * (1.0 - normalized_shore))
    )
    return modulus_n_per_cm2 * 0.01


def dow_dma_shore_a_to_e_mpa(shore_a: float) -> float:
    return 0.2354 * math.exp(0.0657 * shore_a)


def dow_rda_shore_a_to_e_mpa(shore_a: float) -> float:
    return 0.1611 * math.exp(0.0580 * shore_a)


def dow_secant_shore_a_to_e_mpa(shore_a: float) -> float:
    return 0.1614 * math.exp(0.0541 * shore_a)


def dow_lsr_secant_shore_a_to_e_mpa(shore_a: float) -> float:
    return 0.4865 * math.exp(0.0345 * shore_a)


def dow_tpsiv_secant_shore_a_to_e_mpa(shore_a: float) -> float:
    return 0.6851 * math.exp(0.0578 * shore_a)


def dow_tpsiv_dma_shore_a_to_e_mpa(shore_a: float) -> float:
    return 0.5587 * math.exp(0.0472 * shore_a)


def inverse_erf(value: float) -> float:
    if not (-1.0 < value < 1.0):
        if value == -1.0:
            return -math.inf
        if value == 1.0:
            return math.inf
        raise ValueError("erf inverse input must be in [-1, 1]")
    low = -5.0
    high = 5.0
    for _ in range(80):
        mid = (low + high) / 2.0
        if math.erf(mid) < value:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    x_mean = mean(xs)
    y_mean = mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return y_mean, 0.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - slope * x_mean
    return intercept, slope


def correlation(xs: list[float], ys: list[float]) -> float:
    x_mean = mean(xs)
    y_mean = mean(ys)
    x_var = sum((x - x_mean) ** 2 for x in xs)
    y_var = sum((y - y_mean) ** 2 for y in ys)
    if x_var <= 0 or y_var <= 0:
        return 0.0
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return cov / math.sqrt(x_var * y_var)


def ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            result[indexed[k][0]] = rank
        i = j
    return result


if __name__ == "__main__":
    raise SystemExit(main())
