import sys
sys.path.insert(0, r"D:\Coding\Python\Random Topic Practice\panda panda\nova")

from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeChecker

source = 'import os_win\nfd = sys_open("build_test.nv", "r")\ncontent = sys_read(fd)\nprint(str(len(content)))\n'
tokens = tokenize(source)
ast = Parser(tokens).parse()
print("Parsed OK")

tc = TypeChecker()
tc.check(ast)
print("Type check OK")

def find_call(node, depth=0):
    if node is None:
        return
    if hasattr(node, 'name') and node.name == 'sys_read':
        print('  ' * depth + f'Call sys_read inferred_type: {getattr(node, "inferred_type", None)}')
        return
    if isinstance(node, list):
        for item in node:
            find_call(item, depth)
    elif hasattr(node, '__dict__'):
        for attr in ['body', 'value', 'args', 'if_body', 'else_body']:
            val = getattr(node, attr, None)
            if val is not None:
                if isinstance(val, list):
                    for item in val:
                        find_call(item, depth + 1)
                else:
                    find_call(val, depth + 1)

find_call(ast)
print("Done")
