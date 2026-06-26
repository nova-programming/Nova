#!/usr/bin/env python3
"""Local CI pipeline - catch platform-specific issues before pushing to GitHub.

Usage:
    python ci_test.py              # full pipeline
    python ci_test.py --quick      # skip time-consuming self-hosted build
    python ci_test.py --linux-asm  # generate + verify Linux-target assembly
    python ci_test.py --arm64-asm  # generate + verify ARM64/macOS assembly
"""
import sys, os, subprocess, argparse

NOVA_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(NOVA_DIR)
sys.path.insert(0, os.path.join(NOVA_DIR, 'bootstrap'))

PASS, FAIL = 0, 0

def test(name, fn):
    global PASS, FAIL
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    try:
        fn()
        print(f"  [PASS]")
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        FAIL += 1

def run(cmd, **kw):
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()[:500]
        raise RuntimeError(f"exit {res.returncode}: {err}")
    return res.stdout

def test_pytest():
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        capture_output=True, text=True, timeout=120
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip()[:1000])
    print(res.stdout.strip().split('\n')[-3:])

def test_galaxy():
    run([sys.executable, "-m", "unittest", "tests.test_galaxy", "-v"])

def test_installers():
    run([sys.executable, "-m", "unittest", "tests.test_installers", "-v"])

def test_codegen_x86():
    run([sys.executable, "-m", "unittest", "tests.test_codegen_x86_64", "-v"])

def test_codegen_arm64():
    run([sys.executable, "-m", "unittest", "tests.test_codegen_arm64", "-v"])

def test_asm_checks():
    """Generate and verify assembly for all target combos - no .globl, correct entry point."""
    from main import expand_imports
    from lexer.tokenizer import tokenize
    from parser.parser import Parser
    from compiler.type_checker import TypeInferer

    test_src = 'print("Hello from Nova CI")\n'
    tokens = tokenize(test_src)
    ast = Parser(tokens).parse()

    def check_target(arch, os_name, expected_entry):
        a = expand_imports(ast[:], NOVA_DIR, target_arch=arch, target_os=os_name)
        TypeInferer().infer(a)
        if arch == 'arm64':
            from compiler.backend.arm64.codegen import Arm64Codegen
            codegen = Arm64Codegen(a, set(), 0, os_name)
        else:
            from compiler.backend.x86_64.codegen import X86_64Codegen
            codegen = X86_64Codegen(a, set(), 0, os_name)
        asm = codegen.generate()

        for i, line in enumerate(asm.split('\n'), 1):
            s = line.strip()
            if '.globl' in s:
                raise RuntimeError(f"[{arch}/{os_name}] .globl at line {i}")
            if s == f'{expected_entry}:' or s.startswith(f'{expected_entry}:'):
                break
        else:
            raise RuntimeError(f"[{arch}/{os_name}] entry '{expected_entry}:' not found")

    check_target('x86_64', 'linux', 'main')
    check_target('x86_64', 'windows', '_main')
    check_target('arm64', 'linux', 'main')
    check_target('arm64', 'windows', '_main')
    check_target('arm64', 'macos', '_main')
    print("  All targets verified: no .globl, correct entry points [OK]")

def test_selfhosted_build():
    """Build nova.nv with bootstrap, then use stage1 to build a test program."""
    with open('ci-tmp-test.nv', 'w') as f:
        f.write('print("Self-hosted Nova OK")\n')

    run([sys.executable, 'bootstrap/main.py', 'build', '-o', 'nova-stage1', 'nova.nv'],
        cwd=NOVA_DIR, timeout=120)

    run(['./nova-stage1', 'build', 'ci-tmp-test.nv'],
        cwd=NOVA_DIR, timeout=120)

    result = run(['./ci-tmp-test'], cwd=NOVA_DIR, timeout=30)
    if 'Self-hosted Nova OK' not in result:
        raise RuntimeError(f"Unexpected output: {result[:200]}")
    print(f"  Stage2 output: {result.strip()}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--linux-asm', action='store_true')
    ap.add_argument('--arm64-asm', action='store_true')
    args = ap.parse_args()

    print(f"Nova CI Pipeline - {NOVA_DIR}")
    print(f"Python: {sys.version}")

    test("1. Pytest suite (all 245+ tests)", test_pytest)
    test("2. Galaxy tests", test_galaxy)
    test("3. Installer tests", test_installers)

    if not args.arm64_asm:
        test("4a. x86_64 codegen tests", test_codegen_x86)
    if not args.linux_asm:
        test("4b. ARM64 codegen test", test_codegen_arm64)

    test("5. Cross-target assembly validation", test_asm_checks)

    if not args.quick and not args.linux_asm and not args.arm64_asm:
        if sys.platform != 'win32':
            test("6. Self-hosted bootstrap (stage1 -> stage2)", test_selfhosted_build)
        else:
            print("\n  [SKIP] Self-hosted build requires GCC (Linux/macOS/WSL)")

    print(f"\n{'='*60}")
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print(f"{'='*60}")
    return 1 if FAIL > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
