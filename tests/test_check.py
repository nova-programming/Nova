import os
import subprocess
import sys
import tempfile
import json


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "bootstrap", "main.py")


def run_check(source):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "check.nv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        return subprocess.run(
            [sys.executable, MAIN, "check", path],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30,
        )


def test_check_accepts_valid_program():
    result = run_check("value: int = 2 + 3\nprint(value)\n")
    assert result.returncode == 0
    assert "Checked check.nv successfully." in result.stdout


def test_check_reports_syntax_context():
    result = run_check("value = (\n")
    assert result.returncode != 0
    assert "Error" in result.stdout
    assert "value = (" in result.stdout


def test_lint_is_advisory_by_default_and_strict_is_opt_in():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "style.nv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("def BadName() {  \n    print(1)\n}\n")
        advisory = subprocess.run(
            [sys.executable, MAIN, "lint", path],
            capture_output=True, text=True, cwd=ROOT, timeout=30,
        )
        strict = subprocess.run(
            [sys.executable, MAIN, "lint", "--strict", path],
            capture_output=True, text=True, cwd=ROOT, timeout=30,
        )
        assert advisory.returncode == 0
        assert strict.returncode != 0
        assert "trailing whitespace" in advisory.stdout
        assert "snake_case" in advisory.stdout


def test_fmt_check_and_write_are_explicit():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "style.nv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("print(1)  \r\n")
        check = subprocess.run(
            [sys.executable, MAIN, "fmt", path],
            capture_output=True, text=True, cwd=ROOT, timeout=30,
        )
        assert check.returncode != 0
        write = subprocess.run(
            [sys.executable, MAIN, "fmt", "--write", path],
            capture_output=True, text=True, cwd=ROOT, timeout=30,
        )
        assert write.returncode == 0
        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == "print(1)\n"


def test_check_json_has_stable_diagnostic_code():
    result = run_check("value = (\n")
    json_result = subprocess.run(
        [sys.executable, MAIN, "check", "--json",
         os.path.join(tempfile.gettempdir(), "missing-nova-file.nv")],
        capture_output=True, text=True, cwd=ROOT, timeout=30,
    )
    assert json_result.returncode != 0
    diagnostic = json.loads(json_result.stdout.strip())
    assert diagnostic["code"] == "IO001"
    assert result.returncode != 0


def test_portable_stdlib_modules_type_check():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "portable.nv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                'import path\n'
                'import fs\n'
                'import env\n'
                'import time\n'
                'name = path_basename(path_join(["tmp", "notes.txt"]))\n'
                'simple_name = path_basename(path_join2("tmp", "notes.txt"))\n'
                'ok: int = fs_exists(name)\n'
                'content = fs_read(name)\n'
                'saved: int = fs_write(name, "hello")\n'
                'created: int = fs_mkdir("tmp-nova-check-dir")\n'
                'removed: int = fs_delete("tmp-nova-check-file")\n'
                'copied: int = fs_copy("tmp-nova-source", "tmp-nova-copy")\n'
                'moved: int = fs_move("tmp-nova-copy", "tmp-nova-moved")\n'
                'current = env_get("PATH")\n'
                'changed: int = env_set("NOVA_CHECK_ENV", "ok")\n'
                'print(name)\n'
            )
        result = subprocess.run(
            [sys.executable, MAIN, "check", path],
            capture_output=True, text=True, cwd=ROOT, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
