"""Native float printing: values are IEEE single-precision bits, so the Windows printf shim must
decode them as float (it used to read them as a double and print 0.000000)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _native_output  # noqa: E402


def test_python_native_prints_float_variables_and_returns(tmp_path):
    src = (
        "x = 2.5\nprint(x)\n"
        "def half() -> float { return 0.5 }\nprint(half())\n"
        "y = half()\nprint(y)\n"
    )
    assert _native_output(src, tmp_path).split() == ["2.500000", "0.500000", "0.500000"]


def test_python_native_float_arithmetic(tmp_path):
    """addss/subss/mulss/divss on the 32-bit single-precision bit patterns, not addsd/.../divsd
    on 8 bytes that were never a valid double (that silently computed garbage)."""
    src = (
        "a = 2.5\nb = 1.5\n"
        "print(a + b)\nprint(a - b)\nprint(a * b)\nprint(a / b)\n"
    )
    assert _native_output(src, tmp_path).split() == ["4.000000", "1.000000", "3.750000", "1.666667"]


def test_python_native_float_compare(tmp_path):
    """comiss with dest=left, src=right, matching the setcc table below it. The operands used
    to be loaded reversed (dest=right, src=left), so every comparison tested the wrong direction."""
    src = (
        "a = 2.5\nb = 1.5\n"
        "if a < b { print(1) } else { print(0) }\n"
        "if a > b { print(1) } else { print(0) }\n"
        "if a <= a { print(1) } else { print(0) }\n"
        "if a == a { print(1) } else { print(0) }\n"
        "if b >= a { print(1) } else { print(0) }\n"
    )
    assert _native_output(src, tmp_path).split() == ["0", "1", "1", "1", "0"]
