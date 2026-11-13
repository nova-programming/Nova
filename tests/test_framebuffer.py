import os
import subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_EXE = os.path.join(ROOT, "nova.exe" if os.name == "nt" else "nova")

def _run_build_and_exec(tmp_path, src_code: str, exe_name: str = "prog"):
    assert os.path.isfile(NOVA_EXE), f"nova.exe missing: {NOVA_EXE}"
    src_file = tmp_path / f"{exe_name}.nv"
    src_file.write_text(src_code, encoding="utf-8")
    out_exe = tmp_path / (f"{exe_name}.exe" if os.name == "nt" else exe_name)

    env = dict(os.environ)
    gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
    if os.path.isdir(gcc_bin):
        env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")

    build_res = subprocess.run(
        [NOVA_EXE, "build", str(src_file), "-o", str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert build_res.returncode == 0, f"Build failed:\nSTDOUT:\n{build_res.stdout}\nSTDERR:\n{build_res.stderr}"
    assert out_exe.exists(), "Output binary was not created"

    run_res = subprocess.run(
        [str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    return run_res

def test_framebuffer_lifecycle(tmp_path):
    src = """import buffer
import time

extern def gui_init_window(title: string, width: int, height: int) -> int
extern def gui_present_framebuffer(buffer_ptr: int, width: int, height: int)
extern def gui_get_mouse_x() -> int
extern def gui_get_mouse_y() -> int
extern def gui_key_down(keycode: int) -> int
extern def gui_mouse_down_btn(button: int) -> int
extern def gui_poll_events() -> int
extern def gui_close()

w = 640
h = 480
ok = gui_init_window("Nova Framebuffer Smoke Test", w, h)
print("WINDOW_INIT=" + str(ok))

if ok == 1 {
    # Allocate 32-bit RGBA framebuffer: w * h * 4 bytes
    pixel_count = w * h
    fb = new_buffer(pixel_count * 4)
    print("FB_ALLOC_SIZE=" + str(fb.size))

    # Fill with deep slate blue 0x001e1e2e
    fb.fill_i32(pixel_count, 1973806)

    # Draw a 100x100 bright emerald square at (50, 50)
    # Emerald color: 0x0022c55e = 2278750
    y = 50
    while y < 150 {
        x = 50
        while x < 150 {
            idx = y * w + x
            fb.set_i32(idx, 2278750)
            x = x + 1
        }
        y = y + 1
    }

    # Present direct to screen via StretchDIBits
    gui_present_framebuffer(fb.handle, w, h)
    print("FRAMEBUFFER_PRESENTED")

    # Poll input state
    mx = gui_get_mouse_x()
    my = gui_get_mouse_y()
    k_esc = gui_key_down(27) # VK_ESCAPE
    m_left = gui_mouse_down_btn(0)
    print("INPUT_POLL_OK")

    # Event pump for 5 frames
    frame = 0
    while frame < 5 {
        _ = gui_poll_events()
        sleep_ms(16)
        frame = frame + 1
    }

    gui_close()
    fb.release()
    print("CLEAN_TEARDOWN_OK")
}
"""
    res = _run_build_and_exec(tmp_path, src, "test_fb")
    assert res.returncode == 0
    assert "WINDOW_INIT=1" in res.stdout
    assert "FB_ALLOC_SIZE=1228800" in res.stdout
    assert "FRAMEBUFFER_PRESENTED" in res.stdout
    assert "INPUT_POLL_OK" in res.stdout
    assert "CLEAN_TEARDOWN_OK" in res.stdout

