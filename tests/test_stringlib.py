"""Test string library functions in the Nova VM."""
import sys, os, unittest

BOOTSTRAP = os.path.join(os.path.dirname(__file__), "..", "bootstrap")
sys.path.insert(0, BOOTSTRAP)
from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine


class TestStringLib(unittest.TestCase):
    """Verify string library functions in the Nova VM."""

    def _run(self, source):
        tokens = tokenize(source)
        ast = Parser(tokens).parse()
        program = Compiler('.').compile(ast)
        vm = VirtualMachine(program)
        vm.run()

    def test_split_default(self):
        self._run('parts = split("a b c")\nprint(len(parts))\nprint(parts[0])\nprint(parts[1])\nprint(parts[2])\n')

    def test_split_custom(self):
        self._run('parts = split("x|y|z", "|")\nprint(parts[0])\nprint(parts[1])\nprint(parts[2])\n')

    def test_join(self):
        self._run('lst = ["a", "b", "c"]\nprint(join(lst, ","))\n')

    def test_trim(self):
        self._run('print(trim("  hello  "))\n')

    def test_contains(self):
        self._run('print(contains("hello world", "world"))\nprint(contains("hello world", "xyz"))\n')

    def test_replace(self):
        self._run('print(replace("foo bar foo", "foo", "baz"))\n')

    def test_to_upper(self):
        self._run('print(to_upper("hello"))\n')

    def test_to_lower(self):
        self._run('print(to_lower("HELLO"))\n')

    def test_starts_with(self):
        self._run('print(starts_with("hello", "he"))\nprint(starts_with("hello", "xyz"))\n')

    def test_ends_with(self):
        self._run('print(ends_with("hello", "lo"))\nprint(ends_with("hello", "xy"))\n')


if __name__ == "__main__":
    unittest.main()
