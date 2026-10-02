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


def _run_vm(source: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "test.nv")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(source)
        return subprocess.run(
            [sys.executable, MAIN_PY, "dev", src_path],
            capture_output=True, text=True, timeout=30, cwd=BOOTSTRAP_DIR,
        )


def _assert_vm_native_parity(source: str):
    vm_result = _run_vm(source)
    assert vm_result.returncode == 0, vm_result.stderr
    vm_output = "\n".join(
        line for line in vm_result.stdout.splitlines()
        if not line.startswith("[Resolver]")
    )
    if vm_result.stdout.endswith("\n"):
        vm_output += "\n"
    if not _find_gcc():
        pytest.skip("GCC not found — native parity tests require GCC")
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "test.nv")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(source)
        build = subprocess.run(
            [sys.executable, MAIN_PY, "build", src_path],
            capture_output=True, text=True, timeout=120, cwd=BOOTSTRAP_DIR,
        )
        assert build.returncode == 0, build.stderr
        exe_path = src_path.rsplit(".", 1)[0] + (".exe" if os.name == "nt" else "")
        native_result = subprocess.run(
            [exe_path], capture_output=True, text=True, timeout=30,
        )
        assert native_result.returncode == 0, native_result.stderr
        assert native_result.stdout == vm_output


class TestNativeExec:
    def test_vm_native_parity_for_fs_helpers(self):
        if not _find_gcc():
            pytest.skip("GCC not found — native parity tests require GCC")
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "portable.txt").replace("\\", "/")
            source = (
                "import fs\n"
                f'fs_write("{data_path}", "portable")\n'
                f'print(fs_read("{data_path}"))\n'
            )
            _assert_vm_native_parity(source)

    def test_vm_native_parity_for_control_flow_and_collections(self):
        _assert_vm_native_parity(
            'xs = [1, 2, 3]\n'
            'total = 0\n'
            'for x in xs { total = total + x }\n'
            'd = {"total": total}\n'
            'if d.get("total") == 6 { print("ok") }\n'
        )

    def test_vm_native_parity_for_environment_helpers(self):
        _assert_vm_native_parity(
            'import env\n'
            'env_set("NOVA_PARITY_ENV", "portable")\n'
            'print(env_get("NOVA_PARITY_ENV"))\n'
        )

    def test_vm_native_parity_for_no_shell_process_run(self):
        if os.name == "nt":
            source = (
                'import process\n'
                'print(process_run(["cmd", "/c", "exit 7"]))\n'
            )
        else:
            source = (
                'import process\n'
                'print(process_run(["sh", "-c", "exit 7"]))\n'
            )
        _assert_vm_native_parity(source)

    def test_vm_native_parity_for_scalar_value_boxing(self):
        _assert_vm_native_parity(
            'boxed = value_box_int(42)\n'
            'print(nova_value_kind(boxed))\n'
            'print(value_unbox_int(boxed))\n'
            'flag = value_box_bool(true)\n'
            'print(value_unbox_bool(flag))\n'
            'text = value_box_string("Nova")\n'
            'print(value_unbox_string(text))\n'
            'items = [1, 2, 3]\n'
            'print(nova_value_list_count(items))\n'
            'print(nova_value_list_item(items, 1))\n'
            'record = {"name": "Nova", "version": 1}\n'
            'print(nova_value_dict_count(record))\n'
            'pairs = nova_value_dict_items(record)\n'
            'print(nova_value_list_count(pairs))\n'
            'print(nova_value_is_list(items))\n'
            'print(nova_value_is_dict(record))\n'
            'print(nova_value_is_string(text))\n'
            'print(nova_value_kind(value_box_list(items)))\n'
            'print(nova_value_kind(value_box_dict(record)))\n'
            'nova_value_release(text)\n'
            'nova_value_release(boxed)\n'
        )

    def test_vm_native_parity_for_invalid_value_collection_access(self):
        _assert_vm_native_parity(
            'value = value_box_int(42)\n'
            'print(nova_value_kind(value))\n'
            'print(nova_value_kind(value_box_list(value)))\n'
            'print(nova_value_kind(value_box_dict(value)))\n'
            'print(nova_value_list_count(value))\n'
            'print(nova_value_list_item(value, 0))\n'
            'print(nova_value_dict_count(value))\n'
            'print(nova_value_list_count(nova_value_dict_keys(value)))\n'
            'print(nova_value_list_count(nova_value_dict_values(value)))\n'
            'print(nova_value_list_count(nova_value_dict_items(value)))\n'
            'print(nova_value_is_list(value))\n'
            'print(nova_value_is_dict(value))\n'
            'print(nova_value_is_string(value))\n'
        )

    def test_vm_native_parity_for_json_stringify(self):
        _assert_vm_native_parity(
            'import json\n'
            'print(jsonStringify(valueBoxNone()))\n'
            'print(jsonStringify(valueBoxBool(true)))\n'
            'print(valueUnboxInt(valueBoxInt(17)))\n'
            'print(valueUnboxString(valueBoxString("alias")))\n'
            'print(json_stringify(42))\n'
            'print(json_stringify("Nova"))\n'
            'print(json_stringify([1, "two", value_box_bool(false)]))\n'
            'print(json_stringify({"name": "Nova"}))\n'
        )

    def test_vm_native_parity_for_file_management_helpers(self):
        if not _find_gcc():
            pytest.skip("GCC not found — native parity tests require GCC")
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, "source.txt").replace("\\", "/")
            copy_path = os.path.join(tmpdir, "copy.txt").replace("\\", "/")
            moved_path = os.path.join(tmpdir, "moved.txt").replace("\\", "/")
            source = (
                "import fs\n"
                f'fs_write("{source_path}", "portable")\n'
                f'print(fs_copy("{source_path}", "{copy_path}"))\n'
                f'print(fs_move("{copy_path}", "{moved_path}"))\n'
                f'print(fs_read("{moved_path}"))\n'
                f'print(fs_delete("{moved_path}"))\n'
                f'print(fs_exists("{moved_path}"))\n'
            )
            _assert_vm_native_parity(source)

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

    def test_integer_division_truncates_toward_zero(self):
        _build_and_run(
            'print(-5 / 2)\nprint(5 / -2)',
            "-2\n-2\n"
        )

    def test_string_slice(self):
        _build_and_run(
            's = "hello world"\nprint(s[0:5])\nprint(s[6:11])\nprint(s[0])',
            "hello\nworld\nh\n"
        )

    def test_try_catch(self):
        _build_and_run(
            'try { throw("err") } catch e { print("caught") }',
            "caught\n"
        )

    def test_dynamic_call_is_rejected_for_native_builds(self):
        if not _find_gcc():
            pytest.skip("GCC not found — native execution tests require GCC")

        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, "dynamic.nv")
            with open(src_path, "w") as f:
                f.write('def greet() { print("hi") }\ncall("greet", [])\n')

            result = subprocess.run(
                [sys.executable, MAIN_PY, "build", src_path],
                capture_output=True, text=True, timeout=120,
                cwd=BOOTSTRAP_DIR
            )
            assert result.returncode != 0
            assert "call(name, args) is VM-only" in (result.stdout + result.stderr)
