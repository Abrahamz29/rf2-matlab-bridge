"""Experiment runner for rFactor 2 telemetry and automated maneuvers.

This script supports two practical automation modes for the current project:

- ``open_loop``: send keyboard-based throttle/brake/steer commands while
  logging telemetry
- ``ai_driver_monitor``: switch control to the local AI driver and log the run

It also provides preflight validation for installed tracks and the currently
loaded session so experiment variants fail early with a useful error.
"""

from __future__ import annotations

import argparse
import copy
import csv
import ctypes
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "python"))

from rf2_matlab_bridge import snapshot, status  # noqa: E402


RFACTOR_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\rFactor 2")
CONTROLLER_JSON = RFACTOR_ROOT / "UserData" / "player" / "Controller.JSON"
INSTALLED_LOCATIONS = RFACTOR_ROOT / "Installed" / "Locations"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "logs"
INHERITED_SCENARIO_KEYS = {
    "mode",
    "track",
    "vehicle",
    "notes",
    "control_hz",
    "sample_hz",
    "countdown_s",
    "duration_s",
    "warmup_s",
    "pause_after_s",
    "ensure_player_control",
    "ensure_ai_control",
    "restore_player_control",
    "focus_window",
    "require_session_match",
    "segments",
    "replications",
}

KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
SW_RESTORE = 9


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUTUNION)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


@dataclass
class ControlBinding:
    name: str
    scan_code: int


class KeyboardController:
    """Send scan-code based keyboard input and keep track of held keys."""

    def __init__(self) -> None:
        self.held: set[int] = set()

    def key_down(self, scan_code: int) -> None:
        if scan_code in self.held:
            return
        self._send(scan_code, KEYEVENTF_SCANCODE)
        self.held.add(scan_code)

    def key_up(self, scan_code: int) -> None:
        if scan_code not in self.held:
            return
        self._send(scan_code, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)
        self.held.remove(scan_code)

    def release_all(self) -> None:
        for scan_code in list(self.held):
            self.key_up(scan_code)

    def tap(self, scan_code: int, duration: float = 0.05) -> None:
        self.key_down(scan_code)
        time.sleep(duration)
        self.key_up(scan_code)

    def _send(self, scan_code: int, flags: int) -> None:
        data = INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(
            wVk=0,
            wScan=scan_code,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        )))
        sent = user32.SendInput(1, ctypes.byref(data), ctypes.sizeof(INPUT))
        if sent != 1:
            raise OSError(f"SendInput failed for scan code {scan_code}")


class DutyModulator:
    """Pulse-density modulator for a 0..1 digital approximation."""

    def __init__(self) -> None:
        self.accumulator = 0.0

    def step(self, duty: float) -> bool:
        duty = clamp(duty, 0.0, 1.0)
        self.accumulator += duty
        if self.accumulator >= 1.0:
            self.accumulator -= 1.0
            return True
        return False


class SignedDutyModulator:
    """Pulse-density modulator for a -1..1 signed digital approximation."""

    def __init__(self) -> None:
        self.positive = DutyModulator()
        self.negative = DutyModulator()

    def step(self, duty: float) -> int:
        duty = clamp(duty, -1.0, 1.0)
        if duty > 0:
            self.negative.accumulator = 0.0
            return 1 if self.positive.step(duty) else 0
        if duty < 0:
            self.positive.accumulator = 0.0
            return -1 if self.negative.step(-duty) else 0
        self.positive.accumulator = 0.0
        self.negative.accumulator = 0.0
        return 0


