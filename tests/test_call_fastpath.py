"""Tests for the self-hosted x86_64 backend's Nova-to-Nova call fast path.

Unlike test_native_exec.py (which uses the Python bootstrap compiler), these
build the self-hosted compiler (stdlib/*.nv) once and compile test programs
with it, because the fast path lives in stdlib/backend/x86_64/*.nv.
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "bootstrap", "main.py")
EXE = ".exe" if os.name == "nt" else ""


def _gcc_env():
    """Return an env whose first gcc is 64-bit, or None if there isn't one."""
    env = dict(os.environ)
    dirs = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(os.path.join(local, "nova", "gcc", "bin"))
    dirs.append(os.path.join(os.path.expanduser("~"), ".nova", "gcc", "bin"))
    dirs.append(os.path.join(ROOT, "gcc", "bin"))
    for d in dirs:
        if os.path.isdir(d):
            env["PATH"] = d + os.pathsep + env.get("PATH", "")
            break
    gcc = shutil.which("gcc", path=env["PATH"])
    if not gcc:
        return None
    out = subprocess.run([gcc, "-dumpmachine"], capture_output=True, text=True).stdout
    if "x86_64" not in out and "amd64" not in out.lower():
        return None
    return env


@pytest.fixture(scope="module")
def selfhost(tmp_path_factory):
    if platform.machine().lower() not in ("amd64", "x86_64"):
        pytest.skip("x86_64 host required")
    env = _gcc_env()
    if env is None:
        pytest.skip("64-bit GCC not found")
    work = tmp_path_factory.mktemp("selfhost")
    shutil.copytree(os.path.join(ROOT, "stdlib"), work / "stdlib")
    for name in ("nova.nv", "runtime.c"):
        shutil.copy(os.path.join(ROOT, name), work / name)
    stage1 = work / ("stage1" + EXE)
    r = subprocess.run(
        [sys.executable, MAIN_PY, "build", os.path.join(ROOT, "nova.nv"), "-o", str(stage1)],
        capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
    )
    assert r.returncode == 0 and stage1.exists(), r.stdout[-2000:] + r.stderr[-2000:]
    return stage1, work, env


def _compile_run(selfhost, source, name):
    stage1, work, env = selfhost
    src = work / (name + ".nv")
    src.write_text(source, encoding="utf-8")
    exe = work / (name + EXE)
    if exe.exists():
        exe.unlink()
    b = subprocess.run([str(stage1), "build", str(src)], capture_output=True, text=True,
                       timeout=300, cwd=work, env=env)
    assert exe.exists(), b.stdout[-2000:] + b.stderr[-2000:]
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    asm = (work / (name + ".nv.s")).read_text()
    return r, asm


def test_internal_calls_skip_c_interop_frame(selfhost):
    r, asm = _compile_run(selfhost, "def f(n) { return n + 1 }\nprint(f(41))\n", "fp_asm")
    assert r.returncode == 0 and r.stdout.strip() == "42"
    lines = [ln.strip() for ln in asm.splitlines()]
    i = lines.index("call _f")
    # internal call: nothing but arg-register pops before the call, no shadow-space reserve
    assert "sub rsp, 32" not in lines[i - 3:i]
    assert lines[i + 1] != "mov rsp, rbp"
    # C runtime calls keep the interop frame
    j = next(k for k, ln in enumerate(lines) if ln.startswith("call _printf") or ln.startswith("call _print"))
    assert "sub rsp, 32" in lines[j - 6:j]


def test_recursion_and_mutual_recursion(selfhost):
    src = (
        "def fib(n) {\n    if n <= 1 { return n }\n    return fib(n - 1) + fib(n - 2)\n}\n"
        "def even(n) {\n    if n == 0 { return 1 }\n    return odd(n - 1)\n}\n"
        "def odd(n) {\n    if n == 0 { return 0 }\n    return even(n - 1)\n}\n"
        "print(fib(20))\nprint(even(10))\nprint(odd(7))\n"
    )
    r, _ = _compile_run(selfhost, src, "fp_rec")
    assert r.returncode == 0
    assert r.stdout.split() == ["6765", "1", "1"]


def test_six_args_nested_calls_and_register_locals(selfhost):
    src = (
        "def add6(a, b, c, d, e, f) {\n    return a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6\n}\n"
        "def inc(x) { return x + 1 }\n"
        "def many_locals(n) {\n    a = n\n    b = a + 1\n    c = b + 1\n    d = c + 1\n"
        "    e = inc(d)\n    return a + b + c + d + e\n}\n"
        "print(add6(1, 2, 3, 4, 5, 6))\n"
        "print(add6(inc(0), inc(1), inc(2), inc(3), inc(4), inc(5)))\n"
        "print(many_locals(10))\n"
    )
    r, _ = _compile_run(selfhost, src, "fp_args")
    assert r.returncode == 0
    assert r.stdout.split() == ["91", "91", "60"]


def test_internal_then_c_calls_keep_stack_aligned(selfhost):
    # strings/lists go through C runtime helpers (alignment-sensitive) after internal calls
    src = (
        "def greet(name: string) -> string {\n    return \"hi \" + name\n}\n"
        "def deep(n) -> string {\n    if n == 0 { return greet(\"x\") }\n    return deep(n - 1)\n}\n"
        "xs = [3, 1, 2]\nxs.append(4)\n"
        "print(deep(5))\nprint(len(xs))\nprint(deep(6))\n"
    )
    r, _ = _compile_run(selfhost, src, "fp_align")
    assert r.returncode == 0
    assert r.stdout.split("\n")[:3] == ["hi x", "4", "hi x"]
