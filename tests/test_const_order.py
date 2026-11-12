"""A module-level constant must be usable from code that is merged BEFORE the module that declares it.

The constant inliner in compiler.nv makes one in-order pass, so such a read used to become an uninitialised variable
(in the Nova OS kernel `peek.u32(MM_X)` silently read address 0). The type checker now inlines it.

Run: python -m pytest tests/test_const_order.py -q   (uses ./nova.exe)
"""
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA = os.path.join(ROOT, "nova.exe")


def run(tmp_path, files, main="main.nv"):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    cache = tmp_path / ".nova_cache.txt"
    if cache.exists():
        cache.unlink()
    b = subprocess.run([NOVA, "build", str(tmp_path / main), "-o", str(tmp_path / "prog.exe")],
                       capture_output=True, text=True, cwd=str(tmp_path))
    out = b.stdout + b.stderr
    if b.returncode != 0:
        return b.returncode, out
    r = subprocess.run([str(tmp_path / "prog.exe")], capture_output=True, text=True)
    return r.returncode, r.stdout


@pytest.mark.skipif(not os.path.exists(NOVA), reason="nova.exe not built")
class TestConstOrder:
    def test_const_declared_in_a_module_merged_later(self, tmp_path):
        # moda is merged before modb (its const), and uses the const several times, including in a loop
        code, out = run(tmp_path, {
            "modb.nv": "const LIMIT = 7\ndef limit() -> int { return LIMIT }\n",
            "moda.nv": "def triple() -> int {\n    t = 0\n    i = 0\n    while i < 3 {\n        t = t + LIMIT\n        i = i + 1\n    }\n    return t + LIMIT * 0\n}\n",
            "main.nv": "import moda\nimport modb\nprint(triple())\nprint(limit())\n",
        })
        assert code == 0, out
        assert out.split() == ["21", "7"]

    def test_a_local_variable_with_the_same_name_still_wins(self, tmp_path):
        code, out = run(tmp_path, {
            "modb.nv": "const SIZE = 9\n",
            "moda.nv": "def f() -> int {\n    SIZE = 4\n    return SIZE + 1\n}\n",
            "main.nv": "import moda\nimport modb\nprint(f())\n",
        })
        assert code == 0, out
        assert out.split() == ["5"]

    def test_truly_undefined_name_is_still_an_error(self, tmp_path):
        code, out = run(tmp_path, {"main.nv": "def f() -> int {\n    return NOPE_NEVER\n}\nprint(f())\n"})
        assert code != 0 and "undefined name 'NOPE_NEVER'" in out
