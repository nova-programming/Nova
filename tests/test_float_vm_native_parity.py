"""VM/native differential coverage for floats (see ROADMAP.md's test policy: new language
features should add cases to the VM/native parity suite). This is a dedicated file rather than
an addition to tests/test_diff_fuzz.py because that fuzzer's atom()/wrap() machinery is built
entirely around integer invariants (modulo-wrapping values into [0, 999], bitwise ops, floor vs
truncating division) that don't apply to floats; these cases are hand-written instead.

VM output uses Python's float repr ("-0.6"); native uses the runtime's "%.6f" (via printf) --
different text for the same value, so lines are compared as parsed floats (with a small
tolerance) rather than as exact strings. Boolean/int lines (from comparisons) are compared
as exact text, since both pipelines agree on integer formatting.

Regression coverage:
- float arithmetic/compare precision and operand order (movsd/comisd -> movss/comiss; reversed
  compare operands) in bootstrap's native codegen.
- float literal decoding (`float_str_to_hex`'s digit loop reading `.value_byte`, broken by a
  missing `ptr` size-override keyword) and the Compare float-branch nesting bug in the
  self-hosted backend.
- unary `-` on a float applied `neg rax` (two's-complement integer negation) to the IEEE-754
  bit pattern instead of flipping the sign bit, corrupting the value entirely.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output, _native_output  # noqa: E402

PROGRAM = (
    "x = 2.5\ny = -1.5\n"
    "print(x + y)\nprint(x - y)\nprint(x * y)\nprint(y / x)\n"
    "print(-x)\nprint(-y)\n"
    "if y < 0.0 { print(1) } else { print(0) }\n"
    "if -x < 0.0 { print(1) } else { print(0) }\n"
    "if x > y { print(1) } else { print(0) }\n"
    "if x <= x { print(1) } else { print(0) }\n"
    "z = 0.0\nprint(-z)\n"
)

# Each line is either a float value (compared numerically) or an exact int/bool line.
FLOAT_LINE_INDICES = {0, 1, 2, 3, 4, 5, 10}
INT_LINE_INDICES = {6, 7, 8, 9}


def _check_parity(vm_lines, native_lines):
    assert len(vm_lines) == len(native_lines) == 11
    for i in FLOAT_LINE_INDICES:
        assert float(vm_lines[i]) == pytest.approx(float(native_lines[i]), abs=1e-5), (
            f"line {i}: vm={vm_lines[i]!r} native={native_lines[i]!r}"
        )
    for i in INT_LINE_INDICES:
        assert vm_lines[i] == native_lines[i], f"line {i}: vm={vm_lines[i]!r} native={native_lines[i]!r}"


def test_vm_native_float_arithmetic_and_unary_minus_agree(tmp_path):
    vm_lines = _vm_output(PROGRAM).split()
    native_lines = _native_output(PROGRAM, tmp_path).split()
    _check_parity(vm_lines, native_lines)


def test_native_negative_zero_is_negative(tmp_path):
    """-0.0 must keep its sign bit (printf prints "-0.000000"), not collapse to positive zero --
    the bug this guards against (two's-complement neg on the bit pattern) happened to leave
    +0.0's bits alone, so a positive-zero assertion wouldn't have caught the real-value cases."""
    out = _native_output("z = 0.0\nprint(-z)\n", tmp_path).strip()
    assert out.startswith("-"), f"expected a negative-signed zero, got {out!r}"
