import sys
import os
import subprocess

from nova.lexer.tokenizer import tokenize
from nova.parser.parser import Parser
from nova.codegen.generator import CodeGen


def compile_source(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    print("[1] Reading source...")
    tokens = tokenize(source)
    print("[2] Tokenizing...")
    ast = Parser(tokens).parse()
    print("[3] Parsing...")
    
    gen = CodeGen()
    llvm_ir = gen.generate(ast)
    print("[4] Generating LLVM IR...")

    ir_file = file_path + ".ll"
    with open(ir_file, "w", encoding="utf-8") as f:
        f.write(llvm_ir)

    print("[5] LLVM IR written to", ir_file)
    return ir_file


def run_llvm(ir_file):
    exe_file = ir_file.replace(".ll", ".exe") if os.name == 'nt' else ir_file.replace(".ll", "")

    print("[6] Compiling with clang...")
    subprocess.run(["clang", ir_file, "-o", exe_file], check=True)

    print("[7] Running executable...")
    subprocess.run([exe_file], check=True)

    print("[8] Cleaning up...")
    os.remove(ir_file)
    os.remove(exe_file)


def main():
    if len(sys.argv) < 3:
        print("Usage: nova run <file.nv>")
        return

    command = sys.argv[1]
    file_path = sys.argv[2]

    if command == "run":
        ir_file = compile_source(file_path)
        run_llvm(ir_file)


if __name__ == "__main__":
    main()