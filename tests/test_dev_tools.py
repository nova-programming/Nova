"""Developer-tooling features of the self-hosted compiler:

  * `test "name" { ... }` blocks, `assert`, and the `nova test` command
  * diagnostics that show the offending source line with an underline
  * call checks: calling a variable that hides a function, calling a function that does not exist
  * `nova build --os nova` (a .nva package built from one command; manifest from `#nva` comment lines)
"""
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = ".exe" if os.name == "nt" else ""
OS_DIR = os.path.join(os.path.dirname(ROOT), "baremetal_os")


def _nova(selfhost, *args, cwd=None, env_extra=None):
    stage1, work, env = selfhost
    env = dict(env)
    env.update(env_extra or {})
    return subprocess.run([str(stage1), *args], capture_output=True, text=True, timeout=300,
                          cwd=str(cwd or work), env=env)


def _write(selfhost, name, source):
    _, work, _ = selfhost
    path = work / name
    path.write_text(source, encoding="utf-8")
    return path


# ---- test blocks and `nova test` ----------------------------------------------------------------------------

PASSING = '''def add(a: int, b: int) -> int {
    return a + b
}

test "adds numbers" {
    assert(add(1, 2) == 3)
    assert(add(2, 2) == 4, "two plus two")
}

test "strings" {
    assert(len("nova") == 4)
}
'''

FAILING = PASSING + '''
test "this one fails" {
    assert(add(1, 1) == 3, "one plus one is not three")
}
'''


def test_nova_test_passes_and_exits_zero(selfhost):
    src = _write(selfhost, "dt_pass.nv", PASSING)
    r = _nova(selfhost, "test", str(src))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "running 2 test(s)" in r.stdout
    assert "test adds numbers" in r.stdout          # the name is printed without its quotes
    assert "2 passed, 0 failed" in r.stdout


def test_nova_test_reports_failures_and_exits_nonzero(selfhost):
    src = _write(selfhost, "dt_fail.nv", FAILING)
    r = _nova(selfhost, "test", str(src))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "2 passed, 1 failed" in r.stdout
    assert "assertion failed (" in r.stdout and "dt_fail.nv:" in r.stdout     # file:line of the failing assert
    assert "one plus one is not three" in r.stdout


def test_a_failing_assert_ends_only_its_own_test(selfhost):
    src = _write(selfhost, "dt_one.nv", 'test "a" {\n    assert(1 == 2)\n    print("never printed")\n}\n'
                                       'test "b" {\n    assert(1 == 1)\n}\n')
    r = _nova(selfhost, "test", str(src))
    assert "never printed" not in r.stdout
    assert "1 passed, 1 failed" in r.stdout


def test_test_blocks_are_dropped_from_normal_builds(selfhost):
    stage1, work, env = selfhost
    src = _write(selfhost, "dt_drop.nv", 'print("hello")\ntest "never compiled" {\n    assert(1 == 2)\n}\n')
    exe = work / ("dt_drop" + EXE)
    if exe.exists():
        exe.unlink()
    b = _nova(selfhost, "build", str(src))
    assert exe.exists(), b.stdout + b.stderr
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    assert r.stdout.split() == ["hello"] and r.returncode == 0


def test_assert_outside_a_test_stops_the_program(selfhost):
    stage1, work, env = selfhost
    src = _write(selfhost, "dt_assert.nv", 'print("start")\nassert(2 == 3, "arithmetic broke")\nprint("unreachable")\n')
    exe = work / ("dt_assert" + EXE)
    if exe.exists():
        exe.unlink()
    b = _nova(selfhost, "build", str(src))
    assert exe.exists(), b.stdout + b.stderr
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 1
    assert "start" in r.stdout and "arithmetic broke" in r.stdout and "unreachable" not in r.stdout


def test_nova_test_without_tests_is_an_error(selfhost):
    src = _write(selfhost, "dt_none.nv", 'print("no tests here")\n')
    r = _nova(selfhost, "test", str(src))
    assert r.returncode != 0
    assert "no test blocks found" in r.stdout


def test_test_blocks_are_type_checked_by_check(selfhost):
    src = _write(selfhost, "dt_chk.nv", 'test "typo" {\n    assert(undefined_thing == 1)\n}\n')
    r = _nova(selfhost, "check", str(src))
    assert r.returncode != 0
    assert "undefined name 'undefined_thing'" in r.stdout


# ---- diagnostics ---------------------------------------------------------------------------------------------

def test_errors_show_the_source_line_and_underline_the_token(selfhost):
    src = _write(selfhost, "dt_diag.nv", 'def greet(name: string) -> string {\n    return "hi " + name\n}\n'
                                        'message = greet("nova")\nprint(mesage)\n')
    r = _nova(selfhost, "check", str(src))
    assert r.returncode != 0
    lines = r.stdout.splitlines()
    i = next(n for n, l in enumerate(lines) if "undefined name 'mesage'" in l)
    assert lines[i + 1].strip() == "5 | print(mesage)"
    assert lines[i + 2].strip().endswith("^~~~~~") and not lines[i + 2].strip().endswith("^~~~~~~")   # six characters
    assert lines[i + 2].index("^") == lines[i + 1].index("mesage")                                   # aligned under them
    assert "did you mean 'message'?" in lines[i + 3]


# ---- call checks ---------------------------------------------------------------------------------------------

