import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bootstrap'))
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from compiler.backend.arm64.codegen import Arm64Codegen
from nova_ast.nodes import Import

# Match the exact test: print(len("abc"))
source = 'print(len("abc"))'
tokens = tokenize(source)
ast = Parser(tokens).parse()
TypeInferer().infer(ast)

module_names = set()
for node in ast:
    if isinstance(node, Import):
        module_names.add(node.module)

codegen = Arm64Codegen(ast, module_names=module_names)
asm = codegen.generate()
asm_lines = asm.split('\n')

# Show the _main body lines
for i, line in enumerate(asm_lines):
    if '_main:' in line:
        for j in range(i, min(i+40, len(asm_lines))):
            if asm_lines[j].startswith('_concat'):
                break
            print(f"  {j}: {asm_lines[j]}")
