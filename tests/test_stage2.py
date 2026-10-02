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


def test_stage2_lays_out_data_structs_like_stage1(selfhost, stage2):
    """Regression: len(state.struct_fields[si]) was compiled as strlen by the self-hosted backend,
    so a self-built compiler gave every struct two fields' worth of offsets (fields 2.. aliased)."""
    src = (
        "data J {\n    aa: int\n    bb: int\n    cc: int\n    dd: int\n    ee: int\n}\n"
        "v = J()\nv.aa = 1\nv.bb = 2\nv.cc = 3\nv.dd = 4\nv.ee = 5\n"
        "print(v.aa + v.bb * 10 + v.cc * 100 + v.dd * 1000 + v.ee * 10000)\n"
    )
    stage1, work1, env = selfhost
    assert _run((stage1, work1, env), "lay1", src) == _run(stage2, "lay2", src) == ["54321"]


def _oob_lines(stage, name, source):
    """The line numbers written to _oob_line (bounds-check records) in the emitted assembly."""
    exe, work, env = stage
    _run(stage, name, source)
    asm = (work / (name + ".nv.s")).read_text()
    out = []
    marker = "lea rbx, [rip + _oob_line]"
    for i, line in enumerate(asm.splitlines()):
        if marker in line:
            out.append(asm.splitlines()[i + 1].strip())
    return out


def test_stage2_records_bounds_check_lines_like_stage1(selfhost, stage2):
    """Regression: the type checker did not visit the operand of str(...), so `node.line` inside
    str(node.line) had no struct type and the self-hosted backend read Token.line's offset instead
    of AstNode.line's: stage 2 wrote `mov qword ptr [rbx], 0` for every bounds-check line record."""
    src = "xs = [1, 2, 3]\n\nxs[1] = 5\nprint(xs[2])\n"
    stage1, work1, env = selfhost
    l1 = _oob_lines((stage1, work1, env), "oob1", src)
    l2 = _oob_lines(stage2, "oob2", src)
    assert l1 and l1 == l2
    assert "mov qword ptr [rbx], 3" in l1
