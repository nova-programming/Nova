import os
import subprocess
import sys
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_EXE = os.path.join(REPO_ROOT, "nova.exe")


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_gui_raw_execution():
    raw_test_src = os.path.join(REPO_ROOT, "tests", "test_gui_raw.nv")
    assert os.path.isfile(raw_test_src), f"Missing {raw_test_src}"
    
    # Run using native nova.exe
    result = subprocess.run(
        [NOVA_EXE, "run", raw_test_src],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT
    )
    assert result.returncode == 0, f"Raw GUI execution failed:\n{result.stderr}\n{result.stdout}"
    assert "Frame presented successfully!" in result.stdout
    assert "GUI closed cleanly." in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_gui_counter_showcase():
    counter_src = os.path.join(REPO_ROOT, "examples", "gui_counter.nv")
    assert os.path.isfile(counter_src), f"Missing {counter_src}"
    
    result = subprocess.run(
        [NOVA_EXE, "run", counter_src, "--test"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT
    )
    assert result.returncode == 0, f"GUI counter execution failed:\n{result.stderr}\n{result.stdout}"
    assert "Demo completed successfully!" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_gui_mouse_cords():
    test_src = os.path.join(REPO_ROOT, "tests", "test_mouse_cords.nv")
    with open(test_src, "w") as f:
        f.write('import gui\ncords = get_mouseCord()\nprint("cords len: " + str(len(cords)))\nprint("cords x: " + str(cords[0]))\n')
    try:
        result = subprocess.run(
            [NOVA_EXE, "run", test_src],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT
        )
        assert result.returncode == 0, f"Mouse cords test failed:\n{result.stderr}\n{result.stdout}"
        assert "cords len: 2" in result.stdout
        assert "cords x: 0" in result.stdout
    finally:
        if os.path.exists(test_src):
            os.remove(test_src)
        exe = test_src.replace(".nv", ".exe")
        if os.path.exists(exe):
            os.remove(exe)
