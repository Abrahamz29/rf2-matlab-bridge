from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys

try:
    import win32con
    import win32gui
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("pywin32 is required for MAS2 automation") from exc


STAGES = {"250m", "500m", "1000m", "2000m", "5000m", "12000m"}


def kill_mas2() -> None:
    subprocess.run(
        ["taskkill", "/IM", "MAS2.exe", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def mas2_path(rf2_root: Path) -> Path:
    path = rf2_root / "Support" / "Tools" / "MAS2.exe"
    if not path.exists():
        raise FileNotFoundError(f"MAS2.exe not found: {path}")
    return path


def connect_mas2(rf2_root: Path, cwd: Path) -> tuple[subprocess.Popen, Application]:
    kill_mas2()
    proc = subprocess.Popen([str(mas2_path(rf2_root))], cwd=str(cwd))
    app = Application(backend="win32").connect(process=proc.pid, timeout=10)
    app.window(title_re=r".*MAS File Utility.*").wait("visible ready", timeout=10)
    return proc, app


def select_file_dialog(app: Application, title: str, value: str, edit_id: int = 1148) -> None:
    dlg = app.window(title=title)
    dlg.wait("visible ready", timeout=10)
    dlg.child_window(class_name="Edit", control_id=edit_id).set_edit_text(value)
    dlg.child_window(class_name="Button", control_id=1).click_input()


def make_mas(rf2_root: Path, source_dir: Path, mas_name: str) -> Path:
    if not source_dir.exists():
        raise FileNotFoundError(f"MAS source directory not found: {source_dir}")
    out = source_dir / mas_name
    if out.exists():
        out.unlink()

    files = sorted(path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() != ".mas")
    if not files:
        raise RuntimeError(f"No source files found in {source_dir}")

    _proc, app = connect_mas2(rf2_root, source_dir)
    win = app.window(title_re=r".*MAS File Utility.*")
    for path in files:
        win.set_focus()
        time.sleep(0.2)
        send_keys("%e")
        time.sleep(0.15)
        send_keys("f")
        select_file_dialog(app, "Select files to add to MAS archive", str(path), edit_id=1148)
        win.wait("enabled ready", timeout=30)
        time.sleep(0.2)

    list_count = win.child_window(class_name="SysListView32").wrapper_object().item_count()
    if list_count != len(files):
        raise RuntimeError(f"Expected {len(files)} files in {mas_name}, got {list_count}")

    win.set_focus()
    send_keys("^s")
    save = app.window(title="Select MAS archive to save")
    save.wait("visible ready", timeout=10)
    save.child_window(class_name="Edit", control_id=1001).set_edit_text(mas_name)
    save.set_focus()
    time.sleep(0.2)
    send_keys("{ENTER}")

    deadline = time.time() + 60
    while time.time() < deadline:
        if out.exists() and out.stat().st_size > 0:
            kill_mas2()
            return out
        time.sleep(0.5)

    kill_mas2()
    raise RuntimeError(f"MAS2 did not write {out}")


def safe_remove_installed_location(rf2_root: Path, component_name: str, version: str) -> None:
    installed_locations = rf2_root / "Installed" / "Locations"
    target = installed_locations / component_name / version
    resolved_target = target.resolve()
    resolved_root = installed_locations.resolve()
    if not str(resolved_target).lower().startswith(str(resolved_root).lower()):
        raise RuntimeError(f"Refusing to remove path outside Installed\\Locations: {target}")
    if target.exists():
        shutil.rmtree(target)


def build_component(
    rf2_root: Path,
    component_name: str,
    version: str,
    package_path: Path,
    mas_files: list[Path],
    install: bool,
) -> Path:
    for path in mas_files:
        if not path.exists():
            raise FileNotFoundError(f"MAS file not found: {path}")
    package_path.parent.mkdir(parents=True, exist_ok=True)
    if package_path.exists():
        package_path.unlink()

    _proc, app = connect_mas2(rf2_root, rf2_root)
    win = app.window(title_re=r".*MAS File Utility.*")
    win32gui.PostMessage(win.handle, win32con.WM_COMMAND, 32824, 0)

    app.window(title="rFactor2 Mod Packager").wait("visible ready", timeout=10)
    app.window(title="rFactor2 Mod Packager").child_window(
        title="Create Single Cmp Package", class_name="Button"
    ).click_input()
    cp = app.window(title="Create Component Package")
    cp.wait("visible ready", timeout=10)

    cp.child_window(class_name="Button", control_id=1048).click_input()
    name = app.window(title="Edit Component Name")
    name.wait("visible ready", timeout=10)
    name.child_window(class_name="Edit", control_id=1042).set_edit_text(component_name)
    name.child_window(class_name="Button", control_id=1).click_input()
    time.sleep(0.5)

    cp.child_window(class_name="Edit", control_id=1050).set_edit_text(version)
    cp.child_window(class_name="ComboBox", control_id=1060).wrapper_object().select("Location")

    cp.child_window(class_name="Button", control_id=1049).click_input()
    select_file_dialog(app, "Select location for component", str(package_path), edit_id=1148)
    time.sleep(0.5)

    for mas_file in mas_files:
        cp.child_window(class_name="Button", control_id=1054).click_input()
        time.sleep(0.4)
        select_file_dialog(app, "Select MAS files to add to component", str(mas_file), edit_id=1148)
        time.sleep(0.3)

    list_count = cp.child_window(class_name="SysListView32").wrapper_object().item_count()
    if list_count != len(mas_files):
        raise RuntimeError(f"Expected {len(mas_files)} MAS files in package list, got {list_count}")

    cp.child_window(title="Package", class_name="Button").click_input()
    deadline = time.time() + 90
    while time.time() < deadline:
        if package_path.exists() and package_path.stat().st_size > 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError(f"MAS2 did not write package: {package_path}")

    if install:
        safe_remove_installed_location(rf2_root, component_name, version)
        cp.child_window(title="Install", class_name="Button").click_input()
        op = app.window(title="Component Operation")
        op.wait("visible ready", timeout=30)
        message = " ".join(
            item.window_text()
            for item in op.descendants(class_name="Static")
            if item.window_text()
        )
        op.child_window(class_name="Button", control_id=2).click_input()
        if "Installed" not in message:
            raise RuntimeError(f"MAS2 install did not report success: {message}")

        installed = rf2_root / "Installed" / "Locations" / component_name / version
        deadline = time.time() + 20
        while time.time() < deadline:
            if installed.exists():
                break
            time.sleep(0.5)
        if not installed.exists():
            raise RuntimeError(f"MAS2 install did not create expected folder: {installed}")

    kill_mas2()
    return package_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and optionally install the BlackLake rFactor 2 component package.")
    parser.add_argument("--stage", choices=sorted(STAGES), default="250m")
    parser.add_argument("--project-root", type=Path, default=Path(r"C:\Users\Victor\Documents\PYTHON\RFactor2"))
    parser.add_argument("--rf2-root", type=Path, default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\rFactor 2"))
    parser.add_argument("--component-name", default="BlackLake_2026")
    parser.add_argument("--component-version", default="0.10")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    stage_root = args.project_root / "build" / "blacklake_package" / args.stage
    jobs = [
        (stage_root / "01_shared", "BlackLake_shared.mas"),
        (stage_root / "02_layout", f"BlackLake_{args.stage}.mas"),
        (stage_root / "03_gmt", "BlackLake_GMT.mas"),
        (stage_root / "04_maps", "BlackLake_MAPS.mas"),
    ]

    mas_files = [make_mas(args.rf2_root, source, mas_name) for source, mas_name in jobs]
    package_path = args.rf2_root / "Packages" / f"{args.component_name}_{args.component_version}.rfcmp"
    build_component(args.rf2_root, args.component_name, args.component_version, package_path, mas_files, args.install)

    print(f"Package: {package_path}")
    if args.install:
        print(f"Installed: {args.rf2_root / 'Installed' / 'Locations' / args.component_name / args.component_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
