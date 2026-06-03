import os
from parser.parser import Parser
from lexer.tokenizer import tokenize

files = [
    "nova_main.nv",
    "stdlib/math_utils.nv",
    "stdlib/os_win.nv",
    "stdlib/memory.nv",
    "stdlib/codegen.nv",
    "stdlib/codegen_expr.nv",
    "stdlib/codegen_stmt.nv",
    "stdlib/codegen_func.nv",
    "stdlib/type_checker.nv",
    "stdlib/assembler_pass.nv",
    "stdlib/assembler_encode.nv",
    "stdlib/assembler_parse.nv",
    "stdlib/lexer.nv",
    "stdlib/parser.nv",
    "stdlib/types.nv",
    "stdlib/linker.nv",
    "stdlib/compiler.nv"
]

for f in files:
    try:
        with open(f, 'r') as fp:
            source = fp.read()
        tokens = tokenize(source)
        Parser(tokens).parse()
        print(f + ": OK")
    except Exception as e:
        print(f + " ERROR: " + str(e))
