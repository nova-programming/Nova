import os
import sys

# Ensure we can import compiler modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.codegen_x86 import X86Codegen

def extract_asm(filename):
    with open(filename, 'r') as f:
        src = f.read()
    
    tokens = tokenize(src)
    parser = Parser(tokens)
    ast = parser.parse()
    
    cg = X86Codegen(ast)
    
    # Extract only the function implementations
    for node in ast:
        if node.__class__.__name__ == 'Function':
            cg.compile_function(node)
            
    # Now get everything that was appended to cg.asm_lines during compile_function
    return cg.assembly

all_asm = []
for f in ['stdlib/memory.nv', 'stdlib/os_win.nv', 'stdlib/math_utils.nv']:
    all_asm.extend(extract_asm(f))

with open('stdlib_asm.txt', 'w') as f:
    for line in all_asm:
        f.write(line + '\n')

print(f"Extracted {len(all_asm)} lines of assembly.")
