"""Reproduce the macOS ARM64 self-hosted codegen crash locally.

Runs stdlib/backend/arm64/codegen.nv (the self-hosted ARM64 codegen) inside
the Python VM. Module imports of "codegen"/"codegen_expr"/"codegen_stmt" are
redirected to the arm64 backend directory, so the exact same Nova source that
crashes natively on macOS executes here — but the VM reports
"Index Out Of Bounds at <file>:<line>" instead of SIGBUS/SIGSEGV.

Usage:
    python tests/run_arm64_codegen_vm.py <source.nv>
"""

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bootstrap"))

from lexer.tokenizer import tokenize
from parser.parser import Parser
from modules.resolver import ModuleResolver
from vm.compiler import Compiler
from vm.machine import VirtualMachine

_ARM64_MODULES = {
    "codegen", "codegen_expr", "codegen_stmt",
    "assembler", "assembler_parse", "assembler_encode", "assembler_pass",
    "linker",
}

_orig_find = ModuleResolver._find_module


def _arm64_find(self, module_name, importer_dir=None):
    if module_name in _ARM64_MODULES:
        return os.path.join(ROOT, "stdlib", "backend", "arm64", f"{module_name}.nv")
    return _orig_find(self, module_name, importer_dir)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    prog_path = os.path.abspath(sys.argv[1])
    with open(prog_path, "r", encoding="utf-8") as f:
        test_src = f.read()

    ModuleResolver._find_module = _arm64_find

    pipeline = "full"
    if len(sys.argv) >= 3 and sys.argv[2] == "codegen":
        pipeline = "codegen"

    driver_path = os.path.join(ROOT, "tests", "_arm64_driver.nv")
    with open(driver_path, "w", encoding="utf-8") as f:
        f.write(
            'import lexer\n'
            'import parser\n'
            'import errors\n'
            'import types\n'
            'import type_checker\n'
            'import codegen_common\n'
            'import codegen_stmt\n'
            'import codegen_expr\n'
            'import codegen\n'
            'import assembler\n'
            'import linker\n'
            f'src_path = "{prog_path.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"\n'
            'fd = open(src_path, "r")\n'
            'source = read(fd)\n'
            'close(fd)\n'
            'print("DRIVER: read source")\n'
            'toks = tokenize(source)\n'
            'print("DRIVER: tokenized")\n'
            'ast = parse(toks, "arm64test.nv")\n'
            'print("DRIVER: parsed")\n'
            'tc = TypeChecker()\n'
            'print("DRIVER: new tc")\n'
            'tc_init(tc)\n'
            'print("DRIVER: tc_init done")\n'
            'tc_check(tc, ast)\n'
            'print("DRIVER: after tc_check")\n'
            'asm = generate_assembly(ast, 0, 0, "macos")\n'
            'print("DRIVER: after generate_assembly")\n'
            'print("ASM_LINES=" + str(len(asm)))\n'
            'if "' + pipeline + '" != "codegen" {\n'
            '    print("DRIVER: assembling")\n'
            '    assembled = assemble(asm)\n'
            '    print("DRIVER: after assemble")\n'
            '    print("CODE_BYTES=" + str(len(assembled[0])))\n'
            '    print("DATA_BYTES=" + str(len(assembled[1])))\n'
            '    print("DRIVER: linking")\n'
            '    exe_bytes = link(assembled)\n'
            '    print("DRIVER: after link")\n'
            '    print("EXE_BYTES=" + str(len(exe_bytes)))\n'
            '}\n'
        )

    from compiler.type_checker import TypeInferer

    with open(driver_path, "r", encoding="utf-8") as f:
        src = f.read()
    toks = tokenize(src)
    ast = Parser(toks).parse()
    try:
        TypeInferer().infer(ast)
    except Exception as e:
        print("[driver type-check ignored]", e)

    compiler = Compiler(base_dir=os.path.join(ROOT, "tests"))
    program = compiler.compile(ast)
    vm = VirtualMachine(program)
    vm.run()
    print("VM finished without native crash")


if __name__ == "__main__":
    main()