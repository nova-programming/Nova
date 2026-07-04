import sys, os, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bootstrap'))

from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from vm.compiler import Compiler
from vm.machine import VirtualMachine


def run_nova(source):
    tokens = tokenize(source)
    TypeInferer().infer(ast := Parser(tokens).parse())
    compiler = Compiler()
    program = compiler.compile(ast)
    vm = VirtualMachine(program)
    vm.run()
    return vm


def _capture_print(source):
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        run_nova(source)
    finally:
        sys.stdout = old
    return buf.getvalue().strip()


def test_or_desugar_matches_first():
    out = _capture_print("""
a = 2
if a == 2 or 3 {
    print("pass")
} else {
    print("fail")
}
""")
    assert out == "pass"


def test_or_desugar_matches_second():
    out = _capture_print("""
a = 3
if a == 2 or 3 {
    print("pass")
} else {
    print("fail")
}
""")
    assert out == "pass"


def test_or_desugar_no_match():
    out = _capture_print("""
a = 5
if a == 2 or 3 {
    print("fail")
} else {
    print("pass")
}
""")
    assert out == "pass"


def test_and_desugar_matches_both():
    out = _capture_print("""
a = 3
if a == 2 and 3 {
    print("fail")
} else {
    print("pass")
}
""")
    assert out == "pass"


def test_and_desugar_matches_neither():
    out = _capture_print("""
a = 1
if a == 2 and 3 {
    print("fail")
} else {
    print("pass")
}
""")
    assert out == "pass"


def test_string_or_desugar():
    out = _capture_print("""
s = "hello"
if s == "hello" or "world" {
    print("pass")
} else {
    print("fail")
}
""")
    assert out == "pass"


def test_not_equal_or_desugar():
    out = _capture_print("""
a = 5
if a != 6 or 7 {
    print("pass")
} else {
    print("fail")
}
""")
    assert out == "pass"


def test_normal_or_unchanged():
    """a == b or c == d should NOT desugar (both sides are Compare)."""
    out = _capture_print("""
a = 1
b = 1
c = 2
d = 3
if a == b or c == d {
    print("pass")
} else {
    print("fail")
}
""")
    assert out == "pass"
