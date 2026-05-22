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


DEFAULT_ODS = Path("tools/downloads/studio397/TGM Gen V0.33 - GY F1 1975 Front.ods")
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

    return {
        "ods": str(ods),
        "out_dir": str(out_dir),
        "mode": mode,
        "reference": reference["exports"],
        "generated": generated["outputs"],
        "formula_count": report["formula_count"],
        "evaluated_count": report["evaluated_count"],
        "error_count": report["error_count"],
        "fallback_count": report["fallback_count"],
        "tgm": tgm_compare,
        "tbc": tbc_compare,
        "passed": bool(tgm_compare["equal"] and tbc_compare["equal"] and report["error_count"] == 0 and report["fallback_count"] == 0),
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
        print(f"tgm_equal_without_lookup_patch: {report['tgm']['equal']}")
        print(f"tbc_equal: {report['tbc']['equal']}")
        print(f"passed: {report['passed']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
