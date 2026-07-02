import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bootstrap'))
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from compiler.backend.arm64.codegen import Arm64Codegen
from nova_ast.nodes import Import

# Use a simple test: print(len("abcdef")) to see the Len handler output
# Then modify to use a variable path to see the variable case
for label, source in [
    ("len(literal)", 'print(len("abcdef"))'),
    ("len(variable)", 's = "hello"; print(len(s))'),
]:
    print(f"\n=== {label}: {source} ===")
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

    # Show lines around 'len' references
    for i, line in enumerate(asm_lines):
        if 'L_strlen' in line or 'sub x0, x0, x9' in line or 'sub x0, x0, #1' in line or 'strlen' in line:
            start = max(0, i-5)
            end = min(len(asm_lines), i+5)
            for j in range(start, end):
                print(f"  {j}: {asm_lines[j]}")
            print()
