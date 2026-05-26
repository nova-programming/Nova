import sys
sys.path.insert(0, r"D:\Coding\Python\Random Topic Practice\panda panda\nova")

from lexer.tokenizer import tokenize
from parser.parser import Parser
from modules.resolver import ModuleResolver
from main import expand_imports
from compiler.type_checker import TypeChecker
from ast.nodes import Function, Call

source = 'import os_win\nfd = sys_open("build_test.nv", "r")\ncontent = sys_read(fd)\nprint(str(len(content)))\n'
tokens = tokenize(source)
ast = Parser(tokens).parse()
print("Parsed OK")

ast = expand_imports(ast, r"D:\Coding\Python\Random Topic Practice\panda panda\nova")
print("Expand OK")

tc = TypeChecker()
tc.check(ast)

print(f"sys_read in functions: {'sys_read' in tc.functions}")
if 'sys_read' in tc.functions:
    print(f"  return_type: {tc.functions['sys_read']['return_type']}")

def find_all_calls(node, depth=0):
    if node is None:
        return
    if isinstance(node, Call):
        print('  ' * depth + f'Call {node.name} inferred_type: {getattr(node, "inferred_type", None)}')
        for arg in node.args:
            find_all_calls(arg, depth + 1)
        return
    if isinstance(node, list):
        for item in node:
            find_all_calls(item, depth)
    elif hasattr(node, '__dict__'):
        for attr in dir(node):
            if not attr.startswith('_'):
                val = getattr(node, attr, None)
                if val is not None and attr not in ('inferred_type', 'inferred_type'):
                    if isinstance(val, list):
                        for item in val:
                            if hasattr(item, '__dict__') or isinstance(item, list):
                                find_all_calls(item, depth + 1)
                    elif hasattr(val, '__dict__'):
                        find_all_calls(val, depth + 1)

find_all_calls(ast)
print("Done")
