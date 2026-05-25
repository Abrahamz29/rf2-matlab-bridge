#!/usr/bin/env python3
"""Build an HTML comparison of TGM Gen source materials and recognition output."""

from __future__ import annotations

import argparse
import html
import math
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import tgm_gen_ods as odsmod


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ODS = REPO_ROOT / "input" / "TGM Gen V0.33 - GY F1 1975 Front.ods"
DEFAULT_OUT = REPO_ROOT / "tyres" / "analysis" / "tgm_gen_material_recognition_compare.html"
KIND_COLUMNS = ["Tread", "Bulk"]
MATERIAL_RECOGNITION_TOP_N = 12
GLOBAL_DOMINANT_SCOPES = {"PlyMaterial", "TreadMaterial:cap", "BulkMaterial:filler"}
GLOBAL_DOMINANCE_MIN = 0.80
GLOBAL_DOMINANCE_MIN_BY_SCOPE = {"BulkMaterial:filler": 0.50}
GLOBAL_DOMINANCE_LEAD_MIN_BY_SCOPE = {"BulkMaterial:filler": 0.20}
GLOBAL_DOMINANCE_RATIO_MIN_BY_SCOPE = {"BulkMaterial:filler": 1.75}
GLOBAL_OVERRIDE_MAX_SCORE = 0.16
GLOBAL_OVERRIDE_SCORE_MARGIN = 0.08
UNKNOWN_SCORE_MAX = 0.28


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(args.ods.resolve())
    html_text = render_html(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


def build_report(ods: Path) -> dict[str, Any]:
    cells = odsmod.load_formula_cells(ods)
    library = odsmod.extract_material_library(ods)
    out_dir = Path(tempfile.mkdtemp(prefix="tgm_gen_material_report_"))
    export = odsmod.export_reference(ods, out_dir)
    tgm_path = Path(export["exports"]["tgm"]["path"])
    tgm_groups, node_count, max_layer, geometry = parse_tgm_groups(tgm_path)

    used = selected_materials(cells)
    for group in tgm_groups:
        group["candidates"] = material_candidate_matches(group, library["materials"])
        group["localBest"] = group["candidates"][0] if group["candidates"] else None
        group["best"] = group["localBest"]
        group["excel"] = expected_excel_material(group, used)
    global_probabilities = apply_global_material_probability(tgm_groups)

    recognized_summary = summarize_groups(tgm_groups, "best")
    excel_summary = summarize_groups(tgm_groups, "excel")
    differences = compare_expected_and_recognized(used, recognized_summary)
    matrices = build_matrices(tgm_groups, node_count, max_layer)

    return {
        "ods": str(ods.relative_to(REPO_ROOT) if ods.is_relative_to(REPO_ROOT) else ods),
        "tgm": str(tgm_path),
        "used": used,
        "recognized_summary": recognized_summary,
        "excel_summary": excel_summary,
        "global_probabilities": global_probabilities,
        "differences": differences,
        "matrices": matrices,
        "geometry": geometry,
        "node_count": node_count,
        "max_layer": max_layer,
    }


def selected_materials(cells: dict[tuple[str, int, int], odsmod.FormulaCell]) -> list[dict[str, Any]]:
    def cell_value(address: str) -> str:
        row, col = odsmod.a1_to_row_col(address)
        cell = cells.get(("Construction", row, col))
        return cell.display.strip() if cell and cell.display else ""

    specs = [
        ("Tread", "TreadMaterial", "C4", "C7", "D7"),
        ("Tread Sidewall", "TreadMaterial", "G4", "G7", "H7"),
        ("Bulk Bead/Filler", "BulkMaterial", "L4", "L7", "M7"),
        ("Bulk Sidewall", "BulkMaterial", "P4", "P7", "Q7"),
        ("Bulk Belt", "BulkMaterial", "T4", "T7", "U7"),
        ("Inner Liner", "BulkMaterial", "Y4", "Y7", "Z7"),
        ("Bead", "PlyMaterial", "AG4", "AH7", "AJ7"),
        ("Ply1", "PlyMaterial", "C19", "D22", "F22"),
        ("Ply2", "PlyMaterial", "H19", "I22", "K22"),
        ("Ply3", "PlyMaterial", "M19", "N22", "P22"),
        ("Ply4", "PlyMaterial", "R19", "S22", "U22"),
        ("Ply5", "PlyMaterial", "W19", "X22", "Z22"),
        ("Ply6", "PlyMaterial", "AB19", "AC22", "AE22"),
        ("Bead ply", "PlyMaterial", "AG19", "AH22", "AJ22"),
    ]
    rows: list[dict[str, Any]] = []
    for role, kind, material_cell, e_cell, density_cell in specs:
        material = cell_value(material_cell)
        if not material:
            continue
        rows.append(
            {
                "role": role,
                "kind": kind,
                "material": material,
                "eMultiplier": number_or_text(cell_value(e_cell)),
                "densityMultiplier": number_or_text(cell_value(density_cell)),
            }
        )
    return rows


def parse_tgm_groups(tgm_path: Path) -> tuple[list[dict[str, Any]], int, int, dict[int, tuple[float, float, float]]]:
    text = tgm_path.read_text(encoding="utf-8", errors="replace")
    nodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"\[Node\]\s*//\s*(\d+)", line)
        if match:
            current = {
                "node": int(match.group(1)),
                "TreadMaterial": [],
                "BulkMaterial": [],
                "PlyMaterial": [],
                "PlyParams": [],
                "Geometry": [],
            }
            nodes.append(current)
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in current:
            continue
        values = [parse_float(part.strip()) for part in value.split("//", 1)[0].strip().strip("()").split(",")]
        current[key].append(values)

    groups: list[dict[str, Any]] = []
    max_layer = 0
    geometry: dict[int, tuple[float, float, float]] = {}
    for node in nodes:
        if node["Geometry"]:
            radial, lateral, thickness = (node["Geometry"][0] + [0.0, 0.0, 0.0])[:3]
            if radial is not None and lateral is not None:
                geometry[node["node"]] = (radial, lateral, thickness or 0.0)
        for kind in ("TreadMaterial", "BulkMaterial", "PlyMaterial"):
            for index, rows in enumerate(split_material_rows(node[kind]), start=1):
                group: dict[str, Any] = {
                    "node": node["node"],
                    "kind": kind,
                    "index": index,
                    "rows": rows,
                    "column": kind_to_column(kind, index),
                }
                if kind == "PlyMaterial":
                    max_layer = max(max_layer, index)
                    ply_params = node["PlyParams"]
                    if index <= len(ply_params):
                        group["angleDeg"] = ply_params[index - 1][0]
                        group["thicknessM"] = ply_params[index - 1][1]
                groups.append(group)
    return groups, len(nodes), max_layer, geometry


