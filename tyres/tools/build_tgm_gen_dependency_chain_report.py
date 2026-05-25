#!/usr/bin/env python3
"""Build an HTML dependency-chain report for the TGM Gen export."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

import tgm_gen_ods as odsmod


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ODS = REPO_ROOT / "input" / "TGM Gen V0.33 - GY F1 1975 Front.ods"
DEFAULT_OUT = REPO_ROOT / "tyres" / "analysis" / "tgm_gen_dependency_chain.html"


GROUP_COLORS = {
    "Ply geometry": "#4cc9f0",
    "Ply thickness": "#7cda77",
    "Material properties": "#f0b85a",
    "Node-level TGM assembly": "#b090ff",
    "Final export": "#ff8f5c",
    "Visualizer only": "#8aa0b5",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(args.ods.resolve())
    html_text = render_html(report)
    assert_no_visible_cell_addresses(html_text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_text, encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


def build_report(ods: Path) -> dict[str, Any]:
    cells = odsmod.load_formula_cells(ods)
    source = relative_label(ods)

    values = extract_semantic_values(cells)
    evidence = build_evidence(cells)
    export_counts = export_line_counts(cells)

    nodes = [
        node(
            "strand-inputs",
            "Strand Diameter + Strand Spacing",
            "Ply geometry",
            ["Geometry", "Thickness"],
            "Wire or cord diameter and center spacing define the available reinforcing area before any node-specific scaling.",
            values["strand_inputs"],
            evidence=["strand_cross_section", "relative_area"],
        ),
        node(
            "strand-area",
            "Strand Cross Section",
            "Ply geometry",
            ["Geometry", "Thickness"],
            "The generator turns strand diameter into strand area. This is the first geometric reduction from construction input to numeric model input.",
            values["strand_area"],
            evidence=["strand_cross_section"],
        ),
        node(
            "relative-area",
            "Relative Area",
            "Ply thickness",
            ["Thickness"],
            "Cross section is normalized by diameter and spacing. This gives the area fraction carried by the reinforcing strands.",
            values["relative_area"],
            evidence=["relative_area"],
        ),
        node(
            "effective-thickness",
            "Effective Ply Thickness",
            "Ply thickness",
            ["Thickness"],
            "Relative area is converted into an equivalent continuous ply thickness. This value is export relevant.",
            values["effective_thickness"],
            evidence=["effective_thickness"],
        ),
        node(
            "span-angle-inputs",
            "Start/End Nodes + Angle Controls",
            "Ply geometry",
            ["Angle", "Geometry"],
            "Start and end nodes activate each ply over the tyre cross-section. Angle multiplier and minimum angle shape the local orientation.",
            values["span_angle_inputs"],
            evidence=["ply_activation", "angle_controls"],
        ),
        node(
            "local-angle",
            "Local Ply Angle",
            "Ply geometry",
            ["Angle", "Geometry"],
            "The construction sheet derives a local ply angle per active node from the span and angle settings.",
            values["local_angle"],
            evidence=["local_angle"],
        ),
        node(
            "node-thickness",
            "Node-specific Ply Thickness",
            "Ply thickness",
            ["Thickness", "Angle", "Geometry"],
            "Effective thickness is adjusted by local angle, radius/position and thick multipliers for every active node.",
            values["node_thickness"],
            evidence=["node_thickness"],
        ),
        node(
            "material-selection",
            "Material Selection + Multipliers",
            "Material properties",
            ["Material"],
            "Named construction materials are pulled from the material library and scaled by modulus and density multipliers.",
            values["material_selection"],
            evidence=["material_selection"],
        ),
        node(
            "material-lines",
            "PlyMaterial + BulkMaterial + TreadMaterial",
            "Material properties",
            ["Material", "Export"],
            "The generator emits temperature-dependent material lines for reinforcement, bulk rubber and tread compounds.",
            values["material_lines"],
            evidence=["material_lines"],
        ),
        node(
            "tgm-ply-contribution",
            "Directional Stiffness / Mass Contribution",
            "Node-level TGM assembly",
            ["Thickness", "Angle", "Material"],
            "Node ply thickness, local ply angle and material properties are combined into directional model contributions.",
            values["tgm_ply_contribution"],
            evidence=["tgm_ply_contribution"],
        ),
        node(
            "bulk-tread-assembly",
            "Rubber + Tread Node Assembly",
            "Node-level TGM assembly",
            ["Material", "Geometry"],
            "Bulk, filler, belt and tread materials are blended per node from the construction and geometry weights.",
            values["bulk_tread_assembly"],
            evidence=["bulk_tread_assembly"],
        ),
        node(
            "tgm-output",
            "TGM Output Assembly",
            "Node-level TGM assembly",
            ["Export"],
            "The TGM sheet assembles generated text lines for quasi-static settings, node geometry, materials and per-node ply parameters.",
            values["tgm_output"],
            evidence=["tgm_output"],
        ),
        node(
            "final-export",
            "Final TGM Export",
            "Final export",
            ["Export"],
            "The Export sheet forwards the assembled TGM output text into the generated .tgm model.",
            values["final_export"],
            evidence=["final_export"],
        ),
        node(
            "visualizer",
            "Ply Angle Visualiser / Kernfahne",
            "Visualizer only",
            ["Geometry", "Angle"],
            "The visible Kernfahne line is a visual check. Changing only that rendering does not change the export; changing its construction inputs does.",
            values["visualizer"],
            evidence=["visualizer_only"],
        ),
    ]

    edges = [
        edge("strand-inputs", "strand-area", ["Geometry", "Thickness"]),
        edge("strand-area", "relative-area", ["Thickness"]),
        edge("relative-area", "effective-thickness", ["Thickness"]),
        edge("effective-thickness", "node-thickness", ["Thickness"]),
        edge("span-angle-inputs", "local-angle", ["Angle", "Geometry"]),
        edge("local-angle", "node-thickness", ["Angle", "Thickness"]),
        edge("node-thickness", "tgm-ply-contribution", ["Thickness", "Angle"]),
        edge("material-selection", "material-lines", ["Material"]),
        edge("material-lines", "tgm-ply-contribution", ["Material"]),
        edge("material-selection", "bulk-tread-assembly", ["Material"]),
        edge("tgm-ply-contribution", "tgm-output", ["Export", "Thickness", "Angle", "Material"]),
        edge("bulk-tread-assembly", "tgm-output", ["Export", "Material", "Geometry"]),
        edge("tgm-output", "final-export", ["Export"]),
        edge("span-angle-inputs", "visualizer", ["Angle", "Geometry"]),
        edge("local-angle", "visualizer", ["Angle", "Geometry"]),
    ]

    attach_evidence(nodes, evidence)

    return {
        "source": source,
        "nodes": nodes,
        "edges": edges,
        "filters": ["All", "Thickness", "Angle", "Material", "Geometry", "Export"],
        "evidence": evidence,
        "export_counts": export_counts,
        "summary": summary_text(export_counts),
    }


def extract_semantic_values(cells: dict[tuple[str, int, int], odsmod.FormulaCell]) -> dict[str, list[str]]:
    def value(sheet: str, address: str) -> str:
        row, col = odsmod.a1_to_row_col(address)
        cell = cells.get((sheet, row, col))
        if cell is None:
            return ""
        return first_line(cell.display).strip()

    def number(sheet: str, address: str) -> str:
        text = value(sheet, address)
        return compact_number(text) if text else "-"

    active_plies = []
    for label, start, end, material in [
        ("Ply1", "C21", "D21", "C19"),
        ("Ply2", "H21", "I21", "H19"),
        ("Ply3 turnup", "M21", "N21", "M19"),
        ("Ply4", "R21", "S21", "R19"),
        ("Chafer1", "AG21", "AH21", "AG19"),
        ("Chafer2", "AL21", "AM21", "AL19"),
        ("Belt1", "BA21", "BB21", "BA19"),
        ("Belt2", "BF21", "BG21", "BF19"),
    ]:
        start_value = number("Construction", start)
        end_value = number("Construction", end)
        if start_value != "-" and start_value != "-1":
            active_plies.append(f"{label}: active span {start_value} to {end_value}, material {value('Construction', material)}")

    selected_materials = [
        f"Tread: {value('Construction', 'C4')}",
        f"Tread sidewall: {value('Construction', 'G4')}",
        f"Bulk filler: {value('Construction', 'L4')} with E multiplier {number('Construction', 'L7')}, density multiplier {number('Construction', 'M7')}",
        f"Bulk sidewall: {value('Construction', 'P4')} with E multiplier {number('Construction', 'P7')}, density multiplier {number('Construction', 'Q7')}",
        f"Bulk belt: {value('Construction', 'T4')} with E multiplier {number('Construction', 'T7')}, density multiplier {number('Construction', 'U7')}",
        f"Bead wire: {value('Construction', 'AG4')} with E multiplier {number('Construction', 'AH7')}, density multiplier {number('Construction', 'AJ7')}",
    ]

    return {
        "strand_inputs": [
            f"Ply cord diameter: {number('Construction', 'C38')} m",
            f"Ply cord spacing: {number('Construction', 'C39')} m",
            f"Belt cord diameter: {number('Construction', 'I38')} m",
        ],
        "strand_area": [
            f"Ply strand area: {number('Construction', 'C40')} square m",
            f"Belt strand area: {number('Construction', 'I40')} square m",
        ],
        "relative_area": [
            f"Ply relative area: {number('Construction', 'C41')}",
            f"Belt relative area: {number('Construction', 'I41')}",
        ],
        "effective_thickness": [
            f"Ply effective thickness: {number('Construction', 'C42')} m",
            f"Chafer effective thickness: {number('Construction', 'F42')} m",
            f"Belt effective thickness: {number('Construction', 'I42')} m",
        ],
        "span_angle_inputs": active_plies[:8]
        + [
            f"Angle multiplier: {number('Construction', 'B45')}",
            f"Minimum angle: {number('Construction', 'B46')} deg",
            f"Thick multiplier: {number('Construction', 'C44')}",
        ],
        "local_angle": [
            "Calculated for each active node and ply family.",
            "Used by node thickness and directional stiffness calculations.",
        ],
        "node_thickness": [
            "Per-node ply thickness is present for ply, turnup, chafer and belt families.",
            "The calculation uses effective ply thickness, local angle, node radius/position and thick multiplier.",
        ],
        "material_selection": selected_materials,
        "material_lines": [
            "PlyMaterial lines are emitted for reinforcement plies.",
            "BulkMaterial lines are emitted for filler, sidewall, belt and liner rubber.",
            "TreadMaterial lines are emitted for tread cap and tread sidewall.",
        ],
        "tgm_ply_contribution": [
            "Thickness and angle control the active contribution at each node.",
            "Material properties control density, modulus, heat capacity and conductivity.",
        ],
        "bulk_tread_assembly": [
            "Geometry weights blend filler, sidewall and belt rubber at node level.",
            "Tread and tread-sidewall selections are forwarded into TGM material output.",
        ],
        "tgm_output": [
            "The TGM sheet assembles complete model text sections.",
            "Node geometry, material definitions and PlyParams are combined before export.",
        ],
        "final_export": [
            "The Export sheet forwards assembled TGM lines.",
            "The generated model changes when export-relevant construction inputs change.",
        ],
        "visualizer": [
            "The visualizer line is a construction sanity check.",
            "It depends on construction and geometry inputs but is not itself a model object.",
        ],
    }


def build_evidence(cells: dict[tuple[str, int, int], odsmod.FormulaCell]) -> dict[str, dict[str, str]]:
    checks = {
        "strand_cross_section": (
            "Strand cross section formula uses strand diameter.",
            ("Construction", "C40"),
            ["C38"],
        ),
        "relative_area": (
            "Relative area formula uses strand cross section, diameter and spacing.",
            ("Construction", "C41"),
            ["C40", "C38", "C39"],
        ),
        "effective_thickness": (
            "Effective ply thickness formula uses strand diameter and relative area.",
            ("Construction", "C42"),
            ["C38", "C41"],
        ),
        "ply_activation": (
            "Ply activation is derived from start/end node definitions.",
            ("Construction", "C37"),
            ["C21", "H21"],
        ),
        "angle_controls": (
            "Angle controls feed the local-angle calculation region.",
            ("Construction", "B47"),
            ["B45", "B46"],
        ),
        "local_angle": (
            "Local angle formulas depend on the angle controls and active span.",
            ("Construction", "B95"),
            ["B45", "B46"],
        ),
        "node_thickness": (
            "Node-specific thickness formula uses effective thickness, local angle, node position and thick multiplier.",
            ("Construction", "C57"),
            ["C42", "B57", "AM57", "C44"],
        ),
        "material_selection": (
            "Construction material cells pull data from the material library and apply multipliers.",
            ("Construction", "P10"),
            ["P7"],
        ),
        "material_lines": (
            "Construction emits material text from resolved material properties.",
            ("Construction", "C31"),
            ["C23", "C24", "C25"],
        ),
        "tgm_ply_contribution": (
            "TGM ply contribution uses node-specific ply thickness.",
            ("TGM", "BT140"),
            ["Construction.C57"],
        ),
        "bulk_tread_assembly": (
            "TGM rubber assembly uses construction material values and geometry weights.",
            ("TGM", "AP163"),
            ["Construction.L9", "Construction.P9", "Geometry.N47"],
        ),
        "tgm_output": (
            "TGM output text is forwarded into the export sheet.",
            ("Export", "A1"),
            ["TGM."],
        ),
        "final_export": (
            "Final export lines are stored in the Export sheet.",
            ("Export", "A1"),
            ["TGM."],
        ),
        "visualizer_only": (
            "Visualizer formulas produce chart coordinates; no exported line is based on the rendered curve itself.",
            ("Construction", "AN57"),
            ["AM57", "AN56"],
        ),
    }

    evidence: dict[str, dict[str, str]] = {}
    for key, (description, target, needles) in checks.items():
        formula = formula_for(cells, target[0], target[1])
        normalized = formula.replace("$", "")
        ok = all(needle in normalized for needle in needles)
        evidence[key] = {
            "description": description,
            "status": "verified" if ok else "manual",
        }
    return evidence


def export_line_counts(cells: dict[tuple[str, int, int], odsmod.FormulaCell]) -> dict[str, int]:
    counts = {
        "total": 0,
        "Geometry": 0,
        "PlyParams": 0,
        "PlyMaterial": 0,
        "BulkMaterial": 0,
        "TreadMaterial": 0,
    }
    for (sheet, _row, col), cell in cells.items():
        if sheet != "Export" or col != 1:
            continue
        text = cell.display.strip()
        if not text:
            continue
        counts["total"] += 1
        for key in list(counts):
            if key != "total" and text.startswith(f"{key}="):
                counts[key] += 1
    return counts


def summary_text(export_counts: dict[str, int]) -> list[str]:
    return [
        "Export-relevant: material selections, multipliers, ply span/angle controls, cord geometry, effective thickness and node-specific ply thickness.",
        "Visualizer only: the drawn Kernfahne/polyline. It is useful for checking the construction but is not the exported object.",
        f"Generated export content includes {export_counts['Geometry']} Geometry lines, {export_counts['PlyParams']} PlyParams lines, {export_counts['PlyMaterial']} PlyMaterial lines, {export_counts['BulkMaterial']} BulkMaterial lines and {export_counts['TreadMaterial']} TreadMaterial lines.",
    ]


def attach_evidence(nodes: list[dict[str, Any]], evidence: dict[str, dict[str, str]]) -> None:
    for item in nodes:
        item["evidence"] = [evidence[key] for key in item.pop("evidenceKeys") if key in evidence]


def node(
    node_id: str,
    label: str,
    group: str,
    tags: list[str],
    summary: str,
    details: list[str],
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "group": group,
        "tags": tags,
        "summary": summary,
        "details": details,
        "evidenceKeys": evidence,
    }


def edge(source: str, target: str, tags: list[str]) -> dict[str, Any]:
    return {"source": source, "target": target, "tags": tags}


def formula_for(cells: dict[tuple[str, int, int], odsmod.FormulaCell], sheet: str, address: str) -> str:
    row, col = odsmod.a1_to_row_col(address)
    cell = cells.get((sheet, row, col))
    return cell.formula if cell is not None else ""


def first_line(value: str) -> str:
    return str(value or "").splitlines()[-1]


def compact_number(value: str) -> str:
    text = str(value).strip()
    if text == "":
        return "-"
    try:
        number = float(text)
    except ValueError:
        return text
    if abs(number) >= 1000 or (0 < abs(number) < 0.001):
        return f"{number:.4g}"
    return f"{number:.6g}"


def relative_label(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def render_html(report: dict[str, Any]) -> str:
    nodes_json = json.dumps(report["nodes"], ensure_ascii=True)
    edges_json = json.dumps(report["edges"], ensure_ascii=True)
    source = escape(report["source"])
    summary_items = "\n".join(f"<li>{escape(item)}</li>" for item in report["summary"])
    filter_buttons = "\n".join(
        f'<button class="filter-button{" active" if item == "All" else ""}" data-filter="{escape(item)}">{escape(item)}</button>'
        for item in report["filters"]
    )
    legend = "\n".join(
        f'<span class="legend-item"><span class="swatch" style="background:{color}"></span>{escape(group)}</span>'
        for group, color in GROUP_COLORS.items()
    )
    svg = render_svg(report["nodes"], report["edges"])

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TGM Gen Dependency Chain</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1014;
      --panel: #111922;
      --panel2: #162230;
      --line: #263444;
      --text: #e7eef5;
      --muted: #91a4b7;
      --accent: #72b7ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 13px/1.45 Segoe UI, Roboto, Arial, sans-serif;
    }}
    header, main {{ max-width: 1480px; margin: 0 auto; padding: 22px; }}
    header {{ border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0 0 8px; font-size: 28px; font-weight: 750; }}
    h2 {{ margin: 0 0 10px; font-size: 18px; }}
    p {{ margin: 6px 0; color: var(--muted); }}
    code {{ color: #b9d8f2; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(360px, .9fr); gap: 14px; align-items: start; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .summary {{ display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 14px; margin-bottom: 14px; }}
    .summary ul {{ margin: 0; padding-left: 18px; color: #cdd9e4; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }}
    button {{
      appearance: none;
      border: 1px solid var(--line);
      background: #0f171f;
      color: #d8e6f2;
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
      font: inherit;
    }}
    button.active {{ border-color: var(--accent); background: #12304a; color: #fff; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 10px; color: #c9d7e3; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
    .swatch {{ width: 11px; height: 11px; border-radius: 3px; display: inline-block; border: 1px solid rgba(255,255,255,.25); }}
    .flow-wrap {{ overflow: auto; border: 1px solid var(--line); border-radius: 8px; background: #0d151d; }}
    svg {{ min-width: 1120px; width: 100%; height: auto; display: block; }}
    .edge {{ stroke: #5e7489; stroke-width: 2; marker-end: url(#arrow); opacity: .7; }}
    .flow-node rect {{ stroke: rgba(255,255,255,.22); stroke-width: 1.2; rx: 8; }}
    .flow-node text {{ fill: #f6fbff; font-weight: 700; pointer-events: none; }}
    .flow-node .tagline {{ fill: #c1cfdb; font-weight: 500; }}
    .flow-node {{ cursor: pointer; opacity: .94; }}
    .flow-node:hover rect {{ stroke: #ffffff; }}
    .flow-node.selected rect {{ stroke: #ffffff; stroke-width: 2.2; }}
    .hidden {{ display: none; }}
    .detail-title {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; }}
    .group-pill {{ display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px; border: 1px solid var(--line); border-radius: 999px; color: #d8e6f2; white-space: nowrap; }}
    .detail-list, .evidence-list {{ margin: 10px 0 0; padding-left: 18px; }}
    .detail-list li, .evidence-list li {{ margin: 5px 0; color: #cdd9e4; }}
    .tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
    .tag {{ border: 1px solid #314457; background: #0e1822; border-radius: 999px; padding: 2px 8px; color: #bdd3e6; }}
    .note {{ color: #cdd9e4; border-left: 3px solid var(--accent); padding: 8px 10px; background: #0f1b26; }}
    .small {{ color: var(--muted); font-size: 12px; }}
    @media (max-width: 1100px) {{
      .layout, .summary {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <h1>TGM Gen Dependency Chain</h1>
  <p>Quelle: <code>{source}</code></p>
</header>
<main>
  <section class="summary">
    <div class="panel note">
      <ul>
        {summary_items}
      </ul>
    </div>
    <div class="panel">
      <h2>Gruppen</h2>
      <div class="legend">{legend}</div>
    </div>
  </section>
  <section class="layout">
    <div class="panel">
      <h2>Formelpfad</h2>
      <div class="filters">{filter_buttons}</div>
      <div class="flow-wrap">{svg}</div>
    </div>
    <aside class="panel" id="detail-panel">
      <h2>Detail</h2>
      <p class="small">Klicke einen Knoten im Diagramm an.</p>
    </aside>
  </section>
</main>
<script>
const nodes = {nodes_json};
const edges = {edges_json};
const groupColors = {json.dumps(GROUP_COLORS, ensure_ascii=True)};
let activeFilter = "All";
let selectedNode = nodes[0]?.id || "";

function escapeHtml(value) {{
  return String(value ?? "").replace(/[&<>"']/g, char => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[char]));
}}

function matchesFilter(tags) {{
  return activeFilter === "All" || tags.includes(activeFilter);
}}

function renderDetail(nodeId) {{
  const node = nodes.find(item => item.id === nodeId) || nodes[0];
  if (!node) return;
  selectedNode = node.id;
  document.querySelectorAll(".flow-node").forEach(item => item.classList.toggle("selected", item.dataset.id === node.id));
  const color = groupColors[node.group] || "#72b7ff";
  const detailItems = node.details.map(item => `<li>${{escapeHtml(item)}}</li>`).join("");
  const evidenceItems = node.evidence.map(item => `<li>${{escapeHtml(item.description)}} <span class="small">(${{escapeHtml(item.status)}})</span></li>`).join("");
  const tags = node.tags.map(item => `<span class="tag">${{escapeHtml(item)}}</span>`).join("");
  document.getElementById("detail-panel").innerHTML = `
    <div class="detail-title">
      <h2>${{escapeHtml(node.label)}}</h2>
      <span class="group-pill"><span class="swatch" style="background:${{color}}"></span>${{escapeHtml(node.group)}}</span>
    </div>
    <p>${{escapeHtml(node.summary)}}</p>
    <div class="tags">${{tags}}</div>
    <ul class="detail-list">${{detailItems}}</ul>
    <h2 style="margin-top:18px">Formelbelege</h2>
    <ul class="evidence-list">${{evidenceItems}}</ul>
  `;
}}

function applyFilter(filter) {{
  activeFilter = filter;
  document.querySelectorAll(".filter-button").forEach(button => button.classList.toggle("active", button.dataset.filter === filter));
  document.querySelectorAll(".flow-node").forEach(item => {{
    const tags = item.dataset.tags.split(",");
    item.classList.toggle("hidden", !matchesFilter(tags));
  }});
  document.querySelectorAll(".edge").forEach(item => {{
    const tags = item.dataset.tags.split(",");
    item.classList.toggle("hidden", !matchesFilter(tags));
  }});
}}

document.querySelectorAll(".flow-node").forEach(item => item.addEventListener("click", () => renderDetail(item.dataset.id)));
document.querySelectorAll(".filter-button").forEach(button => button.addEventListener("click", () => applyFilter(button.dataset.filter)));
renderDetail(selectedNode);
</script>
</body>
</html>
"""


