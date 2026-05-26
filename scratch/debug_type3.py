import sys
sys.path.insert(0, r"D:\Coding\Python\Random Topic Practice\panda panda\nova")

from lexer.tokenizer import tokenize
from parser.parser import Parser
from modules.resolver import ModuleResolver
from main import expand_imports
from compiler.type_checker import TypeChecker, StaticTypeError
from ast.nodes import Function, Call, Assignment

source = 'import os_win\nfd = sys_open("build_test.nv", "r")\ncontent = sys_read(fd)\nprint(str(len(content)))\n'
tokens = tokenize(source)
ast = Parser(tokens).parse()
print("Parsed OK")

ast = expand_imports(ast, r"D:\Coding\Python\Random Topic Practice\panda panda\nova")
print("Expand OK")

tc = TypeChecker()
try:
    tc.check(ast)
except StaticTypeError as e:
    print(f"Type error: {e}")

# Find the Call('sys_read') node
def find_node(node, pred, depth=0):
    if node is None:
        return None
    if pred(node):
        return node
    if isinstance(node, list):
        for item in node:
            result = find_node(item, pred, depth + 1)
            if result:
                return result
    elif hasattr(node, '__dict__'):
        for attr in dir(node):
            if attr.startswith('_'):
                continue
            val = getattr(node, attr, None)
            if val is None or attr == 'inferred_type':
                continue
            if isinstance(val, list):
                for item in val:
                    if hasattr(item, '__dict__') or isinstance(item, list):
                        result = find_node(item, pred, depth + 1)
                        if result:
                            return result
            elif hasattr(val, '__dict__'):
                result = find_node(val, pred, depth + 1)
                if result:
                    return result
    return None

# Find the Call('sys_read') node
call_node = find_node(ast, lambda n: isinstance(n, Call) and n.name == 'sys_read')
if call_node:
    print(f"Found Call sys_read")
    print(f"  inferred_type: {getattr(call_node, 'inferred_type', 'NOT_SET')}")
    print(f"  args: {call_node.args}")
else:
    print("Call sys_read NOT FOUND in AST")
    print("Dumping all Calls:")
    def dump_calls(node, depth=0):
        if isinstance(node, Call):
            print(f"  {'  ' * depth}Call({node.name}) inferred_type={getattr(node, 'inferred_type', 'N/A')}")
        if isinstance(node, list):
            for item in node:
                dump_calls(item, depth + 1)
        elif hasattr(node, '__dict__'):
            for attr in dir(node):
                if attr.startswith('_'):
                    continue
                val = getattr(node, attr, None)
                if val is not None and attr != 'inferred_type':
                    if isinstance(val, list):
                        for item in val:
                            dump_calls(item, depth + 1)
                    elif hasattr(val, '__dict__'):
                        dump_calls(val, depth + 1)
    dump_calls(ast)
