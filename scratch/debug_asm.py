import sys
sys.path.insert(0, '.')
from vm.machine import VirtualMachine
from vm.compiler import Compiler
from lexer.tokenizer import tokenize
from parser.parser import Parser
from modules.resolver import ModuleResolver
from compiler.type_checker import TypeChecker
from main import expand_imports

source = '''
import assembler

lines = []
lines.append(".data")
lines.append("fmt_test: .asciz \"hello\"")
lines.append(".text")
lines.append("_test:")
lines.append("    ret")

sections = assemble(lines)
print("code len: " + str(len(sections[0])))
print("data len: " + str(len(sections[1])))
print("labels: " + str(len(sections[2])))
print("fixups: " + str(len(sections[3])))
i = 0
while i < len(sections[2]) {
    lbl = sections[2][i]
    print("  label: " + lbl.name + " off=" + str(lbl.offset) + " def=" + str(lbl.defined))
    i = i + 1
}
'''

tokens = tokenize(source)
ast = Parser(tokens).parse()
resolver = ModuleResolver(base_dir='stdlib')
ast = expand_imports(ast, 'stdlib')
TypeChecker().check(ast)
compiler = Compiler(base_dir='stdlib')
program = compiler.compile(ast)
vm = VirtualMachine(program)
vm.run()
