"""VM regression: statement-level calls/method calls leave their result on the operand stack; a function that
did so corrupted the caller's pending operands (`2 > f()` compared garbage). Found by differential fuzzing."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output  # noqa: E402

PROGRAM = (
    "def leak() {\n    xs = [1]\n    xs.append(2)\n    xs.append(3)\n    return 0\n}\n"
    "def other() { return 5 }\n"
    "def noisy() {\n    other()\n    other()\n    return 7\n}\n"
    'if 2 > leak() { print("ok1") } else { print("bad1") }\n'
    'if not (2 > leak()) { print("bad2") } else { print("ok2") }\n'
    "print(10 + noisy() * 2)\n"
)


def test_calls_do_not_corrupt_callers_operand_stack():
    assert _vm_output(PROGRAM).split() == ["ok1", "ok2", "24"]
