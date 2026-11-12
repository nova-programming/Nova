"""Tests for the public API layer: module-qualified calls, camelCase members,
freed soft keywords, the `text` module, and the build-cache fingerprint.

Each feature is checked in all three pipelines where relevant:
VM (python bootstrap `dev`), Python-bootstrap native, and the self-hosted compiler.
"""
import importlib.util
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bootstrap"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import names  # bootstrap/names.py
from lexer.tokenizer import tokenize
from parser.parser import Parser
from test_native_exec import _find_gcc, _run_vm, MAIN_PY  # noqa: E402


def _vm_output(source):
    r = _run_vm(source)
    assert r.returncode == 0, r.stdout + r.stderr
    return "\n".join(l for l in r.stdout.splitlines() if not l.startswith("[Resolver]")) + "\n"


def _native_output(source, tmp_path):
    if not _find_gcc():
        pytest.skip("GCC not found")
    from conftest import gcc_env
    env = gcc_env()
    if env is None:
        pytest.skip("64-bit GCC not found")
    src = tmp_path / "prog.nv"
    src.write_text(source, encoding="utf-8")
    b = subprocess.run([sys.executable, MAIN_PY, "build", str(src)], capture_output=True, text=True,
                       timeout=300, cwd=ROOT, env=env)
    exe = tmp_path / ("prog.exe" if os.name == "nt" else "prog")
    assert exe.exists(), b.stdout[-1500:] + b.stderr[-1500:]
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    return r.stdout


# ---- names.nv is retired in favor of automatic post-parse resolution ---------

def test_names_nv_retired_and_not_needed():
    # stdlib/names.nv is retired; module resolution is dynamic from AST def statements
    assert not os.path.exists(os.path.join(ROOT, "stdlib", "names.nv"))


# ---- module-qualified calls --------------------------------------------------

MODULE_PROGRAM = (
    "import fs\nimport path\nimport env\n"
    'p = path.join("a", "b", "c.txt")\nprint(p)\nprint(path.base(p))\nprint(path.ext(p))\n'
    'print(path.join(["x", "y"]))\n'
    'fs.write("names_mod_tmp.txt", "hi there")\nprint(fs.read("names_mod_tmp.txt"))\n'
    'fs.delete("names_mod_tmp.txt")\nprint(fs.exists("names_mod_tmp.txt"))\n'
    'print(env.get("NOVA_NAMES_TEST_UNSET") == "")\n'
)


def test_module_calls_vm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = _vm_output(MODULE_PROGRAM)
    assert out.splitlines()[:6] == ["a/b/c.txt", "c.txt", ".txt", "x/y", "hi there", "0"]


def test_module_calls_native_and_selfhost(tmp_path, selfhost_run):
    native = _native_output(MODULE_PROGRAM, tmp_path).split()
    assert native[:5] == ["a/b/c.txt", "c.txt", ".txt", "x/y", "hi"]
    r, _ = selfhost_run(MODULE_PROGRAM, "names_mod")
    assert r.returncode == 0
    assert r.stdout.split() == native


def test_unknown_module_member_has_suggestion():
    r = _run_vm('import fs\nprint(fs.reed("x"))\n')
    assert r.returncode != 0
    assert "module 'fs' has no function 'reed'" in r.stdout + r.stderr
    assert "fs.read" in r.stdout + r.stderr


def test_module_names_do_not_touch_unimported_or_plain_variables():
    # `fs` is a plain variable here (no import): no rewriting, normal field access semantics
    ast = Parser(tokenize("fs = 5\nprint(fs)\n")).parse()
    assert [type(n).__name__ for n in ast] == ["Assignment", "Print"]


def test_import_alias_is_supported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = _vm_output('import path as p\nprint(p.base("a/b.txt"))\n')
    assert out.strip() == "b.txt"


# ---- camelCase members -------------------------------------------------------

