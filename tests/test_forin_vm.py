"""Test for-in loops in the Nova VM (bootstrap)."""
import sys, os, unittest, io

BOOTSTRAP = os.path.join(os.path.dirname(__file__), "..", "bootstrap")
sys.path.insert(0, BOOTSTRAP)
from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine


class TestForInVM(unittest.TestCase):
    """Verify for-in over list, string, dict, and break/continue."""

    def _run(self, source):
        old_stdout = sys.stdout
        out = io.StringIO()
        sys.stdout = out
        try:
            tokens = tokenize(source)
            ast = Parser(tokens).parse()
            program = Compiler('.').compile(ast)
            vm = VirtualMachine(program)
            vm.run()
            return out.getvalue()
        finally:
            sys.stdout = old_stdout

    def test_for_in_list(self):
        out = self._run('s = [1, 2, 3, 4, 6]\n'
                        'for i in s {\n'
                        '    print(i)\n'
                        '}\n')
        self.assertEqual(out, "1\n2\n3\n4\n6\n")

    def test_for_in_string(self):
        out = self._run('s = "abc"\n'
                        'for ch in s {\n'
                        '    print(ch)\n'
                        '}\n')
        self.assertEqual(out, "a\nb\nc\n")

    def test_for_in_dict_keys(self):
        out = self._run('d = {"a": 1, "b": 2}\n'
                        'for k in d {\n'
                        '    print(k)\n'
                        '}\n')
        self.assertEqual(sorted(out.split()), ["a", "b"])

    def test_for_in_break(self):
        out = self._run('s = [1, 2, 3, 4, 5]\n'
                        'for i in s {\n'
                        '    if i == 3 {\n'
                        '        break\n'
                        '    }\n'
                        '    print(i)\n'
                        '}\n'
                        'print("done")\n')
        self.assertEqual(out, "1\n2\ndone\n")

    def test_for_in_continue(self):
        out = self._run('s = [1, 2, 3, 4]\n'
                        'for i in s {\n'
                        '    if i % 2 == 0 {\n'
                        '        continue\n'
                        '    }\n'
                        '    print(i)\n'
                        '}\n')
        self.assertEqual(out, "1\n3\n")

    def test_for_in_nested(self):
        out = self._run('a = [1, 2]\n'
                        'b = [10, 20]\n'
                        'for x in a {\n'
                        '    for y in b {\n'
                        '        print(x * y)\n'
                        '    }\n'
                        '}\n')
        self.assertEqual(out, "10\n20\n20\n40\n")

    def test_for_in_sum(self):
        out = self._run('nums = [1, 2, 3, 4, 5]\n'
                        'total = 0\n'
                        'for n in nums {\n'
                        '    total = total + n\n'
                        '}\n'
                        'print(total)\n')
        self.assertEqual(out, "15\n")

    def test_for_loop_continue(self):
        out = self._run('for i = 0 to 10 {\n'
                        '    if i % 2 == 0 {\n'
                        '        continue\n'
                        '    }\n'
                        '    print(i)\n'
                        '}\n')
        self.assertEqual(out, "1\n3\n5\n7\n9\n")

    def test_for_loop_downto_continue(self):
        out = self._run('for i = 5 downto 0 {\n'
                        '    if i == 3 {\n'
                        '        continue\n'
                        '    }\n'
                        '    print(i)\n'
                        '}\n')
        self.assertEqual(out, "5\n4\n2\n1\n0\n")

    def test_while_continue(self):
        out = self._run('i = 0\n'
                        'while i < 6 {\n'
                        '    i = i + 1\n'
                        '    if i % 2 == 0 {\n'
                        '        continue\n'
                        '    }\n'
                        '    print(i)\n'
                        '}\n')
        self.assertEqual(out, "1\n3\n5\n")


if __name__ == "__main__":
    unittest.main()
