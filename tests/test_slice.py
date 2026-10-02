import os
import subprocess
import sys
import tempfile
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(REPO_ROOT, "bootstrap", "main.py")


def _run_native(source: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "test_slice.nv")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(source)

        res_build = subprocess.run(
            [sys.executable, MAIN_PY, "build", src_path],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=REPO_ROOT
        )
        assert res_build.returncode == 0, f"Build failed:\nSTDOUT:\n{res_build.stdout}\nSTDERR:\n{res_build.stderr}"

        exe_path = src_path.rsplit(".", 1)[0]
        if os.name == "nt":
            exe_path += ".exe"

        assert os.path.isfile(exe_path), f"Executable not found at {exe_path}"

        res_run = subprocess.run(
            [exe_path],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmpdir
        )
        assert res_run.returncode == 0, f"Execution failed:\n{res_run.stderr}"
        return res_run.stdout.strip().splitlines()


def test_slice_from_str_and_sub():
    code = """
import slice

s = "Nova Zero-Copy Slices"
sl = slice.from_str(s)
print(sl.len)

sub1 = slice.sub(sl, 0, 4)
print(slice.to_str(sub1))

sub2 = slice.sub(sl, 5, 14)
print(slice.to_str(sub2))
"""
    lines = _run_native(code)
    assert lines == ["21", "Nova", "Zero-Copy"]


def test_slice_equals_and_find():
    code = """
import slice

s = "Nova Systems Programming"
sl = slice.from_str(s)

sub1 = slice.sub(sl, 0, 4)
if slice.equals_str(sub1, "Nova") {
    print("eq: yes")
} else {
    print("eq: no")
}

if slice.starts_with_str(sl, "Nova") {
    print("starts: yes")
}

if slice.ends_with_str(sl, "Programming") {
    print("ends: yes")
}

idx = slice.find_str(sl, "Systems")
print(idx)
"""
    lines = _run_native(code)
    assert lines == ["eq: yes", "starts: yes", "ends: yes", "5"]


def test_slice_byte_at():
    code = """
import slice

s = "ABC"
sl = slice.from_str(s)
print(slice.byte_at(sl, 0))
print(slice.byte_at(sl, 1))
print(slice.byte_at(sl, 2))
print(slice.byte_at(sl, 3))
"""
    lines = _run_native(code)
    assert lines == ["65", "66", "67", "-1"]
