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
