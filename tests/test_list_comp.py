import sys, os, unittest

BOOTSTRAP = os.path.join(os.path.dirname(__file__), "..", "bootstrap")
sys.path.insert(0, BOOTSTRAP)
from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine


class TestListComprehension(unittest.TestCase):

    def _run(self, source):
        tokens = tokenize(source)
        ast = Parser(tokens).parse()
        program = Compiler('.').compile(ast)
        vm = VirtualMachine(program)
        vm.run()

    def test_basic(self):
        self._run('items = [1, 2, 3, 4, 5]\nresult = [x * 2 for x in items]\nprint(result)\n')

    def test_with_if(self):
        self._run('items = [1, 2, 3, 4, 5, 6]\nresult = [x for x in items if x > 3]\nprint(result)\n')

    def test_expr_and_filter(self):
        self._run('vals = [1, 2, 3, 4, 5]\nresult = [x * 10 for x in vals if x % 2 == 1]\nprint(result)\n')

    def test_empty_list(self):
        self._run('items = []\nresult = [x * 2 for x in items]\nprint(result)\n')

    def test_inline_print(self):
        self._run('items = [1, 2, 3]\nprint([x + 10 for x in items])\n')

    def test_square_filter(self):
        self._run('vals = [1, 2, 3, 4, 5]\nresult = [x * x for x in vals if x > 2]\nprint(result)\n')

    def test_even_filter(self):
        self._run('vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\nresult = [x for x in vals if x % 2 == 0]\nprint(result)\n')


if __name__ == "__main__":
    unittest.main()
