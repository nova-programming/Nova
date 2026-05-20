import sys
import os

from lexer.tokenizer import tokenize
from parser.parser import Parser
from vm.compiler import Compiler
from vm.machine import VirtualMachine


def run_source(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    # print("[1] Tokenizing...")
    tokens = tokenize(source)

    # print("[2] Parsing...")
    ast = Parser(tokens).parse()
    
    # print("[3] Compiling to Custom Bytecode...")
    compiler = Compiler()
    program = compiler.compile(ast)

    # print("[4] Executing on Custom VM...")
    vm = VirtualMachine(program)
    vm.run()


def main():
    if len(sys.argv) < 3:
        print("Usage: nova run <file.nv>")
        return

    command = sys.argv[1]
    file_path = sys.argv[2]

    if command == "run":
        run_source(file_path)


if __name__ == "__main__":
    main()