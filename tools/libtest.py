"""
Nova Library Test Helper
Run .nv test files with a single command, in VM or native mode.

Usage:
  python tools/libtest.py                         Run all tests in tests/
  python tools/libtest.py tests/test_foo.nv       Run a specific test
  python tools/libtest.py --vm                    Run in VM mode (faster)
  python tools/libtest.py --native                Run as native executable
  python tools/libtest.py --watch                 Re-run on file changes
"""
import sys
import os
import subprocess
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPILER = os.path.join(REPO_ROOT, "bootstrap", "main.py")


def find_test_files(target):
    if os.path.isfile(target):
        return [target]
    test_dir = target if os.path.isdir(target) else os.path.join(REPO_ROOT, target)
    if not os.path.isdir(test_dir):
        test_dir = os.path.join(REPO_ROOT, "tests")
    return sorted(
        os.path.join(test_dir, f)
        for f in os.listdir(test_dir)
        if f.endswith(".nv")
    )


def run_test(nv_file, use_vm):
    base = os.path.splitext(nv_file)[0]
    if use_vm:
        cmd = [sys.executable, COMPILER, "dev", nv_file]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout, r.stderr
    else:
        cmd = [sys.executable, COMPILER, "build", nv_file]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return r.returncode, r.stdout, r.stderr
        exe = base + (".exe" if sys.platform == "win32" else "")
        if not os.path.exists(exe):
            return 1, "", f"Binary not found: {exe}"
        r2 = subprocess.run([exe], capture_output=True, text=True, timeout=60)
        return r2.returncode, r2.stdout, r2.stderr


def main():
    args = sys.argv[1:]
    use_vm = True
    watch = False
    targets = []

    for a in args:
        if a == "--vm":
            use_vm = True
        elif a == "--native":
            use_vm = False
        elif a == "--watch":
            watch = True
        else:
            targets.append(a)

    test_files = []
    for t in targets or ["tests"]:
        test_files.extend(find_test_files(t))

    if not test_files:
        print("No test files found.")
        sys.exit(1)

    mode = "VM" if use_vm else "native"

    while True:
        passed = failed = 0
        print(f"\n[{time.strftime('%H:%M:%S')}] Running {len(test_files)} test(s) ({mode})")
        print("=" * 50)

        for nv_file in test_files:
            name = os.path.basename(nv_file)
            print(f"  {name} ... ", end="", flush=True)
            rc, stdout, stderr = run_test(nv_file, use_vm)
            if rc == 0:
                print("PASS")
                passed += 1
            else:
                print("FAIL")
                failed += 1
                if stdout.strip():
                    print(f"    stdout: {stdout.strip()}")
                if stderr.strip():
                    for line in stderr.strip().split("\n"):
                        print(f"    {line}")

        total = passed + failed
        print(f"\n{'=' * 50}")
        print(f"Results: {passed}/{total} passed", end="")
        if failed:
            print(f", {failed} FAILED", end="")
        print()

        if not watch:
            sys.exit(0 if failed == 0 else 1)

        for nv_file in test_files:
            with open(nv_file) as f:
                f.read()
        time.sleep(2)


if __name__ == "__main__":
    main()
