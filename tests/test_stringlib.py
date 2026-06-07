import sys
sys.path.insert(0, '.')
from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine

tests = [
    ("split default", 'parts = split("a b c")\nprint(len(parts))\nprint(parts[0])\nprint(parts[1])\nprint(parts[2])\n'),
    ("split custom", 'parts = split("x|y|z", "|")\nprint(parts[0])\nprint(parts[1])\nprint(parts[2])\n'),
    ("join", 'lst = ["a", "b", "c"]\nprint(join(lst, ","))\n'),
    ("trim", 'print(trim("  hello  "))\n'),
    ("contains", 'print(contains("hello world", "world"))\nprint(contains("hello world", "xyz"))\n'),
    ("replace", 'print(replace("foo bar foo", "foo", "baz"))\n'),
    ("to_upper", 'print(to_upper("hello"))\n'),
    ("to_lower", 'print(to_lower("HELLO"))\n'),
    ("starts_with", 'print(starts_with("hello", "he"))\nprint(starts_with("hello", "xyz"))\n'),
    ("ends_with", 'print(ends_with("hello", "lo"))\nprint(ends_with("hello", "xy"))\n'),
]
for label, src in tests:
    print(f"--- {label} ---")
    tokens = tokenize(src)
    ast = Parser(tokens).parse()
    program = Compiler('.').compile(ast)
    vm = VirtualMachine(program)
    vm.run()
    print()
print("All string lib tests passed")
