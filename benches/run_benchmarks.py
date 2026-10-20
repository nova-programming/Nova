"""Nova benchmark suite.

Builds each benches/*.nv program once (excluded from timing), then times repeated
executions of the resulting native binary (median of several runs) plus one VM run
for context. Distinct from tests/benchmark_overall.py, which times build+run together
to compare Nova against Python/C at a system level -- this one isolates pure execution
time so codegen-quality changes (e.g. register allocation) can be measured precisely,
without compile time or process-startup noise from Python dominating the signal.

Usage:
    python benches/run_benchmarks.py                       # run, print a table
    python benches/run_benchmarks.py --save baseline.json  # run, print, and save
    python benches/run_benchmarks.py --compare baseline.json  # run, print, and diff
"""
import argparse
import glob
import json
import os
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(ROOT, "bootstrap", "main.py")

NATIVE_RUNS = 5
VM_RUNS = 2
VM_TIMEOUT = 15
BUILD_TIMEOUT = 120
RUN_TIMEOUT = 120


def build_native(nv_path):
    exe_path = nv_path.rsplit(".", 1)[0] + (".exe" if os.name == "nt" else "")
    if os.path.exists(exe_path):
        os.remove(exe_path)
    r = subprocess.run(
        [sys.executable, MAIN_PY, "build", nv_path],
        capture_output=True, text=True, timeout=BUILD_TIMEOUT, cwd=ROOT,
    )
    if r.returncode != 0 or not os.path.isfile(exe_path):
        raise RuntimeError(f"build failed for {nv_path}:\n{r.stdout}\n{r.stderr}")
    return exe_path


def time_native(exe_path, runs=NATIVE_RUNS):
    # Discard one warm-up run: a freshly-written .exe's first execution is dominated by
    # OS-level overhead (e.g. antivirus scanning the new file) unrelated to codegen quality.
    subprocess.run([exe_path], capture_output=True, text=True, timeout=RUN_TIMEOUT)

    times = []
    output = None
    for _ in range(runs):
        t0 = time.perf_counter()
        r = subprocess.run([exe_path], capture_output=True, text=True, timeout=RUN_TIMEOUT)
        t1 = time.perf_counter()
        if r.returncode != 0:
            raise RuntimeError(f"native run of {exe_path} failed (exit {r.returncode}): {r.stderr}")
        times.append((t1 - t0) * 1000)
        output = r.stdout
    return times, output


def time_vm(nv_path, runs=VM_RUNS):
    times = []
    output = None
    try:
        for _ in range(runs):
            t0 = time.perf_counter()
            r = subprocess.run(
                [sys.executable, MAIN_PY, "dev", nv_path],
                capture_output=True, text=True, timeout=VM_TIMEOUT, cwd=ROOT,
            )
            t1 = time.perf_counter()
            if r.returncode != 0:
                raise RuntimeError(f"VM run of {nv_path} failed (exit {r.returncode}): {r.stderr}")
            times.append((t1 - t0) * 1000)
            output = r.stdout
    except subprocess.TimeoutExpired:
        return None, None
    return times, output


def run_all(names=None):
    results = {}
    nv_files = sorted(glob.glob(os.path.join(BENCH_DIR, "*.nv")))
    if names:
        nv_files = [p for p in nv_files if os.path.basename(p) in names]
    for nv_path in nv_files:
        name = os.path.basename(nv_path)
        print(f"-- {name} --")
        exe_path = build_native(nv_path)
        try:
            native_times, native_out = time_native(exe_path)
            vm_times, vm_out = time_vm(nv_path)
        finally:
            if os.path.exists(exe_path):
                os.remove(exe_path)
            asm_path = nv_path.rsplit(".", 1)[0] + ".s"
            if os.path.exists(asm_path):
                os.remove(asm_path)

        if vm_out is not None and vm_out.strip() != native_out.strip():
            print(f"  WARNING: VM/native output mismatch -- vm={vm_out!r} native={native_out!r}")

        entry = {
            "native_median_ms": statistics.median(native_times),
            "native_min_ms": min(native_times),
            "native_max_ms": max(native_times),
        }
        if vm_times:
            entry["vm_median_ms"] = statistics.median(vm_times)
        results[name] = entry

        print(f"  native: median={entry['native_median_ms']:.1f}ms  "
              f"min={entry['native_min_ms']:.1f}ms  max={entry['native_max_ms']:.1f}ms")
        if vm_times:
            print(f"  vm:     median={entry['vm_median_ms']:.1f}ms  ({VM_RUNS} runs)")
        else:
            print("  vm:     skipped (timed out)")
    return results


def compare(results, baseline_path):
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    print()
    print(f"{'benchmark':<28}{'baseline (ms)':>16}{'current (ms)':>16}{'change':>12}")
    for name, entry in results.items():
        if name not in baseline:
            print(f"{name:<28}{'(no baseline)':>16}{entry['native_median_ms']:>16.1f}")
            continue
        b = baseline[name]["native_median_ms"]
        c = entry["native_median_ms"]
        pct = (c - b) / b * 100 if b else 0.0
        label = "faster" if pct < 0 else "slower"
        print(f"{name:<28}{b:>16.1f}{c:>16.1f}{pct:>+11.1f}% ({label})")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--save", metavar="FILE", help="save results as JSON to FILE")
    ap.add_argument("--compare", metavar="FILE", help="compare results against a saved baseline JSON")
    ap.add_argument("names", nargs="*", help="only run these benchmark filenames (default: all)")
    args = ap.parse_args()

    results = run_all(names=set(args.names) if args.names else None)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved results to {args.save}")

    if args.compare:
        compare(results, args.compare)


if __name__ == "__main__":
    main()
