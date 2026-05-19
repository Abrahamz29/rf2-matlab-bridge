"""Reusable rFactor 2 input control helpers for Python and MATLAB.

This module exposes a small actuator surface that MATLAB can drive through the
Python bridge while shared-memory telemetry is read in parallel.
"""

from __future__ import annotations

import ctypes
import time
from pathlib import Path
from typing import Any, Dict

from rf2_matlab_bridge import snapshot


RFACTOR_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\rFactor 2")
SW_RESTORE = 9
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


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


class DutyModulator:
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


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


class RF2Window:
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


class KeyboardController:
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


def load_bindings(path: Path = RFACTOR_ROOT / "UserData" / "player" / "Controller.JSON") -> Dict[str, int]:
    import json

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
    return {key: int(controls[name][1]) for key, name in names.items()}


class RF2Actuator:
    """Digital actuator wrapper with analog-style command interface."""

    def __init__(self) -> None:
        self.bindings = load_bindings()
        self.controller = KeyboardController()
        self.window = RF2Window()
        self.throttle_mod = DutyModulator()
        self.brake_mod = DutyModulator()
        self.steer_mod = SignedDutyModulator()

    def focus_window(self) -> bool:
        return self.window.focus()

    def release_all(self) -> None:
        self.controller.release_all()

    def ensure_player_control(self, timeout: float = 5.0) -> None:
        self._ensure_control_mode(False, timeout)

    def ensure_ai_control(self, timeout: float = 5.0) -> None:
        self._ensure_control_mode(True, timeout)

    def set_commands(self, throttle: float, brake: float, steer: float) -> None:
        throttle = clamp(float(throttle), 0.0, 1.0)
        brake = clamp(float(brake), 0.0, 1.0)
        steer = clamp(float(steer), -1.0, 1.0)

        if self.throttle_mod.step(throttle):
            self.controller.key_down(self.bindings["throttle"])
        else:
            self.controller.key_up(self.bindings["throttle"])

        if self.brake_mod.step(brake):
            self.controller.key_down(self.bindings["brake"])
        else:
            self.controller.key_up(self.bindings["brake"])

        steer_state = self.steer_mod.step(steer)
        if steer_state > 0:
            self.controller.key_down(self.bindings["steer_right"])
            self.controller.key_up(self.bindings["steer_left"])
        elif steer_state < 0:
            self.controller.key_down(self.bindings["steer_left"])
            self.controller.key_up(self.bindings["steer_right"])
        else:
            self.controller.key_up(self.bindings["steer_left"])
            self.controller.key_up(self.bindings["steer_right"])

    def neutral(self) -> None:
        self.set_commands(0.0, 0.0, 0.0)

    def _ensure_control_mode(self, want_ai: bool, timeout: float) -> None:
        deadline = time.time() + timeout
        desired = 1 if want_ai else 0
        while time.time() < deadline:
            snap = snapshot(trim=True)
            scoring = snap.get("convenience", {}).get("playerScoring")
            if scoring and int(scoring.get("mControl", -1)) == desired:
                return
            self.controller.tap(self.bindings["toggle_ai"], duration=0.08)
            time.sleep(0.5)
        mode_name = "AI" if want_ai else "player"
        raise TimeoutError(f"Could not switch rFactor 2 control mode to {mode_name}")
