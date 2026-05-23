"""Extract Studio-397 tTool realtime batch INI blocks from the official ODS."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


OFFICE_STRING_VALUE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}string-value"
DEFAULT_ODS = Path("tyres/downloads/studio397/Realtime tTool Batch Tester V0.20 - Brabham BT44B Rears.ods")


def iter_realtime_blocks(ods_path: Path):
    with zipfile.ZipFile(ods_path) as ods_file:
        root = ElementTree.fromstring(ods_file.read("content.xml"))

    for element in root.iter():
        value = element.attrib.get(OFFICE_STRING_VALUE)
        if value and "[CustomRealtimeTest]" in value:
            lines = [line for line in value.splitlines() if line.strip()]
            if not lines:
                continue
            first_line = lines[0]
            if not first_line.startswith("//"):
                continue
            match = re.search(r"\[\s*([^\]]+?)\s*\]", first_line)
            if not match:
                continue
            yield {
                "suite": match.group(1),
                "first_line": first_line,
                "test_count": value.count("[CustomRealtimeTest]"),
                "length": len(value),
                "content": value.strip() + "\r\n",
            }


def select_block(ods_path: Path, suite: str):
    suite_key = suite.casefold()
    matches = [
        block
        for block in iter_realtime_blocks(ods_path)
        if block["suite"].casefold() == suite_key
    ]

    if not matches:
        available = sorted({block["suite"] for block in iter_realtime_blocks(ods_path)})
        raise SystemExit(
            f"Suite not found: {suite}\nAvailable suites:\n"
            + "\n".join(f"  - {item}" for item in available)
        )

    return max(matches, key=lambda block: (block["test_count"], block["length"]))


def parse_args(argv: list[str]):
    parser = argparse.ArgumentParser(
        description="Extract a complete [CustomRealtimeTest] suite from the official Studio-397 ODS."
    )
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS, help="Path to the official Studio-397 ODS.")
    parser.add_argument(
        "--suite",
        default="0_Initial-Tests",
        help="ODS test suite label, for example 0_Initial-Tests or 1_Deflection-Tests.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output custom_realtime.ini path.")
    parser.add_argument("--list", action="store_true", help="List available suites and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ods_path = args.ods

    if not ods_path.exists():
        raise SystemExit(f"ODS not found: {ods_path}")

    if args.list:
        for suite in sorted({block["suite"] for block in iter_realtime_blocks(ods_path)}):
            print(suite)
        return 0

    block = select_block(ods_path, args.suite)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(block["content"], encoding="utf-8", newline="")

    print(f"Wrote {args.output}")
    print(f"Suite: {block['suite']}")
    print(f"Tests: {block['test_count']}")
    print(block["first_line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

