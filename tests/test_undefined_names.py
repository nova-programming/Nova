"""The self-hosted type checker rejects reads of names that nothing defines (a typo used to compile and silently
read an untyped zero), suggests the closest known name, and accepts every legitimate way of defining one.

Run: python -m pytest tests/test_undefined_names.py -q   (uses ./nova.exe, the self-hosted compiler)
"""
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA = os.path.join(ROOT, "nova.exe")


def build(tmp_path, source, extra=()):
    src = tmp_path / "prog.nv"
    src.write_text(source, encoding="utf-8")
    cache = os.path.join(str(tmp_path), ".nova_cache.txt")
    if os.path.exists(cache):
        os.remove(cache)
    r = subprocess.run([NOVA, "build", str(src), "-o", str(tmp_path / "prog.exe"), *extra],
                       capture_output=True, text=True, cwd=str(tmp_path))
    return r.returncode, r.stdout + r.stderr


@pytest.mark.skipif(not os.path.exists(NOVA), reason="nova.exe not built")
class TestUndefinedNames:
    def test_typo_is_an_error_with_suggestion(self, tmp_path):
        code, out = build(tmp_path, "def add(a: int, b: int) -> int {\n    total = a + b\n    return totl\n}\nprint(add(1, 2))\n")
        assert code != 0
        assert "undefined name 'totl'" in out
        assert "did you mean 'total'?" in out

    def test_unrelated_name_gets_generic_hint(self, tmp_path):
        code, out = build(tmp_path, "def f() -> int {\n    return zzzzzzzz_never_defined\n}\nprint(f())\n")
        assert code != 0
        assert "undefined name 'zzzzzzzz_never_defined'" in out
        assert "assign it before use" in out

    def test_error_points_at_the_line(self, tmp_path):
        code, out = build(tmp_path, "x = 1\n\n\nprint(nope)\n")
        assert code != 0
        assert "prog.nv:4:" in out

    @pytest.mark.parametrize("name,source", [
        ("assigned later in the function", "def f(a: int) -> int {\n    if a > 0 {\n        r = 1\n    } else {\n        r = 2\n    }\n    return r\n}\nprint(f(1))\n"),
        ("parameter", "def f(a: int) -> int {\n    return a\n}\nprint(f(3))\n"),
        ("let declaration", "def f() -> int {\n    let v = 4\n    return v\n}\nprint(f())\n"),
        ("global constant defined below its use", "def f() -> int {\n    return LIMIT\n}\nLIMIT = 9\nprint(f())\n"),
        ("for loop variable", "def f() -> int {\n    t = 0\n    for i = 0 to 4 {\n        t = t + i\n    }\n    return t\n}\nprint(f())\n"),
        ("module-qualified call", "import system\nprint(system.system_env_get(\"NOVA_X_UNSET\"))\n"),
    ])
    def test_valid_programs_still_compile(self, tmp_path, name, source):
        code, out = build(tmp_path, source)
        assert code == 0, f"{name}: {out}"

    def test_let_is_a_declaration_marker(self, tmp_path):
        """`let` used to survive as a bogus read of an undefined variable called `let`."""
        code, out = build(tmp_path, "def f() -> int {\n    let a = 1\n    let b = a + 1\n    return b\n}\nprint(f())\n")
        assert code == 0, out
        run = subprocess.run([str(tmp_path / "prog.exe")], capture_output=True, text=True)
        assert run.stdout.strip() == "2"


@pytest.mark.skipif(not os.path.exists(NOVA), reason="nova.exe not built")
def test_catch_variable_is_defined(tmp_path):
    code, out = build(tmp_path, "try {\n    throw 3\n} catch e {\n    print(e)\n}\n")
    assert code == 0, out


@pytest.mark.skipif(not os.path.exists(NOVA), reason="nova.exe not built")
def test_data_fields_may_be_comma_separated(tmp_path):
    code, out = build(tmp_path, "data Point { x: int, y: int }\np = Point(1, 2)\nprint(p.y)\n")
    assert code == 0, out
    run = subprocess.run([str(tmp_path / "prog.exe")], capture_output=True, text=True)
    assert run.stdout.strip() == "2"
