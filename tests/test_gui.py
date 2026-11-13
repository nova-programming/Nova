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
@pytest.mark.parametrize("example", ["ui_counter.nv", "ui_widgets.nv"])
def test_ui_examples_run_on_the_desktop(example):
    src = os.path.join(REPO_ROOT, "examples", example)
    assert os.path.isfile(src), f"Missing {src}"
    result = subprocess.run([NOVA_EXE, "run", src, "--test"], capture_output=True, text=True, timeout=60, cwd=REPO_ROOT)
    assert result.returncode == 0, example + " failed: " + result.stderr + result.stdout
    assert "Demo completed successfully!" in result.stdout
