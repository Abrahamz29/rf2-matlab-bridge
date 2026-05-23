"""Regression test for the TGM Gen ODS replacement.

The acceptance target is strict text parity against the official Studio-397
ODS export, with only LookupV2/PatchV1 excluded from the TGM comparison.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


DEFAULT_ODS = Path("tyres/downloads/studio397/TGM Gen V0.33 - GY F1 1975 Front.ods")
DEFAULT_OUT_DIR = Path("tmp/tgm_gen_acceptance_test")


def load_tgm_module():
    script_path = Path(__file__).with_name("tgm_gen_ods.py")
    spec = importlib.util.spec_from_file_location("tgm_gen_ods", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["tgm_gen_ods"] = module
    spec.loader.exec_module(module)
    return module


def run_acceptance(ods: Path, out_dir: Path, mode: str) -> dict:
    tgm = load_tgm_module()
    if not ods.exists():
        raise FileNotFoundError(f"ODS not found: {ods}")

    reference = tgm.export_reference(ods, out_dir)
    generated = tgm.generate_exports(ods, out_dir, mode=mode, fallback_on_error=False)
    tgm_compare = tgm.compare_files(out_dir / "reference_from_ods.tgm", out_dir / "generated.tgm", strip_lookup=True)
    tbc_compare = tgm.compare_files(out_dir / "reference_from_ods.tbc", out_dir / "generated.tbc", strip_lookup=False)

    project_path = out_dir / "inputs.json"
    project_out_dir = out_dir / "project_roundtrip"
    project_inputs = tgm.extract_input_model(ods, out_path=project_path)
    editable_inputs = tgm.extract_input_model(ods, out_path=out_dir / "inputs_editable.json", editable_only=True)
    project_generated = tgm.generate_exports(
        ods,
        project_out_dir,
        mode=mode,
        fallback_on_error=False,
        project_path=project_path,
    )
    project_tgm_compare = tgm.compare_files(out_dir / "reference_from_ods.tgm", project_out_dir / "generated.tgm", strip_lookup=True)
    project_tbc_compare = tgm.compare_files(out_dir / "reference_from_ods.tbc", project_out_dir / "generated.tbc", strip_lookup=False)
    report = tgm.formula_report(
        ods,
        [
            "About",
            "General",
            "Geometry",
            "Construction",
            "TGM",
            "Compound",
            "Realtime",
            "WLF",
            "ContactProps",
            "LoadSens",
            "Export",
            "TBC",
            "Materials",
        ],
        mode=mode,
        fallback_on_error=False,
        sample_limit=3,
    )
    chart_report = tgm.inspect_charts(ods)
    chart_data = tgm.inspect_chart_data(ods, mode=mode, fallback_on_error=False)
    material_library = tgm.extract_material_library(ods)
    chart_series_with_values = sum(
        1
        for chart in chart_data["charts"]
        for series in chart["series"]
        if series["valuesData"]["values"]
    )
    chart_numeric_points = sum(
        1
        for chart in chart_data["charts"]
        for series in chart["series"]
        for value in series["valuesData"]["values"]
        if value["isNumeric"]
    )

    return {
        "ods": str(ods),
        "out_dir": str(out_dir),
        "mode": mode,
        "reference": reference["exports"],
        "generated": generated["outputs"],
        "project_roundtrip": {
            "inputs": {
                "path": str(project_path),
                "input_count": project_inputs["input_count"],
                "sheet_counts": project_inputs["sheet_counts"],
                "editable_confidence_counts": project_inputs["editable_confidence_counts"],
            },
            "editable_inputs": {
                "path": str(out_dir / "inputs_editable.json"),
                "input_count": editable_inputs["input_count"],
                "editable_confidence_counts": editable_inputs["editable_confidence_counts"],
            },
            "generated": project_generated["outputs"],
            "override_count": project_generated["override_count"],
            "tgm": project_tgm_compare,
            "tbc": project_tbc_compare,
            "passed": bool(project_tgm_compare["equal"] and project_tbc_compare["equal"]),
        },
        "formula_count": report["formula_count"],
        "evaluated_count": report["evaluated_count"],
        "error_count": report["error_count"],
        "fallback_count": report["fallback_count"],
        "charts": {
            "chart_count": chart_report["chart_count"],
            "series_count": chart_report["series_count"],
            "evaluated_series_count": chart_series_with_values,
            "numeric_point_count": chart_numeric_points,
            "fallback_count": chart_data["fallback_count"],
            "passed": bool(
                chart_report["chart_count"] == 12
                and chart_report["series_count"] == 79
                and chart_series_with_values == chart_report["series_count"]
                and chart_numeric_points > 0
                and chart_data["fallback_count"] == 0
            ),
        },
        "material_library": {
            "material_count": material_library["material_count"],
            "point_count": material_library["point_count"],
            "category_counts": material_library["category_counts"],
            "passed": bool(material_library["material_count"] >= 100 and material_library["point_count"] >= 300),
        },
        "tgm": tgm_compare,
        "tbc": tbc_compare,
        "passed": bool(
            tgm_compare["equal"]
            and tbc_compare["equal"]
            and project_tgm_compare["equal"]
            and project_tbc_compare["equal"]
            and report["error_count"] == 0
            and report["fallback_count"] == 0
            and chart_report["chart_count"] == 12
            and chart_report["series_count"] == 79
            and chart_series_with_values == chart_report["series_count"]
            and chart_numeric_points > 0
            and chart_data["fallback_count"] == 0
            and material_library["material_count"] >= 100
            and material_library["point_count"] >= 300
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--mode", choices=["recursive", "cached"], default="recursive")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_acceptance(args.ods, args.out_dir, args.mode)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"mode: {report['mode']}")
        print(f"formulas: {report['evaluated_count']}/{report['formula_count']}")
        print(f"errors: {report['error_count']}")
        print(f"fallback: {report['fallback_count']}")
        print(f"charts: {report['charts']['evaluated_series_count']}/{report['charts']['series_count']}")
        print(f"materials: {report['material_library']['material_count']} / {report['material_library']['point_count']} points")
        print(f"tgm_equal_without_lookup_patch: {report['tgm']['equal']}")
        print(f"tbc_equal: {report['tbc']['equal']}")
        print(f"project_roundtrip: {report['project_roundtrip']['passed']}")
        print(f"passed: {report['passed']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

