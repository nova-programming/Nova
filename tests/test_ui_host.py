"""One `ui` library for desktop and Nova OS.

ui.nv writes a display list and leaves the window calls to a backend: `import ui_backend` resolves to ui_os (system
calls, for --os bare / --os nova) or ui_host (Win32 GDI, for native host builds), the same way os_impl picks the
operating system module.
"""
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = ".exe" if os.name == "nt" else ""
OS_DIR = os.path.join(os.path.dirname(ROOT), "baremetal_os")


def _read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


def test_ui_has_no_platform_calls_of_its_own():
    ui = _read("stdlib/ui.nv")
    assert "import ui_backend" in ui
    assert "extern def nova_create_window" not in ui          # those moved into the backends
    os_backend = _read("stdlib/ui_os.nv")
    host_backend = _read("stdlib/ui_host.nv")
    for name in ("nova_create_window", "nova_damage_window", "nova_poll_event", "nova_destroy_window", "nova_sleep"):
        assert name in os_backend and name in host_backend, f"both backends must provide {name}"
    assert "gui_init_window" in host_backend and "gui_init_window" not in os_backend


def test_the_host_backend_reserves_the_fixed_page_on_a_64k_boundary():
    # Regression: VirtualAlloc(0x74C000) rounds down to 0x740000, so checking the returned address against 0x74C000
    # made every window fail to open.
    host = _read("stdlib/ui_host.nv")
    assert "VirtualAlloc(0x740000, 0x20000" in host
    assert "page != 0x740000" in host


@pytest.mark.skipif(os.name != "nt", reason="the desktop backend is Win32 GDI")
def test_a_ui_program_runs_in_a_desktop_window(selfhost):
    stage1, work, env = selfhost
    shutil.copy(os.path.join(ROOT, "examples", "ui_counter.nv"), work / "ui_counter.nv")
    exe = work / ("ui_counter" + EXE)
    if exe.exists():
        exe.unlink()
    b = subprocess.run([str(stage1), "build", str(work / "ui_counter.nv")], capture_output=True, text=True,
                       timeout=300, cwd=str(work), env=env)
    assert exe.exists(), b.stdout[-1500:] + b.stderr[-1500:]
    r = subprocess.run([str(exe), "--test"], capture_output=True, text=True, timeout=60, cwd=str(work))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Demo completed successfully!" in r.stdout


@pytest.mark.skipif(not os.path.exists(os.path.join(OS_DIR, "user.ld")), reason="Nova OS checkout not found")
def test_the_same_library_builds_an_os_package(selfhost, tmp_path):
    stage1, work, env = selfhost
    env = dict(env)
    env["NOVA_OS_DIR"] = OS_DIR
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    shutil.copy(os.path.join(OS_DIR, "user", "ulib.nv"), app_dir / "ulib.nv")
    shutil.copy(os.path.join(OS_DIR, "user", "counter_ui.nv"), app_dir / "counter_ui.nv")
    env["NOVA_PATH"] = str(app_dir)
    out = tmp_path / "counter.nva"
    r = subprocess.run([str(stage1), "build", str(app_dir / "counter_ui.nv"), "--os", "nova", "-o", str(out)],
                       capture_output=True, text=True, timeout=300, cwd=str(app_dir), env=env)
    if not out.exists() and ("objcopy" in (r.stdout + r.stderr).lower() or "not produced" in r.stdout):
        pytest.skip("toolchain for ring-3 ELF packaging not available")
    assert out.exists(), r.stdout[-1500:] + r.stderr[-1500:]
    assert "ui_host" not in r.stdout and "gui_init_window" not in r.stdout    # the OS build never pulls in the desktop backend
    assert "Tokenizing... ui_os" in r.stdout
