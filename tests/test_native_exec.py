import os
import subprocess
import sys
import tempfile
import pytest

BOOTSTRAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(BOOTSTRAP_DIR, "bootstrap", "main.py")


def _find_gcc():
    bundled = os.path.join(BOOTSTRAP_DIR, "gcc", "bin", "gcc.exe")
    if os.path.isfile(bundled):
        return bundled
    for path in os.environ.get("PATH", "").split(os.pathsep):
        cand = os.path.join(path, "gcc")
        if os.name == "nt":
            cand += ".exe"
        if os.path.isfile(cand):
            return cand
    return None


def _build_and_run(source: str, expected: str):
    if not _find_gcc():
        pytest.skip("GCC not found — native execution tests require GCC")

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "test.nv")
        with open(src_path, "w") as f:
            f.write(source)

        result = subprocess.run(
            [sys.executable, MAIN_PY, "build", src_path],
            capture_output=True, text=True, timeout=120,
            cwd=BOOTSTRAP_DIR
        )
        assert result.returncode == 0, f"Build failed:\n{result.stderr}"

        exe_path = src_path.rsplit(".", 1)[0]
        if os.name == "nt":
            exe_path += ".exe"

        assert os.path.isfile(exe_path), f"Executable not produced at {exe_path}"

        result = subprocess.run(
            [exe_path],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Executable failed:\n{result.stderr}"
        assert result.stdout == expected, (
            f"Output mismatch:\nExpected: {expected!r}\nGot: {result.stdout!r}"
        )


class TestNativeExec:
    def test_hello_world(self):
        _build_and_run(
            'print("hello world")',
            "hello world\n"
        )

    def test_arithmetic(self):
        _build_and_run(
            'print(2 + 3 * 4)',
            "14\n"
        )

    def test_function_call(self):
        _build_and_run(
            'def add(a, b) { return a + b }\nprint(add(10, 20))',
            "30\n"
        )

    def test_string_concat(self):
        _build_and_run(
            'print("hello " + "world")',
            "hello world\n"
        )

    def test_string_interpolation(self):
        _build_and_run(
            'n = 42\nprint("The answer is {n}")',
            "The answer is 42\n"
        )

    def test_list_basic(self):
        _build_and_run(
            'xs = [1, 2, 3]\nprint(len(xs))\nprint(xs[0])\nprint(xs[2])',
            "3\n1\n3\n"
        )

    def test_dict_basic(self):
        _build_and_run(
            'd = {"x": 10, "y": 20}\nprint(d.get("x"))\nprint(d.has("z"))',
            "10\n0\n"
        )

    def test_if_else(self):
        _build_and_run(
            'x = 5\nif x > 3 { print("big") } else { print("small") }',
            "big\n"
        )

    def test_while_loop(self):
        _build_and_run(
            'i = 0\nwhile i < 3 { print(i)\ni = i + 1 }',
            "0\n1\n2\n"
        )

    def test_for_in_loop(self):
        _build_and_run(
            'for x in [10, 20, 30] { print(x) }',
            "10\n20\n30\n"
        )

    def test_list_comprehension(self):
        _build_and_run(
            'xs = [x * 2 for x in [1, 2, 3]]\nprint(xs[0])\nprint(xs[1])\nprint(xs[2])',
            "2\n4\n6\n"
        )

    def test_len_string(self):
        _build_and_run(
            'print(len("hello"))',
            "5\n"
        )

    def test_builtin_abs(self):
        _build_and_run(
            'print(abs(-5))',
            "5\n"
        )

    def test_builtin_min_max(self):
        _build_and_run(
            'print(min(3, 7))\nprint(max(3, 7))',
            "3\n7\n"
        )

    def test_builtin_type(self):
        _build_and_run(
            'print(type(42))\nprint(type("hi"))',
            "int\nstring\n"
        )

    def test_try_catch(self):
        _build_and_run(
            'try { throw("err") } catch e { print("caught") }',
            "caught\n"
        )
