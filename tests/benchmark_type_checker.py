"""Performance benchmark for type checker AST kind dispatch.

Times tokenize, parse, and typecheck on a large generated Nova program
to measure the impact of the dict-dispatch optimization."""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bootstrap'))

from lexer.tokenizer import tokenize
from parser.parser import Parser
from compiler.type_checker import TypeInferer


def generate_large_program(func_count=100, expr_per_func=50):
    """Generate a Nova program with many functions, variables, and expressions."""
    lines = []
    for i in range(func_count):
        lines.append(f"def f{i}(x, y) {{")
        lines.append(f"    a = x + y")
        lines.append(f"    b = a * 2")
        for j in range(expr_per_func):
            v = j % 10
            lines.append(f"    if x > {v} {{ z = a + b - {v} }} else {{ z = a - b + {v} }}")
            lines.append(f"    if y < {v + 10} {{ w = z * {v} }} else {{ w = z / 2 }}")
        lines.append("    return a + b")
        lines.append("}")
    lines.append("")
    lines.append("def run() {")
    lines.append("    r = 0")
    for i in range(min(func_count, 20)):
        lines.append(f"    r = r + f{i}(r + {i}, r + {i + 1})")
    lines.append("    print(r)")
    lines.append("}")
    return "\n".join(lines)


def benchmark_phase(name, source, iterations=5):
    tokens = time_phase("tokenize", lambda: tokenize(source), iterations=1)
    
    def parse_phase():
        return Parser(tokens).parse()
    ast = time_phase("parse", parse_phase, iterations=1)
    
    def typecheck_phase():
        TypeInferer().infer(ast)
    
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        typecheck_phase()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    
    avg = sum(times) / len(times)
    best = min(times)
    worst = max(times)
    return avg, best, worst, times


def time_phase(name, fn, iterations=1):
    t0 = time.perf_counter()
    for _ in range(iterations):
        result = fn()
    t1 = time.perf_counter()
    ms = (t1 - t0) * 1000
    return result


def count_ast_nodes(ast):
    count = 1
    for child in ast:
        count += count_ast_node(child)
    return count


def count_ast_node(node):
    if node is None:
        return 0
    count = 1
    for attr in dir(node):
        if attr.startswith('_'):
            continue
        val = getattr(node, attr)
        if isinstance(val, list):
            for item in val:
                count += count_ast_node(item)
    return count


def run_benchmark():
    print("=" * 60)
    print("Nova Type Checker Performance Benchmark")
    print("=" * 60)
    
    for func_count, expr_per_func in [(50, 20), (100, 30), (200, 50)]:
        print(f"\n--- Program: {func_count} functions, ~{expr_per_func * 4} nodes each ---")
        source = generate_large_program(func_count, expr_per_func)
        
        t0 = time.perf_counter()
        tokens = tokenize(source)
        t1 = time.perf_counter()
        token_ms = (t1 - t0) * 1000
        
        ast = Parser(tokens).parse()
        t2 = time.perf_counter()
        parse_ms = (t2 - t1) * 1000
        
        node_count = count_ast_nodes(ast)
        print(f"  Tokens: {len(tokens):,}  |  AST nodes: ~{node_count:,}")
        print(f"  Tokenize: {token_ms:.1f} ms  |  Parse: {parse_ms:.1f} ms")
        
        iterations = 10
        type_times = []
        for i in range(iterations):
            t3 = time.perf_counter()
            TypeInferer().infer(ast)
            t4 = time.perf_counter()
            type_times.append((t4 - t3) * 1000)
        
        avg = sum(type_times) / len(type_times)
        best = min(type_times)
        worst = max(type_times)
        print(f"  TypeCheck ({iterations} runs): avg={avg:.3f} ms  best={best:.3f} ms  worst={worst:.3f} ms")
        print(f"  Total pipeline: {token_ms + parse_ms + avg:.1f} ms")
    
    print("\n" + "=" * 60)
    print("Benchmark complete.")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