def test_camel_case_members_parse_to_internal_names():
    ast = Parser(tokenize("x = alloc[int](4)\ny = x.asList(count=4)\n")).parse()
    call = ast[1].value
    assert call.method_name == "as_list"
    ast2 = Parser(tokenize("@raw {\n  q = p.valueByte\n  p.valueDword = 3\n}\n")).parse()
    props = repr(ast2)
    assert "value_byte" in props and "value_dword" in props
    assert "valueByte" not in props and "valueDword" not in props


# ---- freed soft keywords ------------------------------------------------------

SOFT_PROGRAM = (
    "read = 1\nwrite = 2\nclose = 3\napi = 4\nprint(read + write + close + api)\n"
    'fd = open("{path}", "w")\nwrite(fd, "hello")\nclose(fd)\n'
    'fd2 = open("{path}", "r")\ndata = read(fd2)\nclose(fd2)\nprint(data)\n'
)


def _soft_program(tmp_path):
    return SOFT_PROGRAM.replace("{path}", str(tmp_path / "soft.txt").replace("\\", "/"))


def test_soft_keywords_vm(tmp_path):
    assert _vm_output(_soft_program(tmp_path)).split() == ["10", "hello"]


def test_soft_keywords_selfhost(selfhost_run, tmp_path):
    r, _ = selfhost_run(_soft_program(tmp_path), "names_soft")
    assert r.returncode == 0 and r.stdout.split() == ["10", "hello"]
    # The write()/close() must really hit disk, not just parse: read-back alone could succeed
    # on a zero-length file if write() were silently dropped.
    assert (tmp_path / "soft.txt").read_text() == "hello"


def test_soft_keywords_native(tmp_path):
    # Regression: the Python-bootstrap native backends read WriteFile.file / CloseFile.value /
    # ReadFile.file (real fields are .fd), ignored the open() mode, and passed _fputs its
    # arguments in the wrong order on x86_64 -- so native `open`/`write`/`read`/`close`
    # failed outright or wrote garbage.
    out = _native_output(_soft_program(tmp_path), tmp_path)
    assert out.split() == ["10", "hello"]
    assert (tmp_path / "soft.txt").read_text() == "hello"


def test_user_functions_may_use_soft_keyword_names():
    out = _vm_output("def close() { return 9 }\ndef read(x) { return x + 1 }\nprint(close())\nprint(read(1))\n")
    assert out.split() == ["9", "2"]


# ---- text module --------------------------------------------------------------

TEXT_PROGRAM = (
    "import text\n"
    'print(text.toInt("  -42xyz"))\nprint(text.toInt("7") + 1)\n'
    'print("[" + text.trim("   hi there \\n") + "]")\n'
    'print(text.startsWith("hello", "he"))\nprint(text.endsWith("hello", "lo"))\n'
    'print(text.indexOf("hello world", "o w"))\nprint(text.indexOf("abc", "z"))\n'
    'print(text.replace("foo bar foo", "foo", "baz"))\n'
    'parts = text.split("a,b,,c", ",")\nprint(len(parts))\nprint(text.join(parts, "-"))\n'
    'print(text.repeat("ab", 3))\nprint(text.upper("Hello 1"))\nprint(text.lower("Hello 1"))\n'
)
TEXT_EXPECTED = ["-42", "8", "[hi", "there]", "1", "1", "4", "-1", "baz", "bar", "baz",
                 "4", "a-b--c", "ababab", "HELLO", "1", "hello", "1"]


def test_text_module_all_pipelines(tmp_path, selfhost_run):
    vm = _vm_output(TEXT_PROGRAM).split()
    assert vm == TEXT_EXPECTED
    assert _native_output(TEXT_PROGRAM, tmp_path).split() == TEXT_EXPECTED
    r, _ = selfhost_run(TEXT_PROGRAM, "names_text")
    assert r.returncode == 0 and r.stdout.split() == TEXT_EXPECTED


# ---- build cache fingerprint ---------------------------------------------------

