"""3B syntax simplifications: range loops, data constructors, dict shortcuts.

Each form is run through the VM, the Python-bootstrap native build, and the
self-hosted compiler, and must match the expected output (and the old syntax).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_names import _vm_output, _native_output  # noqa: E402


def all_pipelines(source, tmp_path, selfhost_run, name):
    vm = _vm_output(source).split()
    native = _native_output(source, tmp_path).split()
    r, asm = selfhost_run(source, name)
    assert r.returncode == 0, r.stderr
    return vm, native, r.stdout.split(), asm


# ---- range loops -----------------------------------------------------------------

RANGE_PROGRAM = (
    "for i in range(3) { print(i) }\n"
    "for i in range(2, 5) { print(i) }\n"
    "for i in range(0, 10, 4) { print(i) }\n"
    "for i in range(5, 0, -2) { print(i) }\n"
    "n = 4\nfor i in range(n) { print(i * 10) }\n"
    "xs = [7, 8, 9]\nfor i in range(len(xs)) { print(xs[i]) }\n"
    "for x in xs { print(x + 100) }\n"
)
RANGE_EXPECTED = ("0 1 2 2 3 4 0 4 8 5 3 1 0 10 20 30 7 8 9 107 108 109").split()


def test_range_loops_all_pipelines(tmp_path, selfhost_run):
    vm, native, selfhost, _ = all_pipelines(RANGE_PROGRAM, tmp_path, selfhost_run, "sugar_range")
    assert vm == native == selfhost == RANGE_EXPECTED


def test_range_lowers_to_the_same_code_as_to_step(selfhost_run):
    new = "xs = [0, 0, 0]\nfor i in range(len(xs)) { xs[i] = i }\nprint(xs[2])\n"
    old = "xs = [0, 0, 0]\nfor i = 0 to len(xs) - 1 { xs[i] = i }\nprint(xs[2])\n"
    r1, asm1 = selfhost_run(new, "sugar_range_new")
    r2, asm2 = selfhost_run(old, "sugar_range_old")
    assert r1.stdout.split() == r2.stdout.split() == ["2"]
    assert len(asm1.splitlines()) == len(asm2.splitlines())  # identical lowering, so BCE still applies


def test_range_errors_are_clear():
    from test_native_exec import _run_vm
    bad = _run_vm("n = 2\nfor i in range(0, 10, n) { print(i) }\n")
    assert bad.returncode != 0 and "step must be an integer literal" in bad.stdout + bad.stderr
    zero = _run_vm("for i in range(0, 10, 0) { print(i) }\n")
    assert zero.returncode != 0 and "must not be zero" in zero.stdout + zero.stderr


def test_downto_counts_down_in_native_builds(tmp_path, selfhost_run):
    """Regression: the Python-bootstrap native backends added the step in `downto` loops (infinite loop)."""
    src = "for i = 5 downto 1 step 2 { print(i) }\nfor j = 3 downto 1 { print(j) }\n"
    vm, native, selfhost, _ = all_pipelines(src, tmp_path, selfhost_run, "sugar_downto")
    assert vm == native == selfhost == ["5", "3", "1", "3", "2", "1"]


# ---- data constructors -------------------------------------------------------------

DATA_PROGRAM = (
    "data Point {\n    x: int\n    y: int\n}\n"
    "data Person {\n    name: string\n    age: int\n}\n"
    "p = Point(1, 2)\nprint(p.x)\nprint(p.y)\n"
    "q = Point(y=9, x=4)\nprint(q.x * 10 + q.y)\n"
    "r = Point(7)\nprint(r.y)\n"
    "z = Point()\nz.x = 5\nprint(z.x)\n"
    'who = Person("Ada", 36)\nprint(who.name)\nprint(who.age)\n'
)
DATA_EXPECTED = ["1", "2", "49", "0", "5", "Ada", "36"]


def test_data_constructors_all_pipelines(tmp_path, selfhost_run):
    vm, native, selfhost, _ = all_pipelines(DATA_PROGRAM, tmp_path, selfhost_run, "sugar_data")
    assert vm == native == selfhost == DATA_EXPECTED


def test_data_literal_style_without_values_still_works():
    out = _vm_output("data P {\n    x: int\n}\na = P()\na.x = 3\nprint(a.x)\n")
    assert out.split() == ["3"]


def test_data_constructor_errors():
    from test_native_exec import _run_vm
    too_many = _run_vm("data P {\n    x: int\n}\nq = P(1, 2)\n")
    assert too_many.returncode != 0 and "1 field(s) but 2 values" in too_many.stdout + too_many.stderr
    bad_kw = _run_vm("data P {\n    x: int\n}\nq = P(z=1)\n")
    assert bad_kw.returncode != 0 and "no field 'z'" in bad_kw.stdout + bad_kw.stderr
    mixed = _run_vm("data P {\n    x: int\n    y: int\n}\nq = P(1, y=2)\n")
    assert mixed.returncode != 0 and "cannot mix" in mixed.stdout + mixed.stderr


# ---- dict shortcuts ------------------------------------------------------------------

DICT_PROGRAM = (
    'd = {"a": 1, "b": 2}\n'
    'd["c"] = 3\n'
    'k = "b"\n'
    'print(d["a"] + d[k] + d["c"])\n'
    'if "a" in d { print("has a") }\n'
    'if "z" in d { print("has z") } else { print("no z") }\n'
    'if "z" not in d { print("z missing") }\n'
    'if k in d and "c" in d { print("both") }\n'
    'for x in [1, 2] { print(x) }\n'
)
DICT_EXPECTED = ["6", "has", "a", "no", "z", "z", "missing", "both", "1", "2"]


def test_dict_index_and_in_all_pipelines(tmp_path, selfhost_run):
    vm, native, selfhost, _ = all_pipelines(DICT_PROGRAM, tmp_path, selfhost_run, "sugar_dict")
    assert vm == native == selfhost == DICT_EXPECTED


def test_in_on_lists_and_strings_is_a_clear_error():
    from test_native_exec import _run_vm
    for src in ('xs = [1, 2]\nif 1 in xs { print(1) }\n', 's = "abc"\nif "a" in s { print(1) }\n'):
        r = _run_vm(src)
        assert r.returncode != 0 and "dictionaries only" in r.stdout + r.stderr
