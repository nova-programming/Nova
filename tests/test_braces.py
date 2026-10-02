r"""Literal braces in string literals: \{ and \} escape interpolation, in every pipeline.

Programs are written as raw strings so the backslashes reach the Nova lexer untouched.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output, _native_output  # noqa: E402

BRACE_PROGRAM = (
    "x = 5\n"
    r'print("\{\"a\": 1\}")' "\n"
    'print("x = {x}")\n'
    r'print("a\{b\}c {x} d")' "\n"
    r'print("\\{x}")' "\n"
)
# the last line is an escaped backslash followed by a real interpolation: backslash then 5
EXPECTED = ['{"a":', "1}", "x", "=", "5", "a{b}c", "5", "d", "\\5"]


def test_brace_escapes_all_pipelines(tmp_path, selfhost_run):
    assert _vm_output(BRACE_PROGRAM).split() == EXPECTED
    assert _native_output(BRACE_PROGRAM, tmp_path).split() == EXPECTED
    r, _ = selfhost_run(BRACE_PROGRAM, "braces_prog")
    assert r.returncode == 0 and r.stdout.split() == EXPECTED


def test_json_text_can_be_written_inline(selfhost_run):
    program = (
        "import json\n"
        r'doc = json.parse("\{\"a\": [1, 2, \{\"b\": true\}]\}")' "\n"
        "print(json.kind(doc))\n"
        'print(json.asInt(json.at(json.get(doc, "a"), 1)))\n'
        'print(json.asBool(json.get(json.at(json.get(doc, "a"), 2), "b")))\n'
    )
    assert _vm_output(program).split() == ["5", "2", "1"]
    r, _ = selfhost_run(program, "braces_json")
    assert r.returncode == 0 and r.stdout.split() == ["5", "2", "1"]
