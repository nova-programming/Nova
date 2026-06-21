"""Tests for try/catch/throw exception handling."""

import sys
import os
import io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bootstrap'))

from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from vm.compiler import Compiler
from vm.machine import VirtualMachine


def run_nova(source):
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    TypeInferer().infer(ast)
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


def test_try_catch_basic():
    out = _capture_print("""
try {
    throw 42
} catch e {
    print(e)
}
""")
    assert out == "42"


def test_try_no_throw():
    out = _capture_print("""
try {
    print(1)
} catch e {
    print(2)
}
""")
    assert out == "1"


def test_try_catch_string_exception():
    out = _capture_print("""
try {
    throw "error occurred"
} catch e {
    print(e)
}
""")
    assert "error" in out


def test_try_catch_expression_result():
    out = _capture_print("""
x = 0
try {
    throw 10
} catch e {
    x = e
}
print(x)
""")
    assert out == "10"


def test_try_no_exception_skips_catch():
    out = _capture_print("""
x = 1
try {
    x = 2
} catch e {
    x = 3
}
print(x)
""")
    assert out == "2"


def test_nested_try():
    out = _capture_print("""
x = 0
try {
    try {
        throw "inner"
    } catch inner {
        x = 100
    }
} catch outer {
    x = 200
}
print(x)
""")
    assert out == "100"


def test_throw_out_of_inner_try():
    out = _capture_print("""
x = 0
try {
    try {
        throw "up"
    } catch inner {
        throw "outer"
    }
} catch outer {
    x = 999
}
print(x)
""")
    assert out == "999"


def test_try_in_function():
    out = _capture_print("""
def safe_div(a, b) {
    if b == 0 {
        throw "divide by zero"
    }
    print(a / b)
}
try {
    safe_div(10, 0)
} catch e {
    print(-1)
}
""")
    assert out == "-1"


def test_try_catch_inside_function():
    out = _capture_print("""
def test() {
    try {
        throw 99
    } catch e {
        print(e)
    }
}
test()
""")
    assert out == "99"


def test_try_in_for_loop():
    out = _capture_print("""
x = 0
for i = 0 to 3 step 1 {
    try {
        if i == 2 {
            throw "err"
        }
        print(i)
    } catch e {
        print(-1)
    }
}
""")
    lines = out.split("\n")
    assert lines[0] == "0"
    assert lines[1] == "1"
    assert lines[2] == "-1"
    assert lines[3] == "3"


def test_try_no_exception_no_throw():
    out = _capture_print("""
x = 0
try {
    x = 42
} catch e {
    x = 99
}
print(x)
""")
    assert out == "42"


def test_unhandled_throw():
    out = _capture_print("""
try {
    throw "caught"
} catch e {
    print(e)
}
""")
    assert out == "caught"


def test_throw_in_catch():
    out = _capture_print("""
x = 0
try {
    throw "first"
} catch e {
    try {
        throw "second"
    } catch inner {
        x = 77
    }
}
print(x)
""")
    assert out == "77"
