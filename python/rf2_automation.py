"""Open-loop maneuver runner for rFactor 2.

This script drives rFactor 2 through Windows keyboard input based on the
currently configured scan codes in Controller.JSON, while logging shared-memory
telemetry to CSV for later MATLAB analysis.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import math
import os
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
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "logs"

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


def as_scenarios(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "scenarios" in config:
        return list(config["scenarios"])
    return [config]


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


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


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

    raise TimeoutError("Could not switch rFactor 2 control mode")


def wait_for_rf2_ready(timeout: float = 30.0) -> Dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = snapshot(trim=True)
        extended = snap.get("extended", {})
        if snap.get("meta", {}).get("connected") and int(extended.get("mSessionStarted", 0)) != 0:
            return snap
        time.sleep(0.5)
    raise TimeoutError("rFactor 2 shared memory is not ready; load a session and go on track")


def flatten_snapshot(
    snap: Dict[str, Any],
    scenario_name: str,
    segment_name: str,
    elapsed: float,
    throttle_cmd: float,
    brake_cmd: float,
    steer_cmd: float,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "scenario": scenario_name,
        "segment": segment_name,
        "elapsed_s": elapsed,
        "command_throttle": throttle_cmd,
        "command_brake": brake_cmd,
        "command_steer": steer_cmd,
    }

    telemetry = snap.get("convenience", {}).get("playerTelemetry", {})
    dynamics = snap.get("convenience", {}).get("playerDynamics", {})

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


def run_scenario(
    scenario: Dict[str, Any],
    out_dir: Path,
    bindings: Dict[str, ControlBinding],
    focus_window: bool,
) -> Path:
    scenario_name = str(scenario.get("name", "scenario"))
    control_hz = float(scenario.get("control_hz", 20.0))
    sample_hz = float(scenario.get("sample_hz", control_hz))
    countdown = float(scenario.get("countdown_s", 2.0))
    ensure_player = bool(scenario.get("ensure_player_control", True))

    window = RF2Window()
    if focus_window:
        window.focus()

    controller = KeyboardController()
    wait_for_rf2_ready()
    if ensure_player:
        ensure_control_mode(False, bindings, controller)

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = out_dir / f"{stamp}_{scenario_name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = run_dir / "scenario.json"
    csv_path = run_dir / "telemetry.csv"
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(scenario, handle, indent=2)

    segments = scenario["segments"]
    rows: List[Dict[str, Any]] = []
    throttle_mod = DutyModulator()
    brake_mod = DutyModulator()
    steer_mod = SignedDutyModulator()
    time.sleep(countdown)
    t0 = time.time()
    next_sample = t0

    try:
        for index, segment in enumerate(segments):
            segment_name = str(segment.get("name", f"segment_{index+1}"))
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
    finally:
        controller.release_all()

    write_rows(csv_path, rows)
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run scripted rFactor 2 open-loop maneuvers")
    parser.add_argument("config", type=Path, help="Path to JSON scenario or batch config")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-focus", action="store_true", help="Do not try to focus the rFactor 2 window")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and bindings without sending inputs")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    bindings = load_bindings()

    run_root = args.out / str(config.get("batch_name", args.config.stem))
    run_root.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        summary = {
            "config": str(args.config),
            "output": str(run_root),
            "bindings": {key: value.scan_code for key, value in bindings.items()},
            "scenarios": [scenario.get("name", "scenario") for scenario in as_scenarios(config)],
        }
        print(json.dumps(summary, indent=2))
        return 0

    ready = status()
    if not ready.get("connected"):
        raise RuntimeError("rFactor 2 shared memory is not connected")

    for scenario in as_scenarios(config):
        run_dir = run_scenario(scenario, run_root, bindings, focus_window=not args.no_focus)
        print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