def split_material_rows(rows: list[list[float | None]]) -> list[list[list[float | None]]]:
    groups: list[list[list[float | None]]] = []
    current: list[list[float | None]] = []
    previous_temp: float | None = None
    for row in rows:
        temp = row[0] if row else None
        if current and previous_temp is not None and temp is not None and temp <= previous_temp:
            groups.append(current)
            current = []
        current.append(row)
        previous_temp = temp
    if current:
        groups.append(current)
    return groups


def expected_excel_material(group: dict[str, Any], used: list[dict[str, Any]]) -> dict[str, Any]:
    kind = group["kind"]
    if kind == "TreadMaterial":
        candidates = [row for row in used if row["kind"] == "TreadMaterial"]
        return expected_by_property_match(group, candidates, "Excel tread source")
    if kind == "BulkMaterial":
        sources = [row for row in used if row["kind"] == "BulkMaterial"]
        label = " + ".join(short_material_name(row["material"]) for row in sources[:3])
        return {
            "material": label,
            "label": "Bulk formula",
            "role": "Formula",
            "kind": kind,
            "note": "Excel formula from selected filler, sidewall, belt and liner/tread influence",
        }
    if kind == "PlyMaterial":
        e_values = [value for row in group["rows"] if len(row) > 2 for value in [row[2]] if value is not None]
        density_values = [value for row in group["rows"] if len(row) > 1 for value in [row[1]] if value is not None]
        if e_values and max(e_values) > 1.0e10 or density_values and max(density_values) > 5000:
            selected = first_used_material(used, "Bead")
        else:
            selected = first_used_material(used, "Ply1")
        return {
            "material": selected.get("material", "Ply source"),
            "label": short_material_name(selected.get("material", "Ply source")),
            "role": selected.get("role", "Ply"),
            "kind": kind,
            "eMultiplier": selected.get("eMultiplier"),
            "densityMultiplier": selected.get("densityMultiplier"),
        }
    return {"material": kind, "label": kind, "role": kind, "kind": kind}


def expected_by_property_match(group: dict[str, Any], candidates: list[dict[str, Any]], note: str) -> dict[str, Any]:
    best = None
    for candidate in candidates:
        score = simple_expected_score(group, candidate)
        if best is None or score < best["score"]:
            best = {**candidate, "score": score}
    if not best:
        return {"material": group["kind"], "label": group["kind"], "role": group["kind"], "kind": group["kind"]}
    return {
        "material": best["material"],
        "label": short_material_name(best["material"]),
        "role": best["role"],
        "kind": best["kind"],
        "score": best["score"],
        "note": note,
    }


def simple_expected_score(group: dict[str, Any], candidate: dict[str, Any]) -> float:
    # The ODS source materials are already known. For tread, a density/E distance
    # is enough to split tread center from tread-sidewall regions in this example.
    material = candidate["material"].lower()
    target_e = 3.7e6 if "sidewall" in material else 3.8e6
    values = [row[2] for row in group["rows"] if len(row) > 2 and row[2] is not None]
    if not values:
        return 999.0
    return abs(math.log(max(values) / target_e))


def first_used_material(used: list[dict[str, Any]], role: str) -> dict[str, Any]:
    for row in used:
        if row["role"] == role:
            return row
    return {}


