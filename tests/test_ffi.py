import os
import subprocess
import sys
import tempfile
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(REPO_ROOT, "bootstrap", "main.py")


def _run_native(source: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "test_ffi.nv")
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


def test_extern_lib_linking_and_call():
    if os.name == "nt":
        code = """
extern "kernel32" def SetLastError(code: int) -> int
extern "kernel32" def GetLastError() -> int

SetLastError(1234)
val = GetLastError()
print(val)
"""
    else:
        code = """
extern def puts(s: string) -> int

puts("hello from extern libc")
"""
    lines = _run_native(code)
    if os.name == "nt":
        assert lines == ["1234"]
    else:
        assert "hello from extern libc" in lines


def test_dynamic_ffi_load_and_dispatch():
    if os.name == "nt":
        code = """
import ffi

lib = ffi.load("kernel32.dll")
if lib.handle != 0 {
    print("handle: ok")
}

fn = ffi.symbol(lib, "GetCurrentProcessId")
if fn != 0 {
    pid = ffi.call0(fn)
    if pid > 0 {
        print("pid: ok")
    }
}

ffi.unload(lib)
print("unload: ok")
"""
        lines = _run_native(code)
        assert lines == ["handle: ok", "pid: ok", "unload: ok"]
