#!/usr/bin/env python3
"""Benchmark the Nova compiler on tests/bench/*.nv (and C twins in tests/bench/c/*.c when gcc exists).

    python tools/bench.py                       # build a stage-1 compiler from this checkout, run all
    python tools/bench.py --compiler nova.exe   # use an existing self-hosted compiler
    python tools/bench.py --runs 5 fib loops    # best of 5, only these benchmarks
    python tools/bench.py --json out.json       # also write machine-readable results

Prints build time, best run time, the output checksum (so optimizations can be compared for identical
behavior) and, where a C twin exists, the Nova/C time ratio. Not a gating test: timings are noisy.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "tests", "bench")
EXE = ".exe" if os.name == "nt" else ""


def gcc_env():
    env = dict(os.environ)
    local = os.environ.get("LOCALAPPDATA")
    for d in ([os.path.join(local, "nova", "gcc", "bin")] if local else []) + [os.path.join(os.path.expanduser("~"), ".nova", "gcc", "bin")]:
        if os.path.isdir(d):
            env["PATH"] = d + os.pathsep + env.get("PATH", "")
            break
    return env


def build_stage1(work, env):
    shutil.copytree(os.path.join(ROOT, "stdlib"), os.path.join(work, "stdlib"))
    for name in ("nova.nv", "runtime.c"):
        shutil.copy(os.path.join(ROOT, name), os.path.join(work, name))
    out = os.path.join(work, "stage1" + EXE)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "bootstrap", "main.py"), "build",
                        os.path.join(ROOT, "nova.nv"), "-o", out], capture_output=True, text=True, env=env, cwd=ROOT)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit("could not build stage-1 compiler:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    return out


def timed_runs(path, runs):
    best = None
    output = ""
    for _ in range(runs):
        t = time.perf_counter()
        try:
            r = subprocess.run([path], capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return None, "timeout"
        dt = time.perf_counter() - t
        if r.returncode != 0:
            return None, r.stdout + r.stderr
        output = r.stdout
        best = dt if best is None else min(best, dt)
    return best, output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--compiler")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--json")
    args = ap.parse_args()
    env = gcc_env()
    gcc = shutil.which("gcc", path=env["PATH"])
    names = args.names or sorted(f[:-3] for f in os.listdir(BENCH) if f.endswith(".nv"))
    results = {}
    with tempfile.TemporaryDirectory() as work:
        if args.compiler:
            compiler = os.path.abspath(args.compiler)
            for name in ("stdlib",):
                shutil.copytree(os.path.join(ROOT, name), os.path.join(work, name))
            shutil.copy(os.path.join(ROOT, "runtime.c"), os.path.join(work, "runtime.c"))
        else:
            compiler = build_stage1(work, env)
        print(f"{'benchmark':<10} {'build':>7} {'run (s)':>9} {'C (s)':>8} {'nova/C':>7}  checksum")
        for name in names:
            src = os.path.join(work, name + ".nv")
            shutil.copy(os.path.join(BENCH, name + ".nv"), src)
            t = time.perf_counter()
            subprocess.run([compiler, "build", src], capture_output=True, text=True, env=env, cwd=work)
            build = time.perf_counter() - t
            exe = os.path.join(work, name + EXE)
            if not os.path.exists(exe):
                print(f"{name:<10} build failed")
                continue
            run, out = timed_runs(exe, args.runs)
            checksum = hashlib.sha256(out.encode()).hexdigest()[:10]
            c_time = None
            c_src = os.path.join(BENCH, "c", name + ".c")
            if gcc and os.path.exists(c_src):
                c_exe = os.path.join(work, name + "_c" + EXE)
                subprocess.run([gcc, "-O2", c_src, "-o", c_exe], capture_output=True, env=env)
                if os.path.exists(c_exe):
                    c_time, c_out = timed_runs(c_exe, args.runs)
                    if c_out.split() != out.split():
                        checksum += " (C output differs!)"
            ratio = f"{run / c_time:6.2f}x" if run and c_time else "      -"
            print(f"{name:<10} {build:6.1f}s {run if run is not None else float('nan'):9.3f} "
                  f"{c_time if c_time is not None else float('nan'):8.3f} {ratio}  {checksum}")
            results[name] = {"build_s": build, "run_s": run, "c_s": c_time, "checksum": checksum}
        if args.json:
            with open(args.json, "w") as f:
                json.dump(results, f, indent=2)
    runs = [v["run_s"] for v in results.values() if v["run_s"]]
    if runs:
        geo = 1.0
        for v in runs:
            geo *= v
        print(f"geometric mean run time: {geo ** (1 / len(runs)):.3f}s over {len(runs)} benchmarks")


if __name__ == "__main__":
    main()
