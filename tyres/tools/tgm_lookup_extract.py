#!/usr/bin/env python3
"""Extract rFactor 2 TGM lookup payloads into inspectable files.

This handles both legacy [LookupData] Bin= hex payloads and newer [LookupV2]
P= payloads. LookupV2 and PatchV1 use a custom base85 alphabet containing all
characters from "*" through "~"; each five encoded characters represent one
big-endian 32-bit word.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import struct
from pathlib import Path
from typing import Iterable


STAR85_BASE = ord("*")
STAR85_RADIX = 85


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tgm", type=Path, help="Path to a .tgm file")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory. Defaults to tyres/output/lookup/<tgm-stem>",
    )
    parser.add_argument(
        "--include-patch",
        action="store_true",
        help="Also export PatchV1 R/D word views. D can be large.",
    )
    args = parser.parse_args()

    tgm_path = args.tgm.resolve()
    if not tgm_path.is_file():
        raise SystemExit(f"TGM file not found: {tgm_path}")

    out_dir = args.out
    if out_dir is None:
        out_dir = Path("tyres") / "output" / "lookup" / sanitize_name(tgm_path.stem)
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    text = tgm_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(text)
    qsa_axes = parse_qsa_axes(sections.get("QuasiStaticAnalysis", []))

    summary: dict[str, object] = {
        "source_path": str(tgm_path),
        "source_sha256": hashlib.sha256(tgm_path.read_bytes()).hexdigest(),
        "output_dir": str(out_dir),
        "qsa_axes": qsa_axes,
        "qsa_grid_size": grid_size(qsa_axes),
        "qsa_record_order_assumption": "GaugePressure -> CarcassTemperature -> RotationSquared; raw word_index is authoritative",
        "lookup": None,
        "patch": None,
    }

    lookup_info = export_lookup(tgm_path, out_dir, sections, qsa_axes)
    summary["lookup"] = lookup_info

    patch_info = summarize_patch(out_dir, sections, include_words=args.include_patch)
    summary["patch"] = patch_info

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {summary_path}")
    if lookup_info:
        print(
            "Lookup:",
            lookup_info["format"],
            f"{lookup_info['decoded_bytes']} bytes",
            f"{lookup_info['float32_word_count']} words",
        )
    if patch_info:
        print("PatchV1:", patch_info)
    return 0


def parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            current = line[1 : line.index("]")]
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(raw_line.rstrip("\n"))
    return sections


def parse_qsa_axes(lines: list[str]) -> dict[str, list[float]]:
    axes: dict[str, list[float]] = {
        "GaugePressure": [],
        "CarcassTemperature": [],
        "RotationSquared": [],
    }
    for line in lines:
        key, value = split_assignment(line)
        if key in axes:
            axes[key].append(parse_scalar_number(value))
    return axes


def split_assignment(line: str) -> tuple[str | None, str]:
    if "=" not in line:
        return None, ""
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if key not in {"P", "R", "D", "Bin"}:
        value = value.split("//", 1)[0].strip()
    return key, value


def parse_scalar_number(text: str) -> float:
    text = text.strip().replace(",", ".")
    return float(text)


def grid_size(qsa_axes: dict[str, list[float]]) -> int:
    total = 1
    for key in ("GaugePressure", "CarcassTemperature", "RotationSquared"):
        total *= max(1, len(qsa_axes.get(key, [])))
    return total


def export_lookup(
    tgm_path: Path,
    out_dir: Path,
    sections: dict[str, list[str]],
    qsa_axes: dict[str, list[float]],
) -> dict[str, object] | None:
    if "LookupV2" in sections:
        info = decode_lookup_v2(sections["LookupV2"])
    elif "LookupData" in sections:
        info = decode_lookup_data(sections["LookupData"])
    else:
        return {
            "format": "missing",
            "note": "No [LookupV2] or [LookupData] section found.",
        }

    payload = info.pop("payload")
    payload_path = out_dir / "lookup_payload.bin"
    payload_path.write_bytes(payload)

    words = decode_word_views(payload)
    words_path = out_dir / "lookup_words.csv"
    write_words_csv(words_path, words, qsa_axes)

    matrix_path = out_dir / "lookup_matrix_float32_be.csv"
    write_matrix_csv(matrix_path, words, qsa_axes)

    info.update(
        {
            "decoded_bytes": len(payload),
            "float32_word_count": len(words),
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "payload_bin": str(payload_path),
            "words_csv": str(words_path),
            "matrix_csv": str(matrix_path),
            "source_file": str(tgm_path),
            "bytes_per_qsa_point": safe_div(len(payload), grid_size(qsa_axes)),
            "float32_words_per_qsa_point": safe_div(len(words), grid_size(qsa_axes)),
            "sample_float32_be": [finite_or_none(row["float32_be"]) for row in words[:16]],
        }
    )
    return info


def decode_lookup_v2(lines: list[str]) -> dict[str, object]:
    version = None
    checksum = None
    chunks: list[str] = []
    for line in lines:
        key, value = split_assignment(line)
        if key == "Version":
            version = value
        elif key == "Checksum":
            checksum = parse_int(value)
        elif key == "P":
            chunks.append(value)
    encoded = "".join(chunks)
    return {
        "format": "LookupV2",
        "version": version,
        "checksum": checksum,
        "encoded_chunks": len(chunks),
        "encoded_chars": len(encoded),
        "encoding": "star85 (*..~), 5 chars -> one big-endian 32-bit word",
        "payload": decode_star85(encoded),
    }


def decode_lookup_data(lines: list[str]) -> dict[str, object]:
    version = None
    checksum = None
    chunks: list[str] = []
    for line in lines:
        key, value = split_assignment(line)
        if key == "Version":
            version = value
        elif key == "Checksum":
            checksum = parse_int(value)
        elif key == "Bin":
            chunks.append(re.sub(r"\s+", "", value))
    encoded = "".join(chunks)
    return {
        "format": "LookupData",
        "version": version,
        "checksum": checksum,
        "encoded_chunks": len(chunks),
        "encoded_chars": len(encoded),
        "encoding": "hex Bin payload",
        "payload": bytes.fromhex(encoded),
    }


def summarize_patch(
    out_dir: Path,
    sections: dict[str, list[str]],
    include_words: bool,
) -> dict[str, object] | None:
    if "PatchV1" not in sections:
        return None

    lines = sections["PatchV1"]
    version = None
    deflection_step_size = None
    chunks: dict[str, list[str]] = {"R": [], "D": []}
    for line in lines:
        key, value = split_assignment(line)
        if key == "Version":
            version = value
        elif key == "DeflectionStepSize":
            deflection_step_size = parse_scalar_number(value)
        elif key in chunks:
            chunks[key].append(value)

    out: dict[str, object] = {
        "format": "PatchV1",
        "version": version,
        "deflection_step_size": deflection_step_size,
        "encoding": "star85 (*..~), 5 chars -> one big-endian 32-bit word",
        "streams": {},
    }

    streams = out["streams"]
    assert isinstance(streams, dict)
    for key in ("R", "D"):
        encoded = "".join(chunks[key])
        if not encoded:
            continue
        payload = decode_star85(encoded)
        payload_path = out_dir / f"patch_{key.lower()}_payload.bin"
        payload_path.write_bytes(payload)
        stream_info: dict[str, object] = {
            "encoded_chunks": len(chunks[key]),
            "encoded_chars": len(encoded),
            "decoded_bytes": len(payload),
            "float32_word_count": len(payload) // 4,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "payload_bin": str(payload_path),
        }
        if include_words:
            words = decode_word_views(payload)
            words_path = out_dir / f"patch_{key.lower()}_words.csv"
            write_words_csv(words_path, words, {})
            stream_info["words_csv"] = str(words_path)
        streams[key] = stream_info

    return out


def parse_int(text: str) -> int:
    return int(float(text.strip().replace(",", ".")))


def decode_star85(encoded: str) -> bytes:
    if len(encoded) % 5 != 0:
        raise ValueError(f"star85 payload length must be a multiple of 5, got {len(encoded)}")

    out = bytearray()
    for offset in range(0, len(encoded), 5):
        value = 0
        group = encoded[offset : offset + 5]
        for char in group:
            digit = ord(char) - STAR85_BASE
            if digit < 0 or digit >= STAR85_RADIX:
                raise ValueError(f"invalid star85 char {char!r} at encoded offset {offset}")
            value = value * STAR85_RADIX + digit
        if value > 0xFFFFFFFF:
            raise ValueError(f"star85 group overflows 32 bits at encoded offset {offset}")
        out.extend(value.to_bytes(4, "big"))
    return bytes(out)


def decode_word_views(payload: bytes) -> list[dict[str, object]]:
    words: list[dict[str, object]] = []
    for word_index, offset in enumerate(range(0, len(payload) - len(payload) % 4, 4)):
        chunk = payload[offset : offset + 4]
        float32_be = struct.unpack(">f", chunk)[0]
        float32_le = struct.unpack("<f", chunk)[0]
        uint32_be = struct.unpack(">I", chunk)[0]
        int32_be = struct.unpack(">i", chunk)[0]
        words.append(
            {
                "word_index": word_index,
                "byte_offset": offset,
                "hex": chunk.hex(),
                "uint32_be": uint32_be,
                "int32_be": int32_be,
                "float32_be": float32_be,
                "float32_le": float32_le,
            }
        )
    return words


def qsa_record_axes(qsa_axes: dict[str, list[float]]) -> list[tuple[int, float | None, float | None, float | None]]:
    pressures = qsa_axes.get("GaugePressure") or [None]
    temps = qsa_axes.get("CarcassTemperature") or [None]
    rotations = qsa_axes.get("RotationSquared") or [None]
    records = []
    for record_index, (pressure, temp, rotation) in enumerate(
        itertools.product(pressures, temps, rotations)
    ):
        records.append((record_index, pressure, temp, rotation))
    return records


def write_words_csv(
    path: Path,
    words: list[dict[str, object]],
    qsa_axes: dict[str, list[float]],
) -> None:
    records = qsa_record_axes(qsa_axes)
    words_per_record = safe_div(len(words), len(records)) if records else None
    fieldnames = [
        "word_index",
        "byte_offset",
        "record_index",
        "value_index",
        "gauge_pressure_pa",
        "carcass_temperature_k",
        "rotation_squared",
        "hex",
        "uint32_be",
        "int32_be",
        "float32_be",
        "float32_le",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in words:
            record_index = None
            value_index = None
            pressure = None
            temp = None
            rotation = None
            if words_per_record and float(words_per_record).is_integer():
                per_record = int(words_per_record)
                record_index = int(row["word_index"]) // per_record
                value_index = int(row["word_index"]) % per_record
                if record_index < len(records):
                    _, pressure, temp, rotation = records[record_index]

            writer.writerow(
                {
                    **row,
                    "record_index": record_index,
                    "value_index": value_index,
                    "gauge_pressure_pa": pressure,
                    "carcass_temperature_k": temp,
                    "rotation_squared": rotation,
                    "float32_be": format_float(row["float32_be"]),
                    "float32_le": format_float(row["float32_le"]),
                }
            )


def write_matrix_csv(
    path: Path,
    words: list[dict[str, object]],
    qsa_axes: dict[str, list[float]],
) -> None:
    records = qsa_record_axes(qsa_axes)
    if not records:
        return
    words_per_record = safe_div(len(words), len(records))
    if not words_per_record or not float(words_per_record).is_integer():
        return
    per_record = int(words_per_record)
    fieldnames = [
        "record_index",
        "gauge_pressure_pa",
        "carcass_temperature_k",
        "rotation_squared",
    ] + [f"value_{index:04d}" for index in range(per_record)]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record_index, pressure, temp, rotation in records:
            start = record_index * per_record
            values = {
                f"value_{index:04d}": format_float(words[start + index]["float32_be"])
                for index in range(per_record)
            }
            writer.writerow(
                {
                    "record_index": record_index,
                    "gauge_pressure_pa": pressure,
                    "carcass_temperature_k": temp,
                    "rotation_squared": rotation,
                    **values,
                }
            )


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def finite_or_none(value: object) -> float | None:
    number = float(value)
    if math.isfinite(number):
        return number
    return None


def format_float(value: object) -> str:
    number = float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "inf" if number > 0 else "-inf"
    return f"{number:.9g}"


def sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return sanitized or "tgm_lookup"


if __name__ == "__main__":
    raise SystemExit(main())
