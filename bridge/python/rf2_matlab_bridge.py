"""rFactor 2 shared-memory bridge for MATLAB.

The bridge reads TheIronWolfModding rF2SharedMemoryMapPlugin buffers with the
ctypes structure definitions vendored in ``vendor/pyRfactor2SharedMemory`` and
returns JSON-friendly dictionaries for MATLAB's ``jsondecode``.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENDOR_PYRF2 = PROJECT_ROOT / "vendor" / "pyRfactor2SharedMemory"
if str(VENDOR_PYRF2) not in sys.path:
    sys.path.insert(0, str(VENDOR_PYRF2))

try:
    import rF2data  # type: ignore
except ImportError as exc:  # pragma: no cover - hard failure for misconfigured repo
    raise RuntimeError(f"Cannot import vendored rF2data.py from {VENDOR_PYRF2}") from exc


FILE_MAP_READ = 0x0004
MAX_READ_RETRIES = 10
TEXT_FIELD_TOKENS = (
    "name",
    "message",
    "string",
    "version",
    "class",
    "group",
    "path",
    "vehicle",
    "driver",
    "track",
    "category",
    "control",
)


class SharedMemoryUnavailable(RuntimeError):
    """Raised when an rF2 shared-memory map is not present."""


@dataclass(frozen=True)
class BufferSpec:
    key: str
    map_name: str
    struct_type: Any
    refresh_hz: Optional[float]

    @property
    def size(self) -> int:
        return ctypes.sizeof(self.struct_type)


def output_buffer_specs() -> List[BufferSpec]:
    return [
        BufferSpec("telemetry", "$rFactor2SMMP_Telemetry$", rF2data.rF2Telemetry, 50.0),
        BufferSpec("scoring", "$rFactor2SMMP_Scoring$", rF2data.rF2Scoring, 5.0),
        BufferSpec("rules", "$rFactor2SMMP_Rules$", rF2data.rF2Rules, 3.0),
        BufferSpec("forceFeedback", "$rFactor2SMMP_ForceFeedback$", rF2data.rF2ForceFeedback, 400.0),
        BufferSpec("graphics", "$rFactor2SMMP_Graphics$", rF2data.rF2Graphics, 400.0),
        BufferSpec("pitInfo", "$rFactor2SMMP_PitInfo$", rF2data.rF2PitInfo, 100.0),
        BufferSpec("weather", "$rFactor2SMMP_Weather$", rF2data.rF2Weather, 1.0),
        BufferSpec("extended", "$rFactor2SMMP_Extended$", rF2data.rF2Extended, 5.0),
    ]


if os.name == "nt":
    import ctypes.wintypes as wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.OpenFileMappingW.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    _kernel32.OpenFileMappingW.restype = wintypes.HANDLE
    _kernel32.MapViewOfFile.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_size_t,
    ]
    _kernel32.MapViewOfFile.restype = ctypes.c_void_p
    _kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    _kernel32.UnmapViewOfFile.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL


class WindowsNamedSharedMemory:
    """Open an existing Windows named shared-memory mapping without creating it."""

    def __init__(self, map_name: str, size: int):
        if os.name != "nt":
            raise SharedMemoryUnavailable("rFactor 2 shared memory is Windows-only")
        self.map_name = map_name
        self.size = size
        self.handle = None
        self.view = None
        self.opened_name = None
        self._open()

    def _open(self) -> None:
        candidates = [self.map_name, f"Global\\{self.map_name}"]
        last_error = 0
        for candidate in candidates:
            handle = _kernel32.OpenFileMappingW(FILE_MAP_READ, False, candidate)
            if handle:
                view = _kernel32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, self.size)
                if view:
                    self.handle = handle
                    self.view = view
                    self.opened_name = candidate
                    return
                last_error = ctypes.get_last_error()
                _kernel32.CloseHandle(handle)
            else:
                last_error = ctypes.get_last_error()
        raise SharedMemoryUnavailable(
            f"Shared-memory map {self.map_name!r} is unavailable; WinError {last_error}"
        )

    def read(self, size: Optional[int] = None) -> bytes:
        if not self.view:
            raise SharedMemoryUnavailable(f"Shared-memory map {self.map_name!r} is closed")
        read_size = self.size if size is None else min(size, self.size)
        return ctypes.string_at(self.view, read_size)

    def close(self) -> None:
        if self.view:
            _kernel32.UnmapViewOfFile(self.view)
            self.view = None
        if self.handle:
            _kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "WindowsNamedSharedMemory":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


class RF2SharedMemoryReader:
    """Read all available rF2SharedMemoryMapPlugin output buffers."""

    def __init__(self, specs: Optional[Iterable[BufferSpec]] = None):
        self.specs = list(specs or output_buffer_specs())
        self._maps: Dict[str, WindowsNamedSharedMemory] = {}
        self._open_errors: Dict[str, str] = {}

    def open(self) -> "RF2SharedMemoryReader":
        for spec in self.specs:
            try:
                self._maps[spec.key] = WindowsNamedSharedMemory(spec.map_name, spec.size)
            except SharedMemoryUnavailable as exc:
                self._open_errors[spec.key] = str(exc)
        return self

    def close(self) -> None:
        for mapping in self._maps.values():
            mapping.close()
        self._maps.clear()

    def __enter__(self) -> "RF2SharedMemoryReader":
        return self.open()

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    @property
    def open_errors(self) -> Dict[str, str]:
        return dict(self._open_errors)

    @property
    def available_keys(self) -> List[str]:
        return sorted(self._maps.keys())

    def read_struct(self, spec: BufferSpec) -> Any:
        mapping = self._maps.get(spec.key)
        if mapping is None:
            raise SharedMemoryUnavailable(self._open_errors.get(spec.key, spec.map_name))

        raw = self._read_consistent_bytes(mapping, spec.size)
        return spec.struct_type.from_buffer_copy(raw)

    def _read_consistent_bytes(self, mapping: WindowsNamedSharedMemory, size: int) -> bytes:
        for _ in range(MAX_READ_RETRIES):
            header = mapping.read(8)
            begin_1, end_1 = struct.unpack_from("<ii", header, 0)
            if begin_1 != end_1:
                time.sleep(0.001)
                continue

            raw = mapping.read(size)
            begin_2, end_2 = struct.unpack_from("<ii", raw, 0)
            if begin_2 != end_2:
                time.sleep(0.001)
                continue

            header_after = mapping.read(8)
            begin_3, end_3 = struct.unpack_from("<ii", header_after, 0)
            if begin_2 == begin_3 and end_2 == end_3:
                return raw

            time.sleep(0.001)

        return mapping.read(size)


def _bounded_count(value: Any, maximum: int) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return maximum
    return max(0, min(count, maximum))


def _is_ctypes_structure(value: Any) -> bool:
    return isinstance(value, ctypes.Structure)


def _is_ctypes_array(value: Any) -> bool:
    return isinstance(value, ctypes.Array)


def _is_byte_array(value: Any) -> bool:
    return _is_ctypes_array(value) and value._type_ in (ctypes.c_ubyte, ctypes.c_byte, ctypes.c_char)


def _decode_c_string(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = bytes(int(item) & 0xFF for item in value)
    raw = raw.partition(b"\0")[0]
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding).rstrip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore").rstrip()


def _should_decode_as_text(field_name: str) -> bool:
    lowered = field_name.lower()
    return any(token in lowered for token in TEXT_FIELD_TOKENS)


def _is_expansion_field(field_name: str) -> bool:
    lowered = field_name.lower()
    return "expansion" in lowered or lowered.startswith("pointer")


def _array_limit(parent: Any, field_name: str, value: Any, trim: bool) -> int:
    maximum = len(value)
    if not trim:
        return maximum

    parent_name = type(parent).__name__
    if parent_name == "rF2Telemetry" and field_name == "mVehicles":
        return _bounded_count(getattr(parent, "mNumVehicles", maximum), maximum)
    if parent_name == "rF2Scoring" and field_name == "mVehicles":
        scoring_info = getattr(parent, "mScoringInfo", None)
        return _bounded_count(getattr(scoring_info, "mNumVehicles", maximum), maximum)
    if parent_name == "rF2Rules" and field_name == "mActions":
        track_rules = getattr(parent, "mTrackRules", None)
        return _bounded_count(getattr(track_rules, "mNumActions", maximum), maximum)
    if parent_name == "rF2Rules" and field_name == "mParticipants":
        track_rules = getattr(parent, "mTrackRules", None)
        return _bounded_count(getattr(track_rules, "mNumParticipants", maximum), maximum)
    if parent_name == "rF2SessionTransitionCapture" and field_name == "mScoringVehicles":
        return _bounded_count(getattr(parent, "mNumScoringVehicles", maximum), maximum)
    return maximum


def ctypes_to_python(
    value: Any,
    *,
    field_name: str = "",
    trim: bool = True,
    include_expansion: bool = False,
    parent: Any = None,
) -> Any:
    if _is_ctypes_structure(value):
        converted: Dict[str, Any] = {}
        for child_name, _child_type in value._fields_:
            if not include_expansion and _is_expansion_field(child_name):
                continue
            child_value = getattr(value, child_name)
            converted[child_name] = ctypes_to_python(
                child_value,
                field_name=child_name,
                trim=trim,
                include_expansion=include_expansion,
                parent=value,
            )
        return converted

    if _is_ctypes_array(value):
        if _is_byte_array(value) and _should_decode_as_text(field_name):
            return _decode_c_string(value)

        limit = _array_limit(parent, field_name, value, trim)
        return [
            ctypes_to_python(
                value[index],
                field_name=field_name,
                trim=trim,
                include_expansion=include_expansion,
                parent=value,
            )
            for index in range(limit)
        ]

    if isinstance(value, (bytes, bytearray)):
        return _decode_c_string(value)

    if isinstance(value, float):
        return float(value)
    if isinstance(value, int):
        return int(value)

    try:
        return value.value
    except AttributeError:
        return value


def _find_player_index(scoring: Optional[Dict[str, Any]]) -> Optional[int]:
    if not scoring:
        return None
    for index, vehicle in enumerate(scoring.get("mVehicles", [])):
        if vehicle.get("mIsPlayer"):
            return index
    return None


def _speed_from_telemetry(vehicle: Dict[str, Any]) -> Optional[float]:
    velocity = vehicle.get("mLocalVel")
    if not isinstance(velocity, dict):
        return None
    try:
        return (
            float(velocity["x"]) ** 2
            + float(velocity["y"]) ** 2
            + float(velocity["z"]) ** 2
        ) ** 0.5
    except (KeyError, TypeError, ValueError):
        return None


def _add_convenience_views(snapshot_data: Dict[str, Any]) -> None:
    scoring = snapshot_data.get("scoring")
    telemetry = snapshot_data.get("telemetry")
    player_index = _find_player_index(scoring)

    if player_index is None and telemetry and telemetry.get("mVehicles"):
        player_index = 0

    convenience: Dict[str, Any] = {
        "wheelOrder": ["frontLeft", "frontRight", "rearLeft", "rearRight"],
        "playerIndex": player_index,
    }

    if player_index is not None:
        if telemetry and player_index < len(telemetry.get("mVehicles", [])):
            player_telemetry = telemetry["mVehicles"][player_index]
            convenience["playerTelemetry"] = player_telemetry
            speed_mps = _speed_from_telemetry(player_telemetry)
            if speed_mps is not None:
                convenience["playerDynamics"] = {
                    "speed_mps": speed_mps,
                    "speed_kph": speed_mps * 3.6,
                    "localAcceleration": player_telemetry.get("mLocalAccel"),
                    "localRotation": player_telemetry.get("mLocalRot"),
                    "localRotationAcceleration": player_telemetry.get("mLocalRotAccel"),
                    "wheels": player_telemetry.get("mWheels"),
                }
        if scoring and player_index < len(scoring.get("mVehicles", [])):
            convenience["playerScoring"] = scoring["mVehicles"][player_index]

    pit_info = snapshot_data.get("pitInfo")
    if isinstance(pit_info, dict) and "mPitMneu" in pit_info and "mPitMenu" not in pit_info:
        pit_info["mPitMenu"] = pit_info["mPitMneu"]

    snapshot_data["convenience"] = convenience


def snapshot(trim: bool = True, include_expansion: bool = False) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "meta": {
            "timestampUnix": time.time(),
            "projectRoot": str(PROJECT_ROOT),
            "trimmedArrays": bool(trim),
            "includeExpansion": bool(include_expansion),
            "sources": {
                "plugin": "TheIronWolfModding/rF2SharedMemoryMapPlugin",
                "ctypesMapping": "TonyWhitley/pyRfactor2SharedMemory",
            },
        }
    }

    specs = output_buffer_specs()
    with RF2SharedMemoryReader(specs) as reader:
        data["meta"]["availableBuffers"] = reader.available_keys
        data["meta"]["missingBuffers"] = reader.open_errors
        data["meta"]["connected"] = "extended" in reader.available_keys
        data["meta"]["bufferSizes"] = {spec.key: spec.size for spec in specs}
        data["meta"]["refreshHz"] = {spec.key: spec.refresh_hz for spec in specs}

        for spec in specs:
            if spec.key not in reader.available_keys:
                continue
            struct_value = reader.read_struct(spec)
            data[spec.key] = ctypes_to_python(
                struct_value,
                field_name=spec.key,
                trim=trim,
                include_expansion=include_expansion,
            )

    if "extended" in data:
        data["meta"]["pluginVersion"] = data["extended"].get("mVersion")
    _add_convenience_views(data)
    return data


def snapshot_json(trim: bool = True, include_expansion: bool = False, pretty: bool = False) -> str:
    indent = 2 if pretty else None
    return json.dumps(snapshot(trim=trim, include_expansion=include_expansion), indent=indent)


def status() -> Dict[str, Any]:
    specs = output_buffer_specs()
    with RF2SharedMemoryReader(specs) as reader:
        result = {
            "connected": "extended" in reader.available_keys,
            "availableBuffers": reader.available_keys,
            "missingBuffers": reader.open_errors,
            "projectRoot": str(PROJECT_ROOT),
            "bufferSizes": {spec.key: spec.size for spec in specs},
        }
    if result["connected"]:
        snap = snapshot(trim=True, include_expansion=False)
        result["pluginVersion"] = snap.get("meta", {}).get("pluginVersion", "")
    return result


def status_json(pretty: bool = False) -> str:
    return json.dumps(status(), indent=2 if pretty else None)


def schema() -> Dict[str, Any]:
    def describe_struct(struct_type: Any) -> Any:
        return {
            field_name: getattr(field_type, "__name__", str(field_type))
            for field_name, field_type in struct_type._fields_
        }

    return {
        "buffers": {
            spec.key: {
                "mapName": spec.map_name,
                "sizeBytes": spec.size,
                "refreshHz": spec.refresh_hz,
                "fields": describe_struct(spec.struct_type),
            }
            for spec in output_buffer_specs()
        },
        "vehicleTelemetryFields": describe_struct(rF2data.rF2VehicleTelemetry),
        "wheelFields": describe_struct(rF2data.rF2Wheel),
        "wheelOrder": ["frontLeft", "frontRight", "rearLeft", "rearRight"],
    }


def schema_json(pretty: bool = False) -> str:
    return json.dumps(schema(), indent=2 if pretty else None)


def log_jsonl(path: str, seconds: float, hz: float, full: bool = False) -> Dict[str, Any]:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    interval = 1.0 / hz
    deadline = time.perf_counter() + seconds
    rows = 0

    with out_path.open("w", encoding="utf-8") as handle:
        while time.perf_counter() < deadline:
            started = time.perf_counter()
            handle.write(snapshot_json(trim=not full, include_expansion=False, pretty=False))
            handle.write("\n")
            rows += 1
            elapsed = time.perf_counter() - started
            time.sleep(max(0.0, interval - elapsed))

    return {"path": str(out_path), "rows": rows, "seconds": seconds, "hz": hz}


def log_jsonl_json(path: str, seconds: float, hz: float, full: bool = False) -> str:
    return json.dumps(log_jsonl(path, seconds, hz, full=full))


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read rFactor 2 shared memory for MATLAB")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--pretty", action="store_true")

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--full", action="store_true", help="do not trim vehicle/action arrays")
    snapshot_parser.add_argument("--include-expansion", action="store_true")
    snapshot_parser.add_argument("--pretty", action="store_true")

    schema_parser = subparsers.add_parser("schema")
    schema_parser.add_argument("--pretty", action="store_true")

    log_parser = subparsers.add_parser("log")
    log_parser.add_argument("--seconds", type=float, default=10.0)
    log_parser.add_argument("--hz", type=float, default=20.0)
    log_parser.add_argument("--out", required=True)
    log_parser.add_argument("--full", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if args.command == "status":
        print(status_json(pretty=args.pretty))
    elif args.command == "snapshot":
        print(
            snapshot_json(
                trim=not args.full,
                include_expansion=args.include_expansion,
                pretty=args.pretty,
            )
        )
    elif args.command == "schema":
        print(schema_json(pretty=args.pretty))
    elif args.command == "log":
        print(json.dumps(log_jsonl(args.out, args.seconds, args.hz, full=args.full), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
