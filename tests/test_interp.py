"""Test string interpolation in the Nova VM."""
import sys, os, unittest

BOOTSTRAP = os.path.join(os.path.dirname(__file__), "..", "bootstrap")
sys.path.insert(0, BOOTSTRAP)
from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine


class TestStringInterpolation(unittest.TestCase):
    """Verify string interpolation in the Nova VM."""

    def _run(self, source):
        tokens = tokenize(source)
        ast = Parser(tokens).parse()
        program = Compiler('.').compile(ast)
        vm = VirtualMachine(program)
        vm.run()

    def test_simple(self):
        self._run('name = "World"\nprint("Hello {name}!")\n')

    def test_expr(self):
        self._run('x = 10\ny = 20\nprint("{x} + {y} = {x + y}")\n')

    def test_no_interp(self):
        self._run('print("Hello World")\n')

    def test_empty_embed(self):
        self._run('print("_{x}_")\n')

    def test_leading(self):
        self._run('x = 42\nprint("{x} is the answer")\n')

    def test_trailing(self):
        self._run('x = 99\nprint("value: {x}")\n')


if __name__ == "__main__":
    unittest.main()