def test_build_fingerprint_tracks_siblings_and_stdlib(tmp_path):
    spec = importlib.util.spec_from_file_location("nova_main_fp", MAIN_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    main = tmp_path / "main.nv"
    main.write_text("import helper\nprint(1)\n")
    helper = tmp_path / "helper.nv"
    helper.write_text("def f() { return 1 }\n")
    first = mod._build_fingerprint(str(main))
    assert mod._build_fingerprint(str(main)) == first
    helper.write_text("def f() { return 2 }\n")
    assert mod._build_fingerprint(str(main)) != first


# ---- migration tooling ---------------------------------------------------------

OLD_STYLE = (
    "import fs\n"
    '# fs_read is mentioned in a comment and "fs_write(" in a string\n'
    'p = path_join2("a", "b")\n'
    "print(path_basename(p))\n"
    'fs_write("x.txt", "fs_read(")\n'
    "q = alloc[int](3)\n"
    "l = q.as_list(count=3)\n"
    "def fs_read2() { return 1 }\n"
)


def test_modernize_rewrites_code_but_not_strings_comments_or_own_defs():
    import api_tools
    new = api_tools.modernize_source(OLD_STYLE)
    assert 'p = path.join("a", "b")' in new
    assert "print(path.base(p))" in new
    assert 'fs.write("x.txt", "fs_read(")' in new          # string literal untouched
    assert '# fs_read is mentioned in a comment and "fs_write(" in a string' in new
    assert "q.asList(count=3)" in new
    assert "def fs_read2()" in new                          # own definition untouched
    assert new.splitlines()[:2] == ["import fs", "import path"]  # needed import added
    assert api_tools.modernize_source(new) == new           # idempotent


def test_modernized_program_behaves_like_the_original(tmp_path):
    import api_tools
    old = ('import fs\nimport path\nfs_write("{p}", "same")\nprint(fs_read("{p}"))\n'
           'print(path_basename("a/b.txt"))\nfs_delete("{p}")\n')
    old = old.replace("{p}", str(tmp_path / "m.txt").replace("\\", "/"))
    assert _vm_output(api_tools.modernize_source(old)) == _vm_output(old)


def test_lint_reports_old_spellings_and_accepts_camel_case(tmp_path):
    f = tmp_path / "lint.nv"
    f.write_text('import fs\nx = fs_read("a")\ndef readAll() { return 1 }\ndef BadName() { return 2 }\n')
    r = subprocess.run([sys.executable, MAIN_PY, "lint", str(f)], capture_output=True, text=True, cwd=ROOT)
    assert "STYLE003" in r.stdout and "fs.read" in r.stdout
    assert "'readAll'" not in r.stdout                      # camelCase is allowed
    assert "STYLE002" in r.stdout and "BadName" in r.stdout
    strict = subprocess.run([sys.executable, MAIN_PY, "lint", "--strict", str(f)],
                            capture_output=True, text=True, cwd=ROOT)
    assert strict.returncode != 0


def test_fmt_modernize_only_writes_with_write_flag(tmp_path):
    f = tmp_path / "m.nv"
    f.write_text('x = path_basename("a/b")\n')
    check = subprocess.run([sys.executable, MAIN_PY, "fmt", "--modernize", str(f)],
                           capture_output=True, text=True, cwd=ROOT)
    assert check.returncode != 0 and f.read_text() == 'x = path_basename("a/b")\n'
    subprocess.run([sys.executable, MAIN_PY, "fmt", "--write", "--modernize", str(f)],
                   capture_output=True, text=True, cwd=ROOT)
    assert f.read_text() == 'import path\nx = path.base("a/b")\n'


def test_ui_and_audio_module_names_resolve():
    from parser.parser import Parser
    from lexer.tokenizer import tokenize
    src = "import ui\nimport audio\nui.open(\"Test\", 100, 100)\naudio.beep(440, 50)\n"
    ast = Parser(tokenize(src)).parse()
    # Should resolve ui.open to Call("ui_open") and audio.beep to Call("audio_beep")
    calls = [n for n in ast if type(n).__name__ == "Call"]
    names_called = [c.name for c in calls]
    assert "ui_open" in names_called
    assert "audio_beep" in names_called


# ---- dynamic module resolution & user modules --------------------------------

def test_user_written_module_dynamic_resolution(selfhost, selfhost_run):
    stage1, work, env = selfhost
    mod_file = work / "calc_helper.nv"
    mod_file.write_text(
        'def add(a: int, b: int) -> int {\n'
        '    return a + b\n'
        '}\n'
        'def multiply_nums(a: int, b: int) -> int {\n'
        '    return a * b\n'
        '}\n',
        encoding="utf-8"
    )
    src = (
        'import calc_helper\n'
        'def main() {\n'
        '    print(calc_helper.add(15, 27))\n'
        '    print(calc_helper.multiplyNums(6, 7))\n'
        '}\n'
        'main()\n'
    )
    r, _ = selfhost_run(src, "test_user_mod_main")
    assert r.returncode == 0
    assert r.stdout.split() == ["42", "42"]


def test_user_module_typo_suggestion(selfhost):
    stage1, work, env = selfhost
    from conftest import run_built, EXE
    mod_file = work / "calc_helper.nv"
    mod_file.write_text(
        'def add(a: int, b: int) -> int {\n'
        '    return a + b\n'
        '}\n'
        'def multiply_nums(a: int, b: int) -> int {\n'
        '    return a * b\n'
        '}\n',
        encoding="utf-8"
    )
    src_file = work / "test_typo_main.nv"
    src_file.write_text(
        'import calc_helper\n'
        'def main() {\n'
        '    print(calc_helper.multiplyNum(6, 7))\n'
        '}\n'
        'main()\n',
        encoding="utf-8"
    )
    exe = work / ("test_typo_main" + EXE)
    if exe.exists():
        exe.unlink()
    b = run_built([str(stage1), "build", str(src_file)], str(exe), capture_output=True, text=True,
                  timeout=60, cwd=work, env=env)
    assert b.returncode != 0
    err_out = b.stdout + b.stderr
    assert "module 'calc_helper' has no function 'multiplyNum'" in err_out
    assert "did you mean 'calc_helper.multiplyNums'?" in err_out


def test_shadowed_module_name(selfhost_run):
    src = (
        'import fs\n'
        'def run() {\n'
        '    fs = 42\n'
        '    print(fs)\n'
        '}\n'
        'run()\n'
    )
    r, _ = selfhost_run(src, "test_shadow_fs")
    assert r.returncode == 0
    assert r.stdout.strip() == "42"




# ---- legacy flat names and keyword-named members -----------------------------------------------

LEGACY_PROGRAM = (
    "import text\nimport json\nimport buffer\nimport time\n"
    'print(text_to_int("12"))\n'
    'print(json_as_int(json.parse("5")))\n'
    "b = new_buffer(8)\nb.set_u8(0, 9)\nprint(b.get_u8(0))\n"
    "print(len(time.now()) > 0)\n"
)


def test_legacy_snake_case_names_still_resolve_selfhost(selfhost_run):
    # Module members are camelCase (fs.writeAtomic); the old flat spellings (fs_write_atomic, text_to_int,
    # new_buffer, ...) must keep compiling. Regression: they linked as undefined `_text_to_int` etc.
    r, _ = selfhost_run(LEGACY_PROGRAM, "names_legacy")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["12", "5", "9", "1"]


def test_keywords_may_name_module_functions():
    # `has` and `alloc` are keywords, but json.has / buffer.alloc are public members: only the `def` name is freed.
    ast = Parser(tokenize("def has(a, b) { return 1 }\ndef alloc(n) { return n }\n")).parse()
    assert [n.name for n in ast if type(n).__name__ == "Function"] == ["has", "alloc"]
    # ...while `x has y` and alloc[int](n) are still the operator / intrinsic
    ast2 = Parser(tokenize('ok = "abc" has "b"\nq = alloc[int](4)\n')).parse()
    assert type(ast2[1].value).__name__ == "Alloc"
