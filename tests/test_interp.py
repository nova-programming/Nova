import sys
sys.path.insert(0, '.')
from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine

tests = [
    ("Simple", 'name = "World"\nprint("Hello {name}!")\n'),
    ("Expr", 'x = 10\ny = 20\nprint("{x} + {y} = {x + y}")\n'),
    ("No interp", 'print("Hello World")\n'),
    ("Empty embed", 'print("_{x}_")\n'),
    ("Leading", 'x = 42\nprint("{x} is the answer")\n'),
    ("Trailing", 'x = 99\nprint("value: {x}")\n'),
]
for label, src in tests:
    print(f"--- {label} ---")
    tokens = tokenize(src)
    ast = Parser(tokens).parse()
    program = Compiler('.').compile(ast)
    vm = VirtualMachine(program)
    vm.run()
    print()
print("All interpolation tests passed")
