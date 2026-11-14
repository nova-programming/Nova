"""verify_selfhost.py: the one-command self-host gate (stage2 assembly must equal stage3)."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_compiler_reproduces_itself():
    if os.name == "nt" and not os.path.isdir(os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")):
        pytest.skip("64-bit GCC not found")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "verify_selfhost.py")], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    assert "SELF-HOST OK: stage2 == stage3" in r.stdout
