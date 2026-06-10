import time, sys, subprocess, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer
from compiler.backend.x86.codegen import X86Codegen
from vm.compiler import Compiler
from vm.machine import VirtualMachine

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

def compile_native(source, name):
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    TypeInferer().infer(ast)
    cg = X86Codegen(ast)
    asm = cg.generate()
    s_path = os.path.join(BASE, f'bench_{name}.s')
    exe_path = os.path.join(BASE, f'bench_{name}.exe')
    with open(s_path, 'w') as f:
        f.write(asm)
    r = subprocess.run(['gcc', '-m32', '-o', exe_path, s_path,
                        os.path.join(ROOT, 'runtime.c'),
                        '-masm=intel', '-no-pie'],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return None, r.stderr[:300]
    t0 = time.perf_counter()
    r = subprocess.run([exe_path], capture_output=True, text=True, timeout=120)
    t1 = time.perf_counter()
    return t1 - t0, r.stdout.strip()

def run_vm(source):
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    TypeInferer().infer(ast)
    program = Compiler().compile(ast)
    vm = VirtualMachine(program)
    t0 = time.perf_counter()
    vm.run()
    t1 = time.perf_counter()
    return t1 - t0

# === sum_to(10M) ===
src_sum = "def sum_to(n) { s = 0\ni = 0\nwhile i <= n { s = s + i\ni = i + 1 }\nreturn s }\nprint(sum_to(10000000))"
print("--- sum_to(10M) ---")
result = compile_native(src_sum, "sum")
if result[0] is not None:
    print(f"  Nova native x86: {result[0]:.3f}s -> {result[1]}")
else:
    print(f"  Nova native x86: FAILED - {result[1]}")
print("  Nova VM: ", end="", flush=True)
t = run_vm(src_sum)
print(f"{t:.3f}s")

# === count_primes(50000) ===
src_primes = """
def is_prime(n) {
    if n < 2 { return 0 }
    i = 2
    while i * i <= n {
        if n % i == 0 { return 0 }
        i = i + 1
    }
    return 1
}
def count_primes(limit) {
    count = 0
    i = 2
    while i <= limit {
        if is_prime(i) == 1 { count = count + 1 }
        i = i + 1
    }
    return count
}
print(count_primes(50000))
"""
print("--- count_primes(50000) ---")
result = compile_native(src_primes, "primes")
if result[0] is not None:
    print(f"  Nova native x86: {result[0]:.3f}s -> {result[1]}")
else:
    print(f"  Nova native x86: FAILED - {result[1]}")
print("  Nova VM: ", end="", flush=True)
t = run_vm(src_primes)
print(f"{t:.3f}s")

# === fib(35) ===
src_fib = "def fib(n) { if n <= 1 { return n }\nreturn fib(n - 1) + fib(n - 2) }\nprint(fib(35))"
print("--- fib(35) ---")
result = compile_native(src_fib, "fib")
if result[0] is not None:
    print(f"  Nova native x86: {result[0]:.3f}s -> {result[1]}")
else:
    print(f"  Nova native x86: FAILED - {result[1]}")
print("  Nova VM: ", end="", flush=True)
t = run_vm(src_fib)
print(f"{t:.3f}s")