def render_svg(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    positions = {
        "strand-inputs": (40, 70),
        "strand-area": (290, 70),
        "relative-area": (540, 70),
        "effective-thickness": (790, 70),
        "span-angle-inputs": (40, 220),
        "local-angle": (290, 220),
        "node-thickness": (540, 220),
        "material-selection": (40, 370),
        "material-lines": (290, 370),
        "tgm-ply-contribution": (790, 250),
        "bulk-tread-assembly": (540, 430),
        "tgm-output": (790, 430),
        "final-export": (1040, 430),
        "visualizer": (540, 570),
    }
    size = (210, 86)
    node_by_id = {item["id"]: item for item in nodes}

    edge_lines = []
    for item in edges:
        source = positions[item["source"]]
        target = positions[item["target"]]
        x1 = source[0] + size[0]
        y1 = source[1] + size[1] / 2
        x2 = target[0]
        y2 = target[1] + size[1] / 2
        if target[0] <= source[0]:
            x1 = source[0] + size[0] / 2
            y1 = source[1] + size[1]
            x2 = target[0] + size[0] / 2
            y2 = target[1]
        edge_lines.append(
            f'<path class="edge" data-tags="{escape(",".join(item["tags"]))}" d="M {x1:.1f} {y1:.1f} C {(x1 + x2) / 2:.1f} {y1:.1f}, {(x1 + x2) / 2:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}" />'
        )

    node_groups = []
    for item in nodes:
        x, y = positions[item["id"]]
        color = GROUP_COLORS.get(item["group"], "#72b7ff")
        label_lines = wrap_label(item["label"], 22)
        title = escape(item["label"])
        tags = escape(",".join(item["tags"]))
        text_parts = []
        for index, line in enumerate(label_lines[:2]):
            text_parts.append(
                f'<text x="{x + 14}" y="{y + 28 + index * 17}" font-size="13">{escape(line)}</text>'
            )
        text_parts.append(
            f'<text class="tagline" x="{x + 14}" y="{y + 70}" font-size="11">{escape(item["group"])}</text>'
        )
        node_groups.append(
            f'<g class="flow-node" data-id="{escape(item["id"])}" data-tags="{tags}">'
            f"<title>{title}</title>"
            f'<rect x="{x}" y="{y}" width="{size[0]}" height="{size[1]}" fill="{color}" fill-opacity=".72" />'
            + "".join(text_parts)
            + "</g>"
        )

    return (
        '<svg viewBox="0 0 1280 700" role="img" aria-label="TGM Gen dependency flow">'
        "<defs>"
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L0,6 L9,3 z" fill="#5e7489" />'
        "</marker>"
        "</defs>"
        + "".join(edge_lines)
        + "".join(node_groups)
        + "</svg>"
    )


def wrap_label(label: str, width: int) -> list[str]:
    words = label.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [label]


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def assert_no_visible_cell_addresses(html_text: str) -> None:
    text = re.sub(r"<script>.*?</script>", "", html_text, flags=re.DOTALL)
    patterns = [
        re.compile(r"\b(?:Construction|TGM|Export|Geometry|Materials|About|TBC)![A-Z]{1,3}[0-9]{1,5}\b"),
        re.compile(r"\b(?:AM47|AN57|C42|BT130|AP163|C57|B57|C38|C39)\b"),
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(pattern.findall(text))
    matches = sorted(set(matches))
    if matches:
        raise AssertionError(f"visible spreadsheet-like addresses found: {', '.join(matches[:10])}")


if __name__ == "__main__":
    raise SystemExit(main())
