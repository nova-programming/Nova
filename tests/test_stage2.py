"""Programs compiled by the stage-2 compiler (built by the self-hosted compiler) must behave like stage 1.

Regression: a parser desugar rewrote `len(x) > 0 and d.has(k)` into `len(x) > 0 and len(x) > d.has(k)`.
Python-built stage 1 never hit it, but stage 2 (compiled from the same source by the Nova parser)
crashed on every program containing a function.
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output  # noqa: E402

EXE = ".exe" if os.name == "nt" else ""

PROGRAM = (
    "import text\n"
    "data Point {\n    x: int\n    y: int\n}\n"
    "def fib(n) {\n    if n <= 1 { return n }\n    return fib(n - 1) + fib(n - 2)\n}\n"
    'def label(n) { return "n=" + str(n) }\n'
    "p = Point(y=2, x=1)\n"
    'd = {"k": 5}\n'
    "total = 0\n"
    "for i in range(4) { total = total + i }\n"
    "print(fib(10))\nprint(label(total))\nprint(p.x + p.y)\n"
    'if "k" in d and d["k"] == 5 { print("dict ok") }\n'
    'print(text.upper("done"))\n'
)
EXPECTED = ["55", "n=6", "3", "dict", "ok", "DONE"]


def _run(stage, name, source):
    exe, work, env = stage
    src = work / (name + ".nv")
    src.write_text(source, encoding="utf-8")
    out = work / (name + EXE)
    if out.exists():
        out.unlink()
    b = subprocess.run([str(exe), "build", str(src)], capture_output=True, text=True, timeout=300, cwd=work, env=env)
    assert out.exists(), b.stdout[-1500:] + b.stderr[-1500:]
    r = subprocess.run([str(out)], capture_output=True, text=True, timeout=60, cwd=work)
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def test_stage2_compiles_functions_and_new_syntax(stage2):
    assert _run(stage2, "st2_prog", PROGRAM) == EXPECTED


def test_stage1_and_stage2_agree(selfhost, stage2):
    stage1, work1, env = selfhost
    assert _run((stage1, work1, env), "st1_prog", PROGRAM) == _run(stage2, "st2_prog_b", PROGRAM)


def test_comparison_and_call_is_not_rewritten_as_chained_comparison(tmp_path):
    src = (
        'd = {"a": 1}\nx = 1\nflag = true\nxs = [1, 2]\n'
        'if x == 1 and flag { print("yes") } else { print("no") }\n'
        'if len(xs) > 0 and d.has("a") { print("both") } else { print("neither") }\n'
        'if x == 1 or 2 { print("lit-a") }\nif x == 3 or 1 { print("lit-b") }\n'
    )
    assert _vm_output(src).split() == ["yes", "both", "lit-a", "lit-b"]
