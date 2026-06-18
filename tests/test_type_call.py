"""Tests for type() and call() built-in functions."""

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


def test_type_int():
    out = _capture_print('print(type(42))\n')
    assert out == "int"

def test_type_string():
    out = _capture_print('print(type("hello"))\n')
    assert out == "string"

def test_type_bool_true():
    out = _capture_print('print(type(true))\n')
    assert out == "bool"

def test_type_bool_false():
    out = _capture_print('print(type(false))\n')
    assert out == "bool"

def test_type_float():
    out = _capture_print('print(type(3.14))\n')
    assert out == "float"

def test_type_list():
    out = _capture_print('print(type([1, 2, 3]))\n')
    assert out == "list"

def test_type_dict():
    out = _capture_print('print(type({"a": 1}))\n')
    assert out == "dict"

def test_type_var_int():
    out = _capture_print('n = 42\nprint(type(n))\n')
    assert out == "int"

def test_type_var_string():
    out = _capture_print('s = "hello"\nprint(type(s))\n')
    assert out == "string"

def test_type_var_bool():
    out = _capture_print('b = true\nprint(type(b))\n')
    assert out == "bool"

def test_type_var_list():
    out = _capture_print('l = [1, 2, 3]\nprint(type(l))\n')
    assert out == "list"

def test_type_var_dict():
    out = _capture_print('d = {"a": 1}\nprint(type(d))\n')
    assert out == "dict"

def test_type_var_float():
    out = _capture_print('f = 3.14\nprint(type(f))\n')
    assert out == "float"

def test_call_builtin_abs():
    out = _capture_print('result = call("abs", [-5])\nprint(result)\n')
    assert out == "5"

def test_call_builtin_type():
    out = _capture_print('result = call("type", [42])\nprint(result)\n')
    assert out == "int"

def test_call_user_func():
    out = _capture_print('''
def double(x) { return x * 2 }
print(call("double", [21]))
''')
    assert out == "42"

def test_call_user_func_multi_args():
    out = _capture_print('''
def add(a, b) { return a + b }
print(call("add", [10, 32]))
''')
    assert out == "42"
