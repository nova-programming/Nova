"""Bitwise operators (| ^ ~ & << >>) agree in the VM, Python-native and self-hosted builds.

Regression: the Python bootstrap backends had no `|`, `^` or `~`, so a Python-built stage-1 compiler
folded constant `43 | 23` to 43 (and `43 ^ 23` to 43) and `a | b` on variables returned `a`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output, _native_output  # noqa: E402

PROGRAM = (
    "a = 43\nb = 23\n"
    "print(a | b)\nprint(a & b)\nprint(a ^ b)\nprint(a << 2)\nprint(a >> 2)\nprint(~a)\n"
    "print(43 | 23)\nprint(43 & 23)\nprint(43 ^ 23)\nprint((43 | 23) + (17 / 9))\n"
)
EXPECTED = ["63", "3", "60", "172", "10", "-44", "63", "3", "60", "64"]


def test_bit_operators_all_pipelines(tmp_path, selfhost_run):
    assert _vm_output(PROGRAM).split() == EXPECTED
    assert _native_output(PROGRAM, tmp_path).split() == EXPECTED
    r, _ = selfhost_run(PROGRAM, "bitops_prog")
    assert r.returncode == 0 and r.stdout.split() == EXPECTED
