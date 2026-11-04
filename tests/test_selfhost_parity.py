"""Tests verifying self-hosted compiler parity for the 4 previously broken features:
1. extern def FFI symbol naming & calling convention on Windows x64.
2. List comprehension Block codegen without access violation.
3. Class methods, field assignments (self.x = ...), and method dispatch.
4. Multiple return unpacking assignment (a, b = f()) with -> (T1, T2) signature.
"""

import os
import subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_EXE = os.path.join(ROOT, "nova.exe" if os.name == "nt" else "nova")

def _run_build_and_exec(tmp_path, src_code: str, exe_name: str = "prog"):
    assert os.path.isfile(NOVA_EXE), f"nova.exe missing: {NOVA_EXE}"
    src_file = tmp_path / f"{exe_name}.nv"
    src_file.write_text(src_code, encoding="utf-8")
    out_exe = tmp_path / (f"{exe_name}.exe" if os.name == "nt" else exe_name)

    env = dict(os.environ)
    gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
    if os.path.isdir(gcc_bin):
        env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")

    # Build using self-hosted nova.exe
    build_res = subprocess.run(
        [NOVA_EXE, "build", str(src_file), "-o", str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert build_res.returncode == 0, f"Build failed:\nSTDOUT:\n{build_res.stdout}\nSTDERR:\n{build_res.stderr}"
    assert out_exe.exists(), "Output binary was not created"

    # Execute generated binary
    run_res = subprocess.run(
        [str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    return run_res

def test_extern_def_ffi_symbol_naming(tmp_path):
    """Verify extern def maps to unmangled C ABI symbols and runs with Win64 ABI."""
    src = """extern def puts(s: string) -> int

puts("PARITY_EXTERN_PUTS_OK")
"""
    res = _run_build_and_exec(tmp_path, src, "test_extern")
    assert res.returncode == 0
    assert "PARITY_EXTERN_PUTS_OK" in res.stdout

def test_list_comprehension_codegen_execution(tmp_path):
    """Verify list comprehensions evaluate as Block expressions without 0xC0000005 crash."""
    src = """nums = [1, 2, 3, 4, 5]
doubled = [x * 2 for x in nums]
total = 0
for n in doubled {
    total = total + n
}
print(total)
"""
    res = _run_build_and_exec(tmp_path, src, "test_comp")
    assert res.returncode == 0
    # 2 + 4 + 6 + 8 + 10 = 30
    assert res.stdout.strip() == "30"

def test_class_methods_and_field_assignment(tmp_path):
    """Verify class definitions with self.x mutation and method dispatch execute cleanly."""
    src = """class Counter {
    val: int
    def increment(self, amount: int) {
        self.val = self.val + amount
    }
    def get_val(self) -> int {
        return self.val
    }
}

c = Counter(10)
c.increment(5)
c.increment(20)
print(c.get_val())
"""
    res = _run_build_and_exec(tmp_path, src, "test_class")
    assert res.returncode == 0
    assert res.stdout.strip() == "35"

def test_multiple_return_assignment(tmp_path):
    """Verify multi-return functions with -> (T1, T2) annotations and unpacking assignment."""
    src = """def compute_pair() -> (int, int) {
    return 100, 250
}

a, b = compute_pair()
print(a)
print(b)
"""
    res = _run_build_and_exec(tmp_path, src, "test_multiret")
    assert res.returncode == 0
    lines = res.stdout.strip().split()
    assert lines == ["100", "250"]

def test_user_defined_main_function(tmp_path):
    """Verify user can define def main() -> int and call main() without entry-point collision."""
    src = """def main() -> int {
    print("USER_MAIN_EXECUTED_CLEANLY")
    return 77
}

code = main()
print("RETURN_CODE=" + str(code))
"""
    res = _run_build_and_exec(tmp_path, src, "test_user_main")
    assert res.returncode == 0
    assert "USER_MAIN_EXECUTED_CLEANLY" in res.stdout
    assert "RETURN_CODE=77" in res.stdout