def test_calling_a_parameter_that_hides_a_function_is_an_error(selfhost):
    # Regression: this compiled, then crashed at run time (the code generator called the variable).
    src = _write(selfhost, "dt_shadow.nv", 'def width() -> int {\n    return 5\n}\n'
                                          'def stack(width: int) -> int {\n    return width() + 1\n}\n'
                                          'print(stack(2))\n')
    r = _nova(selfhost, "check", str(src))
    assert r.returncode != 0
    assert "cannot call 'width'" in r.stdout and "variable of type int" in r.stdout
    assert "rename the variable" in r.stdout


def test_a_local_assigned_later_that_hides_a_called_function_is_an_error(selfhost):
    # Regression for the Nova OS freeze: `let toast_x = metrics.toast_x(w)` - the local is assigned AFTER the call, so
    # the checker saw no variable yet, but the code generator treats every assigned name as a local and called
    # through it (address 0), panicking the kernel the first time the toast was drawn.
    lines = ["def toast_x(w: int) -> int {",
             "    return w - 5",
             "}",
             "def draw(w: int) -> int {",
             "    let toast_x = toast_x(w)",
             "    return toast_x",
             "}",
             "print(draw(100))", ""]
    src = _write(selfhost, "dt_shadow_later.nv", chr(10).join(lines))
    r = _nova(selfhost, "check", str(src))
    assert r.returncode != 0
    assert "cannot call 'toast_x'" in r.stdout and "assigned in this function" in r.stdout
    assert "rename the variable" in r.stdout


def test_a_differently_named_local_and_function_pointers_are_fine(selfhost):
    lines = ["def toast_x(w: int) -> int {",
             "    return w - 5",
             "}",
             "def draw(w: int) -> int {",
             "    let tx = toast_x(w)",
             "    return tx",
             "}",
             "def apply(f, v) {",
             "    return f(v)",
             "}",
             "print(draw(100))", ""]
    src = _write(selfhost, "dt_shadow_ok.nv", chr(10).join(lines))
    r = _nova(selfhost, "check", str(src))
    assert r.returncode == 0, r.stdout + r.stderr


def test_call_to_an_undefined_function_is_an_error_with_a_suggestion(selfhost):
    # Regression: this used to survive type checking and fail in the linker (undefined reference to `_greeet`).
    src = _write(selfhost, "dt_undef.nv", 'def greet(name: string) -> string {\n    return "hi " + name\n}\n'
                                         'print(greeet("x"))\n')
    r = _nova(selfhost, "check", str(src))
    assert r.returncode != 0
    assert "call to undefined function 'greeet'" in r.stdout
    assert "did you mean 'greet()'?" in r.stdout


def test_indirect_call_through_a_raw_address_is_still_allowed(selfhost):
    # h = mem.read_u64(..); h(v) is a legitimate low-level indirect call (the kernel's interrupt table does it)
    lines = ["def dispatch(addr: int, v: int) {",
             "    h = mem.read_u64(addr)",
             "    if h != 0 {",
             "        h(v)",
             "    }",
             "}", ""]
    source = chr(10).join(lines)
    src = _write(selfhost, "dt_indirect.nv", source)
    r = _nova(selfhost, "check", str(src))
    assert r.returncode == 0, r.stdout + r.stderr


def test_c_library_calls_are_still_allowed(selfhost):
    src = _write(selfhost, "dt_libc.nv", 'def stop(code: int) {\n    exit(code)\n}\nprint(1)\n')
    r = _nova(selfhost, "check", str(src))
    assert r.returncode == 0, r.stdout + r.stderr


# ---- nova build --os nova ------------------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(os.path.join(OS_DIR, "user.ld")), reason="Nova OS checkout not found")
def test_build_os_nova_produces_a_nva_with_the_manifest_from_the_source(selfhost, tmp_path):
    sys.path.insert(0, OS_DIR)
    import nvapack
    work = tmp_path / "app"
    work.mkdir()
    shutil.copy(os.path.join(OS_DIR, "user", "ulib.nv"), work / "ulib.nv")
    app = work / "hello_app.nv"
    app.write_text('#nva name=Hello_App id=dev.test.hello version=2.5 window=300x180 perms=fs\n'
                   'import ulib\n\ndef main() -> int {\n    puts("hello from a .nva")\n    return 0\n}\n', encoding="utf-8")
    out = tmp_path / "hello.nva"
    r = _nova(selfhost, "build", str(app), "--os", "nova", "-o", str(out), cwd=work,
              env_extra={"NOVA_OS_DIR": OS_DIR, "NOVA_PATH": str(work)})
    if not out.exists() and ("objcopy" in (r.stdout + r.stderr).lower() or "not produced" in r.stdout):
        pytest.skip("toolchain for ring-3 ELF packaging not available: " + r.stdout[-300:])
    assert out.exists(), r.stdout[-1500:] + r.stderr[-1500:]
    info = nvapack.parse(out.read_bytes())
    assert info["manifest"]["name"] == "Hello App"          # `_` is a space in name=
    assert info["manifest"]["id"] == "dev.test.hello"
    assert info["manifest"]["version"] == "2.5"
    assert info["manifest"]["window"] == "300x180"
    assert info["manifest"]["perms"] == "fs"


# ---- trailing commas -----------------------------------------------------------------------------------------

def test_trailing_commas_are_allowed_in_lists_dicts_and_calls(selfhost_run):
    source = ("def add(a: int, b: int) -> int {\n    return a + b\n}\n"
              "items = [1, 2, 3,]\n"
              "table = {\"a\": 1, \"b\": 2,}\n"
              "print(len(items))\n"
              "print(table[\"b\"])\n"
              "print(add(4, 5,))\n"
              "print(len([]))\n")
    r, _ = selfhost_run(source, "dt_trailing_commas")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["3", "2", "9", "0"]
