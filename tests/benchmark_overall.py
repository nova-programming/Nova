"""Overall Nova system benchmark.

Runs benchmark_overall.nv through the Nova pipeline, plus equivalent
Python and C code. Also tests native-compiled Nova (nova build + run)
with both small and large workloads.
"""
import os, sys, time, subprocess, re, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(BASE, "tests")
BOOTSTRAP = os.path.join(BASE, "bootstrap")


def parse_nv_workloads():
    path = os.path.join(TESTS, "benchmark_overall.nv")
    with open(path) as f:
        text = f.read()
    w = {}
    for m in re.finditer(r'w_(\w+)\s*=\s*(\d+)', text):
        w[m.group(1)] = int(m.group(2))
    return w, path


def time_cmd(cmd, iterations=3, timeout=120):
    times = []
    outputs = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
        outputs.append(r.stdout)
    avg = sum(times) / len(times)
    return avg, min(times), max(times), outputs[0]


def run_benchmark():
    print("=" * 70)
    print("Nova System \u2014 Overall Performance Benchmark")
    print("=" * 70)

    workloads, nv_path = parse_nv_workloads()
    print(f"\nWorkloads (from .nv):")
    for k, v in workloads.items():
        print(f"  {k} = {v:,}")
    print()

    # Heavy workloads for native testing (500x bigger)
    heavy = {
        'sum_to': workloads['sum_to'] * 100,
        'primes': workloads['primes'] * 60,
        'fib': 35,
    }
    print(f"Heavy workloads (native only):")
    for k, v in heavy.items():
        print(f"  {k} = {v:,}")
    print()

    # ---- 1. Nova VM Execution ----
    print("-" * 70)
    print("1. Nova VM (python main.py dev)")
    print("-" * 70)
    avg_vm, best_vm, worst_vm, out_vm = time_cmd(
        [sys.executable, os.path.join(BOOTSTRAP, "main.py"), "dev", nv_path],
        iterations=5, timeout=120
    )
    print(f"  avg={avg_vm:.0f} ms  best={best_vm:.0f}  worst={worst_vm:.0f}")
    for l in out_vm.strip().split("\n"):
        if l:
            print(f"    {l}")

    # ---- 2. CPython Execution ----
    print("-" * 70)
    print("2. CPython (same algorithm)")
    print("-" * 70)
    py_src = f"""
s = 0
for i in range(1, {workloads['sum_to']} + 1): s += i
print(s)
def is_prime(n):
    if n < 2: return 0
    i = 2
    while i * i <= n:
        if n % i == 0: return 0
        i += 1
    return 1
count = 0
for i in range(2, {workloads['primes']} + 1):
    if is_prime(i): count += 1
print(count)
def fib(n):
    if n <= 1: return n
    return fib(n - 1) + fib(n - 2)
print(fib({workloads['fib']}))
"""
    avg_py, best_py, worst_py, out_py = time_cmd(
        [sys.executable, "-c", py_src],
        iterations=5, timeout=120
    )
    print(f"  avg={avg_py:.0f} ms  best={best_py:.0f}  worst={worst_py:.0f}")
    for l in out_py.strip().split("\n"):
        if l:
            print(f"    {l}")

    # ---- 3. C Execution ----
    print("-" * 70)
    print("3. C (gcc -O2)")
    print("-" * 70)
    c_src = f"""
#include <stdio.h>
long long sum_to(int n) {{
    long long s = 0;
    for (int i = 1; i <= n; i++) s += i;
    return s;
}}
int is_prime(int n) {{
    if (n < 2) return 0;
    for (int i = 2; i * i <= n; i++)
        if (n % i == 0) return 0;
    return 1;
}}
int count_primes(int limit) {{
    int count = 0;
    for (int i = 2; i <= limit; i++)
        if (is_prime(i)) count++;
    return count;
}}
int fib(int n) {{
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}}
int main() {{
    printf("%lld\\n", sum_to({workloads['sum_to']}));
    printf("%d\\n", count_primes({workloads['primes']}));
    printf("%d\\n", fib({workloads['fib']}));
    return 0;
}}
"""
    c_tmp = os.path.join(tempfile.gettempdir(), "nova_bench_c.c")
    exe_tmp = os.path.join(tempfile.gettempdir(), "nova_bench_c.exe")
    with open(c_tmp, "w") as f:
        f.write(c_src.lstrip("\n"))
    r = subprocess.run(["gcc", "-O2", "-o", exe_tmp, c_tmp], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"  C compilation failed: {r.stderr}")
        avg_c = best_c = worst_c = 999999
        out_c = ""
    else:
        avg_c, best_c, worst_c, out_c = time_cmd([exe_tmp], iterations=5, timeout=120)
        print(f"  avg={avg_c:.0f} ms  best={best_c:.0f}  worst={worst_c:.0f}")
        for l in out_c.strip().split("\n"):
            if l:
                print(f"    {l}")
    for p in [c_tmp, exe_tmp]:
        try: os.unlink(p)
        except: pass

    # ---- 4. Nova Native (small workloads) ----
    print("-" * 70)
    print("4. Nova Native (python main.py run)")
    print("-" * 70)
    avg_nn, best_nn, worst_nn, out_nn = time_cmd(
        [sys.executable, os.path.join(BOOTSTRAP, "main.py"), "run", nv_path],
        iterations=3, timeout=120
    )
    print(f"  avg={avg_nn:.0f} ms  best={best_nn:.0f}  worst={worst_nn:.0f}")
    for l in out_nn.strip().split("\n"):
        if l:
            print(f"    {l}")

    # ---- 5. Nova Native (heavy workloads) ----
    # Create a heavy .nv file, build it natively, time the binary
    print("-" * 70)
    print("5. Nova Native (heavy workloads)")
    print("-" * 70)
    heavy_nv = os.path.join(tempfile.gettempdir(), "nova_bench_heavy.nv")
    heavy_nv_src = f"""
def sum_to(n) {{
    s = 0
    i = 1
    while i <= n {{
        s = s + i
        i = i + 1
    }}
    return s
}}

def is_prime(n) {{
    if n < 2 {{ return 0 }}
    i = 2
    while i * i <= n {{
        if n % i == 0 {{ return 0 }}
        i = i + 1
    }}
    return 1
}}

def count_primes(limit) {{
    count = 0
    i = 2
    while i <= limit {{
        if is_prime(i) == 1 {{ count = count + 1 }}
        i = i + 1
    }}
    return count
}}

def fib(n) {{
    if n <= 1 {{ return n }}
    return fib(n - 1) + fib(n - 2)
}}

w_sum_to = {heavy['sum_to']}
w_primes = {heavy['primes']}
w_fib = {heavy['fib']}

print(sum_to(w_sum_to))
print(count_primes(w_primes))
print(fib(w_fib))
"""
    with open(heavy_nv, "w") as f:
        f.write(heavy_nv_src)

    avg_nh, best_nh, worst_nh, out_nh = time_cmd(
        [sys.executable, os.path.join(BOOTSTRAP, "main.py"), "run", heavy_nv],
        iterations=3, timeout=120
    )
    print(f"  avg={avg_nh:.0f} ms  best={best_nh:.0f}  worst={worst_nh:.0f}")
    for l in out_nh.strip().split("\n"):
        if l:
            print(f"    {l}")
    try: os.unlink(heavy_nv)
    except: pass

    # ---- CPython + C comparison (heavy workloads) ----
    print("-" * 70)
    print("6. CPython (heavy workloads)")
    print("-" * 70)
    py_heavy = f"""
s = 0
for i in range(1, {heavy['sum_to']} + 1): s += i
print(s)
def is_prime(n):
    if n < 2: return 0
    i = 2
    while i * i <= n:
        if n % i == 0: return 0
        i += 1
    return 1
count = 0
for i in range(2, {heavy['primes']} + 1):
    if is_prime(i): count += 1
print(count)
def fib(n):
    if n <= 1: return n
    return fib(n - 1) + fib(n - 2)
print(fib({heavy['fib']}))
"""
    avg_ph, best_ph, worst_ph, out_ph = time_cmd(
        [sys.executable, "-c", py_heavy],
        iterations=5, timeout=120
    )
    print(f"  avg={avg_ph:.0f} ms  best={best_ph:.0f}  worst={worst_ph:.0f}")
    for l in out_ph.strip().split("\n"):
        if l:
            print(f"    {l}")

    print("-" * 70)
    print("7. C (gcc -O2, heavy workloads)")
    print("-" * 70)
    c_heavy = f"""
#include <stdio.h>
long long sum_to(int n) {{
    long long s = 0;
    for (int i = 1; i <= n; i++) s += i;
    return s;
}}
int is_prime(int n) {{
    if (n < 2) return 0;
    for (int i = 2; i * i <= n; i++)
        if (n % i == 0) return 0;
    return 1;
}}
int count_primes(int limit) {{
    int count = 0;
    for (int i = 2; i <= limit; i++)
        if (is_prime(i)) count++;
    return count;
}}
int fib(int n) {{
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}}
int main() {{
    printf("%lld\\n", sum_to({heavy['sum_to']}));
    printf("%d\\n", count_primes({heavy['primes']}));
    printf("%d\\n", fib({heavy['fib']}));
    return 0;
}}
"""
    c_heavy_tmp = os.path.join(tempfile.gettempdir(), "nova_bench_c_heavy.c")
    exe_heavy_tmp = os.path.join(tempfile.gettempdir(), "nova_bench_c_heavy.exe")
    with open(c_heavy_tmp, "w") as f:
        f.write(c_heavy.lstrip("\n"))
    r = subprocess.run(["gcc", "-O2", "-o", exe_heavy_tmp, c_heavy_tmp], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"  C compilation failed: {r.stderr}")
        avg_ch = best_ch = worst_ch = 999999
        out_ch = ""
    else:
        avg_ch, best_ch, worst_ch, out_ch = time_cmd([exe_heavy_tmp], iterations=5, timeout=120)
        print(f"  avg={avg_ch:.0f} ms  best={best_ch:.0f}  worst={worst_ch:.0f}")
        for l in out_ch.strip().split("\n"):
            if l:
                print(f"    {l}")
    for p in [c_heavy_tmp, exe_heavy_tmp]:
        try: os.unlink(p)
        except: pass

    # ---- Summary ----
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  {'Runtime':<35s} {'Avg Wall':>10s} {'vs C':>10s}")
    print(f"  {'-'*35} {'-'*10} {'-'*10}")

    # Small workloads (C as baseline)
    c_compute = max(best_c - 20, 0.1)
    print(f"  {'--- Small workloads ---':<35s}")
    print(f"  {'C (gcc -O2)':<35s} {avg_c:>10.0f} ms {'1.0x':>10s}")
    print(f"  {'CPython':<35s} {avg_py:>10.0f} ms {avg_py/c_compute:>9.1f}x")
    print(f"  {'Nova Native (build+run)':<35s} {avg_nn:>10.0f} ms {avg_nn/c_compute:>9.1f}x")
    print(f"  {'Nova VM (interpreted)':<35s} {avg_vm:>10.0f} ms {avg_vm/c_compute:>9.1f}x")

    print()
    print(f"  {'--- Heavy workloads (sum_to='+str(heavy['sum_to']//1000)+'K, primes='+str(heavy['primes'])+', fib='+str(heavy['fib'])+') ---':<35s}")
    if best_ch and best_ch > 0:
        ch_compute = max(best_ch - 20, 0.1)
        print(f"  {'C (gcc -O2)':<35s} {avg_ch:>10.0f} ms {'1.0x':>10s}")
        print(f"  {'CPython':<35s} {avg_ph:>10.0f} ms {avg_ph/ch_compute:>9.1f}x")
        print(f"  {'Nova Native (build+run)':<35s} {avg_nh:>10.0f} ms {avg_nh/ch_compute:>9.1f}x")

    print()
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
