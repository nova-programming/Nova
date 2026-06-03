import sys, os
sys.path.insert(0, '.')
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.codegen_x86 import X86Codegen

with open('tests/test_shl_debug.nv') as f:
    code = f.read()

tokens = tokenize(code)
p = Parser(tokens)
ast = p.parse()

from main import expand_imports
ast = expand_imports(ast, '.')

# Show y2 assignment
for node in ast:
    if hasattr(node, 'name') and node.name == 'y2':
        print('y2:')
        val = node.value
        print(f'  type={type(val).__name__}')
        if hasattr(val, 'op'):
            print(f'  op={val.op}')
        if hasattr(val, 'left'):
            print(f'  left kind={type(val.left).__name__} val={val.left.value if hasattr(val.left, "value") else "?"}')
        if hasattr(val, 'right'):
            print(f'  right kind={type(val.right).__name__} val={val.right.value if hasattr(val.right, "value") else "?"}')

# Also check y1
for node in ast:
    if hasattr(node, 'name') and node.name == 'y1':
        print('y1:')
        val = node.value
        print(f'  type={type(val).__name__}')
        if hasattr(val, 'op'):
            print(f'  op={val.op}')
        if hasattr(val, 'left'):
            print(f'  left kind={type(val.left).__name__} val={val.left.value if hasattr(val.left, "value") else "?"}')
        if hasattr(val, 'right'):
            print(f'  right kind={type(val.right).__name__} val={val.right.value if hasattr(val.right, "value") else "?"}')