def best_material_match(group: dict[str, Any], materials: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = material_candidate_matches(group, materials)
    return matches[0] if matches else None


def material_candidate_matches(group: dict[str, Any], materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for material in materials:
        if not material_candidate_for_kind(group["kind"], material):
            continue
        match = match_material_candidate(group, material)
        if match:
            candidates.append(match)
    candidates.sort(key=lambda item: item["score"])
    return dedupe_material_candidates(candidates)[:MATERIAL_RECOGNITION_TOP_N]


def dedupe_material_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = material_identity_key(candidate)
        existing = by_key.get(key)
        if existing is None or candidate["score"] < existing["score"]:
            by_key[key] = candidate
    return sorted(by_key.values(), key=lambda item: item["score"])


def material_identity_key(candidate: dict[str, Any]) -> str:
    return f"{candidate.get('category', '')}|{candidate.get('material', '')}".lower()


def apply_global_material_probability(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    totals: Counter[str] = Counter()
    scope_meta: dict[str, tuple[str, str]] = {}
    for group in groups:
        local = group.get("localBest")
        if not local or local.get("score", math.inf) > UNKNOWN_SCORE_MAX:
            continue
        scope = material_global_scope(group["kind"], local)
        scope_meta[scope] = (group["kind"], material_global_scope_label(scope))
        counts[(scope, local["material"])] += 1
        totals[scope] += 1

    dominant_by_scope: dict[str, dict[str, Any]] = {}
    for scope in totals:
        ranked = sorted(
            ((material, count) for (candidate_scope, material), count in counts.items() if candidate_scope == scope),
            key=lambda item: (-item[1], item[0]),
        )
        material, count = ranked[0]
        probability = count / max(totals[scope], 1)
        second_probability = ranked[1][1] / max(totals[scope], 1) if len(ranked) > 1 else 0.0
        dominant_by_scope[scope] = {
            "material": material,
            "probability": probability,
            "secondProbability": second_probability,
            "leadProbability": probability - second_probability,
            "count": count,
            "dominant": global_dominance_accepts(scope, probability, second_probability),
        }

    for group in groups:
        kind = group["kind"]
        local = group.get("localBest")
        if not local:
            continue
        local_scope = material_global_scope(kind, local)
        final = dict(local)
        final["localMaterial"] = local["material"]
        final["globalScope"] = local_scope
        final["globalScopeLabel"] = material_global_scope_label(local_scope)
        final["globalProbability"] = counts[(local_scope, local["material"])] / max(totals[local_scope], 1) if totals[local_scope] else 0
        final["globalGroupCount"] = counts[(local_scope, local["material"])]
        final["globalOverride"] = False

        dominant = dominant_by_scope.get(local_scope)
        if dominant and local_scope in GLOBAL_DOMINANT_SCOPES:
            dominant_material = dominant["material"]
            dominant_probability = dominant["probability"]
            dominant_count = dominant["count"]
            dominant_candidate = next(
                (
                    candidate
                    for candidate in group.get("candidates", [])
                    if candidate["material"] == dominant_material and material_global_scope(kind, candidate) == local_scope
                ),
                None,
            )
            if (
                dominant_candidate
                and dominant_material != local["material"]
                and dominant["dominant"]
                and dominant_candidate.get("score", math.inf) <= GLOBAL_OVERRIDE_MAX_SCORE
                and dominant_candidate.get("score", math.inf) <= local.get("score", math.inf) + GLOBAL_OVERRIDE_SCORE_MARGIN
            ):
                final = dict(dominant_candidate)
                final["localMaterial"] = local["material"]
                final["globalScope"] = local_scope
                final["globalScopeLabel"] = material_global_scope_label(local_scope)
                final["globalProbability"] = dominant_probability
                final["globalGroupCount"] = dominant_count
                final["globalOverride"] = True

        group["best"] = final

    rows = []
    for (scope, material), count in sorted(counts.items(), key=lambda item: (scope_meta[item[0][0]][0], item[0][0], -item[1], item[0][1])):
        kind, label = scope_meta[scope]
        probability = count / max(totals[scope], 1)
        dominant = dominant_by_scope[scope]
        is_dominant = dominant["material"] == material and dominant["dominant"]
        rows.append(
            {
                "kind": kind,
                "scope": scope,
                "scopeLabel": label,
                "material": material,
                "localWinnerCount": count,
                "total": totals[scope],
                "probability": probability,
                "secondProbability": dominant["secondProbability"] if dominant["material"] == material else None,
                "leadProbability": dominant["leadProbability"] if dominant["material"] == material else None,
                "dominant": is_dominant,
                "stabilized": scope in GLOBAL_DOMINANT_SCOPES and is_dominant,
            }
        )
    return rows


def global_dominance_accepts(scope: str, probability: float, second_probability: float) -> bool:
    minimum = GLOBAL_DOMINANCE_MIN_BY_SCOPE.get(scope, GLOBAL_DOMINANCE_MIN)
    if probability < minimum:
        return False
    lead_minimum = GLOBAL_DOMINANCE_LEAD_MIN_BY_SCOPE.get(scope, 0.0)
    ratio_minimum = GLOBAL_DOMINANCE_RATIO_MIN_BY_SCOPE.get(scope, 0.0)
    if lead_minimum and probability - second_probability < lead_minimum:
        return False
    if ratio_minimum and second_probability > 0 and probability / second_probability < ratio_minimum:
        return False
    return True


def material_global_scope(kind: str, candidate: dict[str, Any]) -> str:
    if kind == "PlyMaterial":
        return "PlyMaterial"
    text = f"{candidate.get('category', '')} {candidate.get('material', '')}".lower()
    if kind == "TreadMaterial":
        if "sidewall" in text:
            return "TreadMaterial:tread-sidewall"
        return "TreadMaterial:cap"
    if kind == "BulkMaterial":
        if re.search(r"filler|bead|apex", text):
            return "BulkMaterial:filler"
        if "inner liner" in text:
            return "BulkMaterial:inner-liner"
        if "belt" in text:
            return "BulkMaterial:belt"
        if "sidewall" in text:
            return "BulkMaterial:sidewall"
        return "BulkMaterial:bulk"
    return kind


def material_global_scope_label(scope: str) -> str:
    labels = {
        "PlyMaterial": "Ply",
        "TreadMaterial:cap": "Cap / Tread",
        "TreadMaterial:tread-sidewall": "Tread Sidewall",
        "BulkMaterial:filler": "Filler / Bead / Apex",
        "BulkMaterial:inner-liner": "Inner Liner",
        "BulkMaterial:belt": "Belt",
        "BulkMaterial:sidewall": "Sidewall Bulk",
        "BulkMaterial:bulk": "Bulk",
    }
    return labels.get(scope, scope)


def material_candidate_for_kind(kind: str, material: dict[str, Any]) -> bool:
    category = str(material.get("category", "")).lower()
    if kind == "PlyMaterial":
        return "ply" in category or "reinforcement" in category
    if kind == "BulkMaterial":
        return bool(re.search(r"bulk|filler|bead|apex|inner liner", category))
    if kind == "TreadMaterial":
        return bool(re.search(r"rubber tread|tread sidewall|inner liner", category))
    return True


def match_material_candidate(group: dict[str, Any], material: dict[str, Any]) -> dict[str, Any] | None:
    points = normalized_material_points(material)
    if not points:
        return None
    fields = [
        ("youngsModulusPa", "youngsModulusPa", 2.6, "scaled", "eMultiplier"),
        ("densityKgM3", "densityKgM3", 1.1, "scaled", "densityMultiplier"),
        ("poissonRatio", "poissonsRatio", 1.7, "abs", None),
        ("compressionMultiplier", "compressionTensionRatio", 1.7, "log", None),
        ("specificHeatJKgK", "specificHeat", 0.65, "log", None),
        ("conductivityWMK", "thermalConductivity", 0.9, "log", None),
    ]
    observed = observed_points(group)
    weighted_score = 0.0
    weight_sum = 0.0
    result: dict[str, Any] = {
        "material": material["name"],
        "label": short_material_name(material["name"]),
        "category": material["category"],
        "score": math.inf,
        "eMultiplier": None,
        "densityMultiplier": None,
    }
    for observed_field, base_field, weight, mode, multiplier_name in fields:
        obs_values = []
        base_values = []
        for point in observed:
            observed_value = point.get(observed_field)
            base_value = interpolate_material_value(points, point.get("temperatureK"), base_field)
            if observed_value is not None and base_value is not None:
                obs_values.append(observed_value)
                base_values.append(base_value)
        if not obs_values:
            continue
        if mode == "scaled":
            multiplier, residual = scaled_log_fit(obs_values, base_values)
            if residual is None:
                continue
            residual += scale_penalty(multiplier)
            result[multiplier_name] = multiplier
        elif mode == "log":
            residual = log_residual(obs_values, base_values)
            if residual is None:
                continue
        else:
            residual = absolute_residual(obs_values, base_values, 0.08)
            if residual is None:
                continue
        weighted_score += residual * weight
        weight_sum += weight
    if weight_sum <= 0:
        return None
    result["score"] = weighted_score / weight_sum
    return result


def observed_points(group: dict[str, Any]) -> list[dict[str, float]]:
    points = []
    for row in group["rows"]:
        if len(row) < 7:
            continue
        points.append(
            {
                "temperatureK": row[0],
                "densityKgM3": row[1],
                "youngsModulusPa": row[2],
                "poissonRatio": row[3],
                "compressionMultiplier": row[4],
                "specificHeatJKgK": row[5],
                "conductivityWMK": row[6],
            }
        )
    return points


def normalized_material_points(material: dict[str, Any]) -> list[dict[str, float | None]]:
    points = []
    for point in material.get("points", []):
        points.append(
            {
                "temperatureK": parse_float(point.get("temperatureK")),
                "densityKgM3": parse_float(point.get("densityKgM3")),
                "youngsModulusPa": parse_float(point.get("youngsModulusPa")),
                "poissonsRatio": parse_float(point.get("poissonsRatio")),
                "compressionTensionRatio": parse_float(point.get("compressionTensionRatio")),
                "specificHeat": parse_float(point.get("specificHeat")),
                "thermalConductivity": parse_float(point.get("thermalConductivity")),
            }
        )
    return sorted([point for point in points if point["temperatureK"] is not None], key=lambda item: item["temperatureK"])  # type: ignore[arg-type]


def interpolate_material_value(points: list[dict[str, float | None]], temperature: float | None, field: str) -> float | None:
    if temperature is None:
        return None
    values = [
        (point["temperatureK"], point[field])
        for point in points
        if point.get("temperatureK") is not None and point.get(field) is not None
    ]
    values.sort(key=lambda item: item[0])  # type: ignore[arg-type]
    if not values:
        return None
    if temperature <= values[0][0]:  # type: ignore[operator]
        return values[0][1]
    if temperature >= values[-1][0]:  # type: ignore[operator]
        return values[-1][1]
    for left, right in zip(values, values[1:]):
        t0, v0 = left
        t1, v1 = right
        if t0 <= temperature <= t1:  # type: ignore[operator]
            ratio = (temperature - t0) / max(t1 - t0, 1.0e-12)  # type: ignore[operator]
            return v0 + (v1 - v0) * ratio  # type: ignore[operator]
    return None


def scaled_log_fit(observed: list[float], base: list[float]) -> tuple[float | None, float | None]:
    pairs = [(obs, ref) for obs, ref in zip(observed, base) if obs and ref and obs > 0 and ref > 0]
    if not pairs:
        return None, None
    log_offsets = [math.log(obs) - math.log(ref) for obs, ref in pairs]
    mean = sum(log_offsets) / len(log_offsets)
    residual = sum((value - mean) ** 2 for value in log_offsets) / len(log_offsets)
    return math.exp(mean), residual


def log_residual(observed: list[float], base: list[float]) -> float | None:
    pairs = [(obs, ref) for obs, ref in zip(observed, base) if obs and ref and obs > 0 and ref > 0]
    if not pairs:
        return None
    return sum((math.log(obs) - math.log(ref)) ** 2 for obs, ref in pairs) / len(pairs)


def absolute_residual(observed: list[float], base: list[float], tolerance: float) -> float | None:
    pairs = [(obs, ref) for obs, ref in zip(observed, base) if obs is not None and ref is not None]
    if not pairs:
        return None
    return sum(min(abs(obs - ref) / tolerance, 8.0) ** 2 for obs, ref in pairs) / len(pairs)


def scale_penalty(multiplier: float | None) -> float:
    if multiplier is None or multiplier <= 0:
        return 3.0
    delta = abs(math.log(multiplier))
    if delta <= math.log(1.08):
        return 0.0
    return min(2.5, (delta - math.log(1.08)) * 0.45)


def summarize_groups(groups: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    bucket: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        item = group.get(key)
        if not item:
            continue
        bucket[(group["kind"], item["material"])].append(group)
    rows = []
    for (kind, material), items in sorted(bucket.items(), key=lambda pair: (pair[0][0], -len(pair[1]), pair[0][1])):
        e_values = [item[key].get("eMultiplier") for item in items if item.get(key) and item[key].get("eMultiplier") is not None]
        density_values = [item[key].get("densityMultiplier") for item in items if item.get(key) and item[key].get("densityMultiplier") is not None]
        scores = [item[key].get("score") for item in items if item.get(key) and item[key].get("score") is not None]
        global_probabilities = [item[key].get("globalProbability") for item in items if item.get(key) and item[key].get("globalProbability") is not None]
        categories = Counter(item[key].get("category", "") for item in items if item.get(key))
        rows.append(
            {
                "kind": kind,
                "material": material,
                "label": short_material_name(material),
                "category": categories.most_common(1)[0][0] if categories else "",
                "groupCount": len(items),
                "nodeMin": min(item["node"] for item in items),
                "nodeMax": max(item["node"] for item in items),
                "indices": sorted(set(item["index"] for item in items)),
                "scoreMean": average(scores),
                "eMultiplierMin": min(e_values) if e_values else None,
                "eMultiplierMax": max(e_values) if e_values else None,
                "densityMultiplierMin": min(density_values) if density_values else None,
                "densityMultiplierMax": max(density_values) if density_values else None,
                "globalProbabilityMin": min(global_probabilities) if global_probabilities else None,
                "globalProbabilityMax": max(global_probabilities) if global_probabilities else None,
                "globalOverrideCount": sum(1 for item in items if item.get(key) and item[key].get("globalOverride")),
            }
        )
    return rows


def compare_expected_and_recognized(used: list[dict[str, Any]], recognized_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected: dict[str, set[str]] = defaultdict(set)
    recognized: dict[str, set[str]] = defaultdict(set)
    for row in used:
        expected[row["kind"]].add(row["material"])
    for row in recognized_summary:
        recognized[row["kind"]].add(row["material"])
    rows = []
    for kind in ("TreadMaterial", "BulkMaterial", "PlyMaterial"):
        rows.append(
            {
                "kind": kind,
                "expected": sorted(expected[kind]),
                "recognized": sorted(recognized[kind]),
                "missing": sorted(expected[kind] - recognized[kind]),
                "extra": sorted(recognized[kind] - expected[kind]),
            }
        )
    return rows


def build_matrices(groups: list[dict[str, Any]], node_count: int, max_layer: int) -> dict[str, Any]:
    columns = KIND_COLUMNS + [f"L{index}" for index in range(1, max_layer + 1)]
    expected_by_cell = {}
    recognized_by_cell = {}
    for group in groups:
        column = group["column"]
        node = group["node"]
        expected_by_cell[(node, column)] = group.get("excel")
        recognized_by_cell[(node, column)] = group.get("best")
    return {
        "columns": columns,
        "expected": matrix_rows(expected_by_cell, columns, node_count),
        "recognized": matrix_rows(recognized_by_cell, columns, node_count),
    }


def matrix_rows(values: dict[tuple[int, str], dict[str, Any] | None], columns: list[str], node_count: int) -> list[dict[str, Any]]:
    rows = []
    for node in range(1, node_count + 1):
        cells = []
        for column in columns:
            item = values.get((node, column))
            cells.append(
                {
                    "column": column,
                    "label": short_material_name(item["material"]) if item else "",
                    "full": item["material"] if item else "",
                    "score": item.get("score") if item else None,
                    "eMultiplier": item.get("eMultiplier") if item else None,
                    "densityMultiplier": item.get("densityMultiplier") if item else None,
                    "globalProbability": item.get("globalProbability") if item else None,
                    "globalScopeLabel": item.get("globalScopeLabel") if item else "",
                    "globalOverride": bool(item.get("globalOverride")) if item else False,
                    "localMaterial": item.get("localMaterial") if item else "",
                }
            )
        rows.append({"node": node, "cells": cells})
    return rows


def kind_to_column(kind: str, index: int) -> str:
    if kind == "TreadMaterial":
        return "Tread"
    if kind == "BulkMaterial":
        return "Bulk"
    return f"L{index}"


def render_html(report: dict[str, Any]) -> str:
    palette = build_palette(report)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TGM Gen Materialvergleich</title>
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
    h2 {{ margin: 28px 0 10px; font-size: 18px; }}
    p {{ margin: 6px 0; color: var(--muted); }}
    code {{ color: #b9d8f2; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ color: #b9d8f2; font-weight: 700; background: #121c27; position: sticky; top: 0; }}
    .small {{ color: var(--muted); font-size: 12px; }}
    .matrix-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: start; }}
    .matrix {{ overflow: auto; max-height: 72vh; border: 1px solid var(--line); border-radius: 8px; background: #0f171f; }}
    .matrix table {{ min-width: 760px; table-layout: fixed; }}
    .matrix th, .matrix td {{ padding: 3px; text-align: center; border-bottom: 1px solid #1e2b38; border-right: 1px solid #1e2b38; }}
    .matrix th:first-child, .matrix td:first-child {{ width: 48px; color: var(--muted); background: #111922; position: sticky; left: 0; z-index: 2; }}
    .matrix th {{ z-index: 3; }}
    .cell {{
      display: block;
      min-height: 22px;
      border-radius: 4px;
      padding: 3px 4px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      color: #f6fbff;
      font-size: 11px;
      font-weight: 650;
      text-shadow: 0 1px 1px rgba(0,0,0,.45);
    }}
    .empty {{ opacity: .25; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 0; }}
    .chip {{ display: inline-flex; align-items: center; gap: 6px; color: #c9d7e3; }}
    .swatch {{ width: 11px; height: 11px; border-radius: 3px; display: inline-block; border: 1px solid rgba(255,255,255,.25); }}
    .note {{ border-left: 3px solid var(--accent); padding: 8px 10px; background: #0f1b26; color: #cdd9e4; }}
    .section-svg {{ width: 100%; height: auto; display: block; background: #0d151d; border: 1px solid var(--line); border-radius: 8px; }}
    .guide {{ fill: none; stroke: #6b7f94; stroke-width: 1.1; opacity: .55; }}
    .node-dot {{ stroke: rgba(255,255,255,.55); stroke-width: .45; }}
    .cross-note {{ margin-top: 8px; font-size: 12px; color: var(--muted); }}
    @media (max-width: 980px) {{ .grid, .matrix-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<header>
  <h1>TGM Gen Materialvergleich</h1>
  <p>Excel/ODS-Quelle gegen unsere Rückerkennung für <code>G_9.2-20.0-13x10_Soft_Slick_1975</code>.</p>
  <p>Quelle: <code>{escape(report["ods"])}</code></p>
</header>
<main>
  <section class="note">
    Links steht, was aus den Excel-/ODS-Selections und bekannten Generatorformeln kommt. Rechts steht, welches Einzelmaterial unser Recognizer aus den generierten TGM-Materialwerten ableitet. Ply, Cap/Tread und Filler werden zusätzlich mit einer globalen Dominanzwahrscheinlichkeit stabilisiert, damit einzelne lokale Ausreißer nicht als Materialwechsel erscheinen.
  </section>

  <h2>Querschnitt-Materialbelegung</h2>
  <div class="matrix-grid">
    <section class="panel">
      <h2>Excel / ODS</h2>
      {render_cross_section_svg(report["geometry"], report["matrices"]["expected"], report["matrices"]["columns"], palette)}
    </section>
    <section class="panel">
      <h2>Unsere Erkennung</h2>
      {render_cross_section_svg(report["geometry"], report["matrices"]["recognized"], report["matrices"]["columns"], palette)}
    </section>
  </div>

  <h2>Node-Matrix</h2>
  <div class="matrix-grid">
    <section class="panel">
      <h2>Excel / ODS</h2>
      <p>Materialquelle bzw. Generatorrolle pro Node und Stack-Position.</p>
      {render_matrix(report["matrices"]["expected"], report["matrices"]["columns"], palette)}
    </section>
    <section class="panel">
      <h2>Unsere Erkennung</h2>
      <p>Global stabilisierter Einzelmaterialtreffer aus den TGM-Materialwerten.</p>
      {render_matrix(report["matrices"]["recognized"], report["matrices"]["columns"], palette)}
    </section>
  </div>

  <h2>Excel-Auswahl</h2>
  <section class="panel">{render_used_table(report["used"])}</section>

  <h2>Globale Material-Wahrscheinlichkeit</h2>
  <section class="panel">{render_global_probability_table(report["global_probabilities"])}</section>

  <div class="grid">
    <section class="panel">
      <h2>Excel-Zusammenfassung</h2>
      {render_summary_table(report["excel_summary"], include_scores=False)}
    </section>
    <section class="panel">
      <h2>Erkennungs-Zusammenfassung</h2>
      {render_summary_table(report["recognized_summary"], include_scores=True)}
    </section>
  </div>

  <h2>Abweichungen</h2>
  <section class="panel">{render_difference_table(report["differences"])}</section>

  {render_legend(palette)}
</main>
</body>
</html>
"""


def render_cross_section_svg(
    geometry: dict[int, tuple[float, float, float]],
    rows: list[dict[str, Any]],
    columns: list[str],
    palette: dict[str, str],
) -> str:
    if not geometry:
        return '<p class="small">Keine Geometry-Einträge im TGM gefunden.</p>'

    width = 680
    height = 360
    margin = 34
    points = sorted((node, values[1], values[0]) for node, values in geometry.items())
    lateral_values = [point[1] for point in points]
    radial_values = [point[2] for point in points]
    lateral_mid = (min(lateral_values) + max(lateral_values)) / 2
    radial_mid = (min(radial_values) + max(radial_values)) / 2
    lateral_span = max(max(lateral_values) - min(lateral_values), 1.0e-9)
    radial_span = max(max(radial_values) - min(radial_values), 1.0e-9)
    scale = min((width - 2 * margin) / lateral_span, (height - 2 * margin) / radial_span)

    def map_point(node: int) -> tuple[float, float]:
        radial, lateral, _thickness = geometry[node]
        x = width / 2 + (lateral - lateral_mid) * scale
        y = height / 2 - (radial - radial_mid) * scale
        return x, y

    base_by_node = {node: map_point(node) for node, _lateral, _radial in points}
    center = (width / 2, height / 2)
    column_offsets = {"Tread": 13.0, "Bulk": 0.0}
    for layer_index, column in enumerate([column for column in columns if column.startswith("L")], start=1):
        column_offsets[column] = -6.0 - layer_index * 4.2

    cell_by_node_column: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        node = row["node"]
        for cell in row["cells"]:
            if cell["full"]:
                cell_by_node_column[(node, cell["column"])] = cell

    guide_parts = []
    for idx, (node, _lateral, _radial) in enumerate(points):
        x, y = base_by_node[node]
        command = "M" if idx == 0 else "L"
        guide_parts.append(f"{command} {x:.1f} {y:.1f}")
    guide_path = " ".join(guide_parts)
    circles: list[str] = []
    for column in columns:
        offset = column_offsets.get(column, 0.0)
        radius = 3.3 if column in {"Tread", "Bulk"} else 2.45
        for node, _lateral, _radial in points:
            cell = cell_by_node_column.get((node, column))
            if not cell:
                continue
            base_x, base_y = base_by_node[node]
            outward_x = base_x - center[0]
            outward_y = base_y - center[1]
            length = math.hypot(outward_x, outward_y) or 1.0
            x = base_x + offset * outward_x / length
            y = base_y + offset * outward_y / length
            title = f"N{node} {column}: {cell['full']}"
            color = palette.get(cell["full"], "#526375")
            circles.append(
                f'<circle class="node-dot" cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}"><title>{escape(title)}</title></circle>'
            )

    return (
        f'<svg class="section-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Materialbelegung im Reifenquerschnitt">'
        f'<path class="guide" d="{guide_path}"/>'
        f'{"".join(circles)}'
        "</svg>"
        '<p class="cross-note">Punkte folgen der TGM-Node-Geometrie: Tread außen, Bulk auf der Kontur, Ply-Lagen leicht nach innen versetzt. Tooltips zeigen Node, Lage und Material.</p>'
    )


def render_matrix(rows: list[dict[str, Any]], columns: list[str], palette: dict[str, str]) -> str:
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = []
        for cell in row["cells"]:
            label = cell["label"]
            if not label:
                cells.append('<td><span class="cell empty"></span></td>')
                continue
            color = palette.get(cell["full"], "#526375")
            title_parts = [cell["full"]]
            if cell.get("score") is not None:
                title_parts.append(f"score {fmt(cell['score'])}")
            if cell.get("eMultiplier") is not None:
                title_parts.append(f"E x{fmt(cell['eMultiplier'])}")
            if cell.get("densityMultiplier") is not None:
                title_parts.append(f"rho x{fmt(cell['densityMultiplier'])}")
            if cell.get("globalProbability") is not None:
                scope = f" {cell['globalScopeLabel']}" if cell.get("globalScopeLabel") else ""
                title_parts.append(f"global{scope} {fmt_percent(cell['globalProbability'])}")
            if cell.get("globalOverride"):
                title_parts.append(f"local {cell.get('localMaterial', '')}")
            cells.append(
                f'<td><span class="cell" style="background:{color}" title="{escape(" | ".join(title_parts))}">{escape(label)}</span></td>'
            )
        body.append(f"<tr><td>N{row['node']}</td>{''.join(cells)}</tr>")
    return f'<div class="matrix"><table><thead><tr><th>Node</th>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def render_used_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{escape(row['role'])}</td><td>{escape(row['kind'])}</td><td>{escape(row['material'])}</td><td>{fmt(row['eMultiplier'])}</td><td>{fmt(row['densityMultiplier'])}</td></tr>"
        for row in rows
    )
    return f"<table><thead><tr><th>Rolle</th><th>TGM-Art</th><th>Excel-Material</th><th>E-Mult.</th><th>Dichte-Mult.</th></tr></thead><tbody>{body}</tbody></table>"


def render_global_probability_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        "<tr>"
        f"<td>{escape(row['kind'])}</td>"
        f"<td>{escape(row['scopeLabel'])}</td>"
        f"<td>{escape(row['material'])}</td>"
        f"<td>{row['localWinnerCount']}</td>"
        f"<td>{row['total']}</td>"
        f"<td>{fmt_percent(row['probability'])}</td>"
        f"<td>{fmt_percent(row.get('secondProbability'))}</td>"
        f"<td>{fmt_percent(row.get('leadProbability'))}</td>"
        f"<td>{'ja' if row.get('dominant') else ''}</td>"
        f"<td>{'ja' if row.get('stabilized') else ''}</td>"
        "</tr>"
        for row in rows
    )
    return f"<table><thead><tr><th>TGM-Art</th><th>Scope</th><th>Lokaler Gewinner</th><th>Gruppen</th><th>Gesamt</th><th>Global</th><th>Zweiter</th><th>Abstand</th><th>Dominant</th><th>Korrektur aktiv</th></tr></thead><tbody>{body}</tbody></table>"


def render_summary_table(rows: list[dict[str, Any]], include_scores: bool) -> str:
    score_header = "<th>Score</th>" if include_scores else ""
    global_header = "<th>Global</th><th>Korrektur</th>" if include_scores else ""
    body = []
    for row in rows:
        score_cell = f"<td>{fmt(row.get('scoreMean'))}</td>" if include_scores else ""
        global_cell = (
            f"<td>{mult_range_percent(row.get('globalProbabilityMin'), row.get('globalProbabilityMax'))}</td>"
            f"<td>{row.get('globalOverrideCount', 0)}</td>"
            if include_scores
            else ""
        )
        body.append(
            "<tr>"
            f"<td>{escape(row['kind'])}</td>"
            f"<td>{escape(row['material'])}</td>"
            f"<td>{row['groupCount']}</td>"
            f"<td>{row['nodeMin']}-{row['nodeMax']}</td>"
            f"<td>{escape(', '.join(str(index) for index in row['indices']))}</td>"
            f"<td>{mult_range(row.get('eMultiplierMin'), row.get('eMultiplierMax'))}</td>"
            f"<td>{mult_range(row.get('densityMultiplierMin'), row.get('densityMultiplierMax'))}</td>"
            f"{score_cell}{global_cell}</tr>"
        )
    return f"<table><thead><tr><th>TGM-Art</th><th>Material</th><th>Gruppen</th><th>Nodes</th><th>Index/Lage</th><th>E-Mult.</th><th>Dichte-Mult.</th>{score_header}{global_header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_difference_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        "<tr>"
        f"<td>{escape(row['kind'])}</td>"
        f"<td>{escape('; '.join(row['expected']))}</td>"
        f"<td>{escape('; '.join(row['recognized']))}</td>"
        f"<td>{escape('; '.join(row['missing']) or '-')}</td>"
        f"<td>{escape('; '.join(row['extra']) or '-')}</td>"
        "</tr>"
        for row in rows
    )
    return f"<table><thead><tr><th>TGM-Art</th><th>Excel-Materialien</th><th>Erkannt</th><th>Fehlt erkannt</th><th>Zusätzlich erkannt</th></tr></thead><tbody>{body}</tbody></table>"


def render_legend(palette: dict[str, str]) -> str:
    chips = "".join(
        f'<span class="chip"><span class="swatch" style="background:{color}"></span>{escape(short_material_name(name))}</span>'
        for name, color in sorted(palette.items())
    )
    return f'<h2>Legende</h2><section class="panel"><div class="legend">{chips}</div></section>'


def build_palette(report: dict[str, Any]) -> dict[str, str]:
    names = set()
    for side in ("expected", "recognized"):
        for row in report["matrices"][side]:
            for cell in row["cells"]:
                if cell["full"]:
                    names.add(cell["full"])
    colors = [
        "#3b82f6", "#a855f7", "#ef4444", "#f97316", "#22c55e", "#14b8a6",
        "#eab308", "#ec4899", "#64748b", "#06b6d4", "#84cc16", "#f43f5e",
        "#8b5cf6", "#10b981", "#fb7185", "#38bdf8", "#f59e0b", "#94a3b8",
    ]
    return {name: colors[index % len(colors)] for index, name in enumerate(sorted(names))}


def short_material_name(name: str) -> str:
    text = str(name or "")
    replacements = [
        ("Race – ", ""),
        ("Race - ", ""),
        ("G – FI 1975 ", "G "),
        ("G - FI 1975 ", "G "),
        ("Steel – 0.8% Carbon Steel", "0.8%C Steel"),
        ("Steel - 0.8% Carbon Steel", "0.8%C Steel"),
        ("Nylon – ", "Nylon "),
        ("Nylon - ", "Nylon "),
        ("Formula ", ""),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text if len(text) <= 18 else text[:17] + "."


def number_or_text(value: str) -> float | str:
    parsed = parse_float(value)
    return parsed if parsed is not None else value


def parse_float(value: Any) -> float | None:
    try:
        if value == "":
            return None
        parsed = float(str(value).replace(",", "."))
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def average(values: list[float | None]) -> float | None:
    finite = [value for value in values if value is not None and math.isfinite(value)]
    return sum(finite) / len(finite) if finite else None


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(value):
        return "-"
    if value == 0:
        return "0"
    if abs(value) < 0.001 or abs(value) >= 1.0e5:
        return f"{value:.3g}"
    return f"{value:.3f}".rstrip("0").rstrip(".")


def mult_range(left: Any, right: Any) -> str:
    if left is None and right is None:
        return "-"
    if right is None or left == right:
        return fmt(left)
    return f"{fmt(left)}..{fmt(right)}"


def fmt_percent(value: Any) -> str:
    parsed = parse_float(value)
    if parsed is None:
        return "-"
    return f"{parsed * 100:.0f}%"


def mult_range_percent(left: Any, right: Any) -> str:
    if left is None and right is None:
        return "-"
    if right is None or left == right:
        return fmt_percent(left)
    return f"{fmt_percent(left)}..{fmt_percent(right)}"


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
