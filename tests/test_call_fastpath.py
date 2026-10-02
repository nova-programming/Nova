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


def test_peephole_cleans_generated_code(selfhost):
    src = (
        "def fib(n) {\n    if n <= 1 { return n }\n    return fib(n - 1) + fib(n - 2)\n}\n"
        "def total(n) {\n    s = 0\n    i = 0\n    while i <= n {\n        s = s + i\n        i = i + 1\n    }\n    return s\n}\n"
        "print(fib(15))\nprint(total(100))\n"
    )
    r, asm = _compile_run(selfhost, src, "fp_peep")
    assert r.returncode == 0
    assert r.stdout.split() == ["610", "5050"]
    lines = asm.splitlines()
    regs = {"rax", "rbx", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"}
    for a, b in zip(lines, lines[1:]):
        if a.startswith("    push ") and b.startswith("    pop "):
            assert not (a[9:] in regs and b[8:] in regs), f"unfused push/pop: {a.strip()} / {b.strip()}"
        if a == "    ret" or a.startswith("    jmp "):
            assert not (b.startswith("    ") and not b.startswith("    .")), f"dead code after {a.strip()}: {b.strip()}"


def test_compare_and_branch_fusion(selfhost_run):
    src = (
        "def classify(n) {\n"
        "    r = 0\n"
        "    if n == 5 { r = r + 1 }\n"
        "    if n != 5 { r = r + 2 }\n"
        "    if n < 5 { r = r + 4 }\n"
        "    if n <= 5 { r = r + 8 }\n"
        "    if n > 5 { r = r + 16 }\n"
        "    if n >= 5 { r = r + 32 }\n"
        "    if n > 2 and n < 8 { r = r + 64 }\n"
        "    if n < 2 or n > 8 { r = r + 128 }\n"
        "    return r\n"
        "}\n"
        "def count_to(limit) {\n    i = 0\n    while i < limit { i = i + 1 }\n    return i\n}\n"
        "for k in range(11) { print(classify(k)) }\n"
        "print(count_to(1000))\n"
    )

    def expected(n):
        return ((n == 5) * 1 + (n != 5) * 2 + (n < 5) * 4 + (n <= 5) * 8 + (n > 5) * 16 + (n >= 5) * 32
                + (2 < n < 8) * 64 + (n < 2 or n > 8) * 128)

    r, asm = selfhost_run(src, "fp_fusion")
    assert r.returncode == 0
    assert r.stdout.split() == [str(expected(k)) for k in range(11)] + ["1000"]
    lines = [ln.strip() for ln in asm.splitlines()]
    # statement-level conditions branch straight off the compare...
    for i, ln in enumerate(lines):
        if ln.startswith("set") and ln.endswith(" al") and i + 3 < len(lines):
            # ...so a setCC/movzx/cmp 0/jcc test may only survive where the value is reused (and/or)
            assert not lines[i + 3].split()[-1].startswith(("L_else_", "L_loop_end_")), lines[i:i + 4]