class RF2Window:
    """Best-effort focus helper for the rFactor 2 client window."""

    def focus(self) -> bool:
        hwnd = self._find_window()
        if hwnd == 0:
            return False
        user32.ShowWindow(hwnd, SW_RESTORE)
        return bool(user32.SetForegroundWindow(hwnd))

    def _find_window(self) -> int:
        matches: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            title = self._window_title(hwnd)
            if not title:
                return True
            exe_name = self._window_executable(hwnd)
            title_lower = title.lower()
            if exe_name == "rfactor2.exe" or "rfactor 2" in title_lower:
                matches.append(hwnd)
            return True

        user32.EnumWindows(enum_callback, 0)
        return matches[0] if matches else 0

    def _window_title(self, hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value

    def _window_executable(self, hwnd: int) -> str:
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return ""
        process = kernel32.OpenProcess(0x1000 | 0x0400, False, pid.value)
        if not process:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(len(buffer))
            if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name.lower()
            if psapi.GetModuleFileNameExW(process, None, buffer, len(buffer)):
                return Path(buffer.value).name.lower()
        finally:
            kernel32.CloseHandle(process)
        return ""


def load_bindings(path: Path = CONTROLLER_JSON) -> Dict[str, ControlBinding]:
    with path.open("r", encoding="utf-8-sig") as handle:
        controller = json.load(handle)
    controls = controller["Input"]

    names = {
        "throttle": "Control - Throttle",
        "brake": "Control - Brake",
        "steer_left": "Control - Steer Left",
        "steer_right": "Control - Steer Right",
        "toggle_ai": "Control - Toggle AI Control",
        "shift_up": "Control - Shift Up",
        "shift_down": "Control - Shift Down",
    }
    bindings: Dict[str, ControlBinding] = {}
    for key, control_name in names.items():
        scan_code = int(controls[control_name][1])
        bindings[key] = ControlBinding(control_name, scan_code)
    return bindings


def scan_installed_tracks(root: Path = INSTALLED_LOCATIONS) -> List[Dict[str, Any]]:
    tracks: List[Dict[str, Any]] = []
    if not root.exists():
        return tracks
    for track_dir in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not track_dir.is_dir():
            continue
        versions = sorted(
            [child.name for child in track_dir.iterdir() if child.is_dir()],
            key=str.lower,
        )
        tracks.append({
            "installed_name": track_dir.name,
            "path": str(track_dir),
            "versions": versions,
        })
    return tracks


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def slugify(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text or "scenario"


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def inherited_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    defaults = copy.deepcopy(config.get("scenario_defaults", {}))
    for key in INHERITED_SCENARIO_KEYS:
        if key in config and key not in defaults:
            defaults[key] = copy.deepcopy(config[key])
    return defaults


def as_scenarios(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    defaults = inherited_defaults(config)
    if "scenarios" in config:
        raw = [merge_dicts(defaults, scenario) for scenario in config["scenarios"]]
    elif "variants" in config:
        raw = [merge_dicts(defaults, variant) for variant in config["variants"]]
    else:
        raw = [merge_dicts(defaults, config)]

    expanded: List[Dict[str, Any]] = []
    for scenario in raw:
        replications = max(1, int(scenario.get("replications", 1)))
        base_name = str(scenario.get("name", "scenario"))
        for index in range(replications):
            scenario_copy = copy.deepcopy(scenario)
            if replications > 1:
                scenario_copy["name"] = f"{base_name}_rep{index + 1:02d}"
                scenario_copy["replication_index"] = index + 1
                scenario_copy["replication_count"] = replications
            expanded.append(scenario_copy)
    return expanded


def find_track_match(track_request: Dict[str, Any], installed_tracks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = [
        track_request.get("installed_name"),
        track_request.get("alias"),
        track_request.get("name"),
    ]
    normalized = [normalize_name(item) for item in candidates if item]
    if not normalized:
        return None

    for track in installed_tracks:
        installed_norm = normalize_name(track["installed_name"])
        if any(
            token
            and (token == installed_norm or token in installed_norm or installed_norm in token)
            for token in normalized
        ):
            return track
    return None


def track_preflight(track_request: Optional[Dict[str, Any]], installed_tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not track_request:
        return {"ok": True, "requested": None, "matched": None, "reason": "no track requested"}

    required = bool(track_request.get("required", True))
    matched = find_track_match(track_request, installed_tracks)
    if matched:
        return {"ok": True, "requested": track_request, "matched": matched, "reason": "installed"}
    return {
        "ok": not required,
        "requested": track_request,
        "matched": None,
        "reason": "track not installed",
    }


def current_track_names(snap: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    scoring = snap.get("scoring", {})
    scoring_info = scoring.get("mScoringInfo", {}) if isinstance(scoring, dict) else {}
    player_scoring = snap.get("convenience", {}).get("playerScoring", {})
    for value in (
        scoring_info.get("mTrackName"),
        player_scoring.get("mTrackName"),
    ):
        if isinstance(value, str) and value.strip():
            names.append(value.strip())
    return list(dict.fromkeys(names))


def session_track_matches(track_request: Optional[Dict[str, Any]], snap: Dict[str, Any]) -> bool:
    if not track_request:
        return True

    expected_values = [
        track_request.get("current_name_contains"),
        track_request.get("alias"),
        track_request.get("name"),
        track_request.get("installed_name"),
    ]
    expected = [normalize_name(value) for value in expected_values if value]
    if not expected:
        return True

    actual_names = [normalize_name(value) for value in current_track_names(snap)]
    return any(
        token and actual and (token in actual or actual in token)
        for token in expected
        for actual in actual_names
    )


def scenario_duration(scenario: Dict[str, Any]) -> float:
    if "duration_s" in scenario:
        return float(scenario["duration_s"])
    if "segments" in scenario:
        return sum(float(segment["duration_s"]) for segment in scenario["segments"])
    raise ValueError(f"Scenario '{scenario.get('name', 'scenario')}' is missing duration information")


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def evaluate_command(spec: Any, elapsed: float, duration: float) -> float:
    if spec is None:
        return 0.0
    if isinstance(spec, (int, float)):
        return float(spec)
    if not isinstance(spec, dict):
        raise ValueError(f"Unsupported command specification: {spec!r}")

    kind = str(spec.get("kind", "constant")).lower()
    if kind == "constant":
        return float(spec.get("value", spec.get("offset", 0.0)))
    if kind == "ramp":
        start = float(spec.get("start", 0.0))
        end = float(spec.get("end", start))
        alpha = 0.0 if duration <= 0 else min(max(elapsed / duration, 0.0), 1.0)
        return start + alpha * (end - start)
    if kind == "sine":
        amplitude = float(spec.get("amplitude", 0.0))
        offset = float(spec.get("offset", 0.0))
        frequency = float(spec.get("frequency_hz", 1.0))
        phase = float(spec.get("phase_rad", 0.0))
        return offset + amplitude * math.sin((2.0 * math.pi * frequency * elapsed) + phase)
    raise ValueError(f"Unsupported command kind: {kind}")


def ensure_control_mode(
    want_ai: bool,
    bindings: Dict[str, ControlBinding],
    controller: KeyboardController,
    timeout: float = 5.0,
) -> None:
    deadline = time.time() + timeout
    desired = 1 if want_ai else 0

    while time.time() < deadline:
        snap = snapshot(trim=True)
        scoring = snap.get("convenience", {}).get("playerScoring")
        if scoring and int(scoring.get("mControl", -1)) == desired:
            return
        controller.tap(bindings["toggle_ai"].scan_code, duration=0.08)
        time.sleep(0.5)

    mode_name = "AI" if want_ai else "player"
    raise TimeoutError(f"Could not switch rFactor 2 control mode to {mode_name}")


def wait_for_rf2_ready(timeout: float = 30.0) -> Dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = snapshot(trim=True)
        extended = snap.get("extended", {})
        if snap.get("meta", {}).get("connected") and int(extended.get("mSessionStarted", 0)) != 0:
            return snap
        time.sleep(0.5)
    raise TimeoutError("rFactor 2 shared memory is not ready; load a session and go on track")


def require_session_track(track_request: Optional[Dict[str, Any]], snap: Dict[str, Any], scenario_name: str) -> None:
    if not track_request:
        return
    if session_track_matches(track_request, snap):
        return

    actual = current_track_names(snap)
    expected = ", ".join(
        str(value) for value in (
            track_request.get("current_name_contains"),
            track_request.get("alias"),
            track_request.get("name"),
            track_request.get("installed_name"),
        ) if value
    )
    raise RuntimeError(
        f"Scenario '{scenario_name}' expects track '{expected}', "
        f"but current session reports {actual or ['<unknown>']}"
    )


def snapshot_session_summary(snap: Dict[str, Any]) -> Dict[str, Any]:
    scoring = snap.get("scoring", {})
    scoring_info = scoring.get("mScoringInfo", {}) if isinstance(scoring, dict) else {}
    player_scoring = snap.get("convenience", {}).get("playerScoring", {})
    telemetry = snap.get("convenience", {}).get("playerTelemetry", {})
    return {
        "track_names": current_track_names(snap),
        "session": scoring_info.get("mSession"),
        "session_time_s": scoring_info.get("mCurrentET"),
        "lap_distance_m": player_scoring.get("mLapDist"),
        "control_mode": player_scoring.get("mControl"),
        "vehicle_name": player_scoring.get("mVehicleName"),
        "vehicle_class": player_scoring.get("mVehicleClass"),
        "gear": telemetry.get("mGear"),
        "speed_kph": snap.get("convenience", {}).get("playerDynamics", {}).get("speed_kph"),
    }


def flatten_snapshot(
    snap: Dict[str, Any],
    scenario_name: str,
    scenario_mode: str,
    segment_name: str,
    elapsed: float,
    throttle_cmd: float,
    brake_cmd: float,
    steer_cmd: float,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "scenario": scenario_name,
        "mode": scenario_mode,
        "segment": segment_name,
        "elapsed_s": elapsed,
        "command_throttle": throttle_cmd,
        "command_brake": brake_cmd,
        "command_steer": steer_cmd,
    }

    telemetry = snap.get("convenience", {}).get("playerTelemetry", {})
    dynamics = snap.get("convenience", {}).get("playerDynamics", {})
    player_scoring = snap.get("convenience", {}).get("playerScoring", {})
    scoring_info = snap.get("scoring", {}).get("mScoringInfo", {})

    row["track_name"] = next(iter(current_track_names(snap)), None)
    row["session_type"] = scoring_info.get("mSession")
    row["session_time_s"] = scoring_info.get("mCurrentET")
    row["lap_distance_m"] = player_scoring.get("mLapDist")
    row["control_mode"] = player_scoring.get("mControl")

    row["speed_kph"] = dynamics.get("speed_kph")
    row["gear"] = telemetry.get("mGear")
    row["rpm"] = telemetry.get("mEngineRPM")
    row["driver_throttle"] = telemetry.get("mUnfilteredThrottle")
    row["driver_brake"] = telemetry.get("mUnfilteredBrake")
    row["driver_steer"] = telemetry.get("mUnfilteredSteering")

    local_accel = telemetry.get("mLocalAccel", {})
    row["lat_g"] = local_accel.get("x", 0.0) / 9.80665 if local_accel else None
    row["long_g"] = local_accel.get("z", 0.0) / 9.80665 if local_accel else None

    wheels = dynamics.get("wheels", [])
    wheel_labels = ["fl", "fr", "rl", "rr"]
    for label, wheel in zip(wheel_labels, wheels):
        row[f"{label}_load_n"] = wheel.get("mTireLoad")
        row[f"{label}_grip"] = wheel.get("mGripFract")
        row[f"{label}_pressure_kpa"] = wheel.get("mPressure")
        row[f"{label}_brake_temp_c"] = wheel.get("mBrakeTemp")
        row[f"{label}_carcass_temp_c"] = _kelvin_to_c(wheel.get("mTireCarcassTemperature"))

        surface = wheel.get("mTemperature", [])
        row[f"{label}_surface_temp_c"] = _mean_kelvin_to_c(surface)
    return row


def _kelvin_to_c(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value) - 273.15


def _mean_kelvin_to_c(values: Iterable[Any]) -> Optional[float]:
    values = [float(value) for value in values]
    if not values:
        return None
    return (sum(values) / len(values)) - 273.15


def _write_run_metadata(path: Path, scenario: Dict[str, Any], track_info: Dict[str, Any], session_info: Dict[str, Any]) -> None:
    payload = {
        "scenario": scenario,
        "trackPreflight": track_info,
        "sessionAtStart": session_info,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def run_open_loop(
    scenario: Dict[str, Any],
    scenario_name: str,
    controller: KeyboardController,
    bindings: Dict[str, ControlBinding],
    rows: List[Dict[str, Any]],
    t0: float,
    sample_hz: float,
) -> None:
    control_hz = float(scenario.get("control_hz", 20.0))
    segments = scenario["segments"]
    throttle_mod = DutyModulator()
    brake_mod = DutyModulator()
    steer_mod = SignedDutyModulator()
    next_sample = time.time()

    for index, segment in enumerate(segments):
        segment_name = str(segment.get("name", f"segment_{index + 1}"))
        duration = float(segment["duration_s"])
        segment_start = time.time()
        while True:
            now = time.time()
            elapsed = now - segment_start
            if elapsed >= duration:
                break

            throttle = clamp(evaluate_command(segment.get("throttle", 0.0), elapsed, duration), 0.0, 1.0)
            brake = clamp(evaluate_command(segment.get("brake", 0.0), elapsed, duration), 0.0, 1.0)
            steer = clamp(evaluate_command(segment.get("steer", 0.0), elapsed, duration), -1.0, 1.0)

            cycle_start = time.time()
            if throttle_mod.step(throttle):
                controller.key_down(bindings["throttle"].scan_code)
            else:
                controller.key_up(bindings["throttle"].scan_code)

            if brake_mod.step(brake):
                controller.key_down(bindings["brake"].scan_code)
            else:
                controller.key_up(bindings["brake"].scan_code)

            steer_state = steer_mod.step(steer)
            if steer_state > 0:
                controller.key_down(bindings["steer_right"].scan_code)
                controller.key_up(bindings["steer_left"].scan_code)
            elif steer_state < 0:
                controller.key_down(bindings["steer_left"].scan_code)
                controller.key_up(bindings["steer_right"].scan_code)
            else:
                controller.key_up(bindings["steer_left"].scan_code)
                controller.key_up(bindings["steer_right"].scan_code)

            if time.time() >= next_sample:
                snap = snapshot(trim=True)
                rows.append(flatten_snapshot(
                    snap,
                    scenario_name=scenario_name,
                    scenario_mode="open_loop",
                    segment_name=segment_name,
                    elapsed=time.time() - t0,
                    throttle_cmd=throttle,
                    brake_cmd=brake,
                    steer_cmd=steer,
                ))
                next_sample += 1.0 / sample_hz

            remaining = (1.0 / control_hz) - (time.time() - cycle_start)
            if remaining > 0:
                time.sleep(remaining)


def run_ai_monitor(
    scenario: Dict[str, Any],
    scenario_name: str,
    rows: List[Dict[str, Any]],
    t0: float,
    sample_hz: float,
) -> None:
    duration = scenario_duration(scenario)
    next_sample = time.time()
    while True:
        now = time.time()
        elapsed = now - t0
        if elapsed >= duration:
            break
        if now >= next_sample:
            snap = snapshot(trim=True)
            rows.append(flatten_snapshot(
                snap,
                scenario_name=scenario_name,
                scenario_mode="ai_driver_monitor",
                segment_name="ai_drive",
                elapsed=elapsed,
                throttle_cmd=0.0,
                brake_cmd=0.0,
                steer_cmd=0.0,
            ))
            next_sample += 1.0 / sample_hz
        sleep_for = max(0.0, min((1.0 / sample_hz) * 0.5, next_sample - time.time()))
        if sleep_for > 0:
            time.sleep(sleep_for)


def run_scenario(
    scenario: Dict[str, Any],
    out_dir: Path,
    bindings: Dict[str, ControlBinding],
    installed_tracks: List[Dict[str, Any]],
    focus_window: bool,
) -> Path:
    scenario_name = str(scenario.get("name", "scenario"))
    scenario_mode = str(scenario.get("mode", "open_loop")).lower()
    sample_hz = float(scenario.get("sample_hz", scenario.get("control_hz", 20.0)))
    countdown = float(scenario.get("countdown_s", 2.0))
    warmup = float(scenario.get("warmup_s", 0.0))
    pause_after = float(scenario.get("pause_after_s", 0.0))
    ensure_player = bool(scenario.get("ensure_player_control", scenario_mode == "open_loop"))
    ensure_ai = bool(scenario.get("ensure_ai_control", scenario_mode == "ai_driver_monitor"))
    restore_player = bool(scenario.get("restore_player_control", False))
    require_match = bool(scenario.get("require_session_match", True))
    track_request = scenario.get("track")

    preflight = track_preflight(track_request, installed_tracks)
    if not preflight["ok"]:
        requested = track_request or {}
        expected = requested.get("installed_name") or requested.get("alias") or requested.get("name")
        raise RuntimeError(f"Scenario '{scenario_name}' requests missing track '{expected}'")

    window = RF2Window()
    if focus_window:
        window.focus()

    controller = KeyboardController()
    ready_snap = wait_for_rf2_ready()
    if require_match:
        require_session_track(track_request, ready_snap, scenario_name)

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = out_dir / f"{stamp}_{slugify(scenario_name)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = run_dir / "scenario.json"
    csv_path = run_dir / "telemetry.csv"
    _write_run_metadata(metadata_path, scenario, preflight, snapshot_session_summary(ready_snap))

    rows: List[Dict[str, Any]] = []
    time.sleep(countdown)

    try:
        if ensure_player:
            ensure_control_mode(False, bindings, controller)
        if ensure_ai:
            ensure_control_mode(True, bindings, controller)
        if warmup > 0:
            time.sleep(warmup)

        t0 = time.time()
        if scenario_mode == "open_loop":
            if "segments" not in scenario:
                raise ValueError(f"Scenario '{scenario_name}' in open_loop mode needs 'segments'")
            run_open_loop(scenario, scenario_name, controller, bindings, rows, t0, sample_hz)
        elif scenario_mode == "ai_driver_monitor":
            run_ai_monitor(scenario, scenario_name, rows, t0, sample_hz)
        else:
            raise ValueError(f"Unsupported mode '{scenario_mode}' in scenario '{scenario_name}'")
    finally:
        controller.release_all()
        if restore_player:
            ensure_control_mode(False, bindings, controller)

    write_rows(csv_path, rows)
    if pause_after > 0:
        time.sleep(pause_after)
    return run_dir


def write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dry_run_summary(config: Dict[str, Any], config_path: Path, out_dir: Path, bindings: Dict[str, ControlBinding]) -> Dict[str, Any]:
    installed_tracks = scan_installed_tracks()
    scenarios = as_scenarios(config)
    summaries: List[Dict[str, Any]] = []
    for scenario in scenarios:
        preflight = track_preflight(scenario.get("track"), installed_tracks)
        summaries.append({
            "name": scenario.get("name", "scenario"),
            "mode": scenario.get("mode", "open_loop"),
            "track": preflight,
            "duration_s": scenario_duration(scenario),
        })
    return {
        "config": str(config_path),
        "output": str(out_dir / str(config.get("batch_name", config_path.stem))),
        "bindings": {key: value.scan_code for key, value in bindings.items()},
        "installed_tracks": installed_tracks,
        "scenarios": summaries,
    }


def list_tracks_payload() -> Dict[str, Any]:
    tracks = scan_installed_tracks()
    return {
        "rfactorRoot": str(RFACTOR_ROOT),
        "installedLocations": str(INSTALLED_LOCATIONS),
        "tracks": tracks,
        "trackCount": len(tracks),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run scripted rFactor 2 experiments")
    parser.add_argument("config", nargs="?", type=Path, help="Path to JSON scenario or batch config")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-focus", action="store_true", help="Do not try to focus the rFactor 2 window")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and bindings without sending inputs")
    parser.add_argument("--list-tracks", action="store_true", help="Print installed rFactor 2 locations as JSON and exit")
    args = parser.parse_args(argv)

    if args.list_tracks:
        print(json.dumps(list_tracks_payload(), indent=2))
        return 0

    if args.config is None:
        parser.error("the following arguments are required: config")

    config = load_config(args.config)
    bindings = load_bindings()
    installed_tracks = scan_installed_tracks()
    run_root = args.out / str(config.get("batch_name", args.config.stem))
    run_root.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(json.dumps(dry_run_summary(config, args.config, args.out, bindings), indent=2))
        return 0

    ready = status()
    if not ready.get("connected"):
        raise RuntimeError("rFactor 2 shared memory is not connected")

    run_dirs: List[str] = []
    for scenario in as_scenarios(config):
        scenario_focus = not args.no_focus if "focus_window" not in scenario else bool(scenario["focus_window"])
        run_dir = run_scenario(
            scenario,
            run_root,
            bindings,
            installed_tracks=installed_tracks,
            focus_window=scenario_focus,
        )
        run_dirs.append(str(run_dir))
        print(run_dir)

    summary_path = run_root / "batch_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump({
            "batch_name": config.get("batch_name", args.config.stem),
            "config": str(args.config),
            "runs": run_dirs,
        }, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
