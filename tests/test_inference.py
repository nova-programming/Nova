"""Return-type inference: un-annotated functions that return strings print as strings natively."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output, _native_output  # noqa: E402

PROGRAM = (
    'def f() { return "x" }\n'
    'def g(n) {\n    if n == 0 { return "base" }\n    return g(n - 1)\n}\n'
    'def greet(name: string) -> string { return "hi " + name }\n'
    'def deep(n) {\n    if n == 0 { return greet("x") }\n    return deep(n - 1)\n}\n'
    'def wrap(s) { return "<" + s + ">" }\n'
    'def inc(n) { return n + 1 }\n'
    'def mixed(n) {\n    if n > 0 { return "pos" }\n    return n\n}\n'
    'def explicit(n) -> int { return n }\n'
    'print(f())\nprint(g(3))\nprint(deep(5))\nprint(wrap("z"))\nmsg = wrap("y")\nprint(msg + "!")\n'
    'print(inc(1))\nprint(mixed(1))\nprint(explicit(7))\n'
)
EXPECTED = ["x", "base", "hi", "x", "<z>", "<y>!", "2", "pos", "7"]


def test_string_returns_all_pipelines(tmp_path, selfhost_run):
    assert _vm_output(PROGRAM).split() == EXPECTED
    assert _native_output(PROGRAM, tmp_path).split() == EXPECTED
    r, _ = selfhost_run(PROGRAM, "infer_prog")
    assert r.returncode == 0 and r.stdout.split() == EXPECTED


def test_python_inference_unit():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bootstrap"))
    import infer
    from lexer.tokenizer import tokenize
    from parser.parser import Parser
    ast = Parser(tokenize(
        'def a() { return "x" }\ndef b(n) { return n }\ndef c() -> int { return "x" }\n'
        'def d(n) {\n    if n { return "p" }\n    return 1\n}\n'
    )).parse()
    result = infer.infer_return_types(ast)
    assert result == {"a": "string"}          # only the unambiguous one
    names = {f.name: f.return_type for f in ast}
    assert names["c"] == "int"                 # explicit annotation untouched
    assert not names["b"] and not names["d"]   # unknown / conflicting returns stay un-annotated
