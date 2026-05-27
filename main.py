import sys
import os

from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine
from compiler.type_checker import TypeChecker, StaticTypeError


def run_source(file_path):
    """Run a Nova program in the VM (development mode — fast execution)."""
    file_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tokens = tokenize(source)
    ast = Parser(tokens).parse()

    try:
        TypeChecker().check(ast)
    except StaticTypeError as e:
        print(f"StaticTypeError: {e}")
        sys.exit(1)

    compiler = Compiler(base_dir=base_dir)
    program = compiler.compile(ast)

    vm = VirtualMachine(program)
    vm.run()


def expand_imports(ast, base_dir, resolver=None, visited=None):
    from modules.resolver import ModuleResolver
    from ast.nodes import Import
    import sys
    if resolver is None:
        resolver = ModuleResolver(base_dir=base_dir)
    if visited is None:
        visited = set()

    expanded_ast = []
    for node in ast:
        if isinstance(node, Import):
            if node.module not in visited:
                visited.add(node.module)
                try:
                    imported_ast = resolver.resolve(node.module, base_dir)
                    # Recursively expand imports inside the imported file
                    expanded_ast.extend(expand_imports(imported_ast, base_dir, resolver, visited))
                except FileNotFoundError as e:
                    print(e)
                    sys.exit(1)
        else:
            expanded_ast.append(node)
    return expanded_ast


def compile_native(file_path):
    """Compile a Nova program to a native executable (build mode)."""
    file_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    
    # Collect module names before expansion
    from ast.nodes import Import
    module_names = set()
    for node in ast:
        if isinstance(node, Import):
            module_names.add(node.module)

    ast = expand_imports(ast, base_dir)

    try:
        TypeChecker().check(ast)
    except StaticTypeError as e:
        print(f"StaticTypeError: {e}")
        sys.exit(1)

    from compiler.codegen_x86 import X86Codegen
    codegen = X86Codegen(ast, module_names=module_names)
    asm_code = codegen.generate()

    asm_file = file_path.rsplit(".", 1)[0] + ".s"
    exe_file = file_path.rsplit(".", 1)[0] + ".exe"

    with open(asm_file, "w", encoding="utf-8") as f:
        f.write(asm_code)

    print(f"Generated assembly: {asm_file}")
    
    import subprocess
    cmd = ["gcc", asm_file, "-o", exe_file, "-lkernel32"]
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("GCC Compilation Failed:")
        print(res.stderr)
        sys.exit(1)
    print(f"Successfully compiled native executable: {exe_file}")


def print_usage():
    print("Nova Programming Language")
    print("")
    print("Usage:")
    print("  nova dev <file.nv>     Run in VM (fast, for development)")
    print("  nova build <file.nv>   Compile to native executable")
    print("  nova run <file.nv>     Alias for 'dev' (backward compatible)")
    print("")
    print("Examples:")
    print("  python main.py dev program.nv")
    print("  python main.py build program.nv")


def main():
    if len(sys.argv) < 3:
        print_usage()
        return

    command = sys.argv[1]
    file_path = sys.argv[2]

    if command in ("dev", "run"):
        run_source(file_path)
    elif command == "build":
        compile_native(file_path)
    else:
        print(f"Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()