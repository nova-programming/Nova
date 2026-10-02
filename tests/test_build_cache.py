"""The self-hosted driver's incremental cache must never return a stale executable."""
import os
import subprocess

EXE = ".exe" if os.name == "nt" else ""


def _build(selfhost, name, source, extra=None):
    stage1, work, env = selfhost
    src = work / (name + ".nv")
    src.write_text(source, encoding="utf-8")
    for fname, text in (extra or {}).items():
        (work / fname).write_text(text, encoding="utf-8")
    r = subprocess.run([str(stage1), "build", str(src)], capture_output=True, text=True,
                       timeout=300, cwd=work, env=env)
    out = subprocess.run([str(work / (name + EXE))], capture_output=True, text=True, timeout=60).stdout.strip()
    return r.stdout, out


def test_unchanged_source_is_cached(selfhost):
    first, out1 = _build(selfhost, "cache_same", "print(1)\n")
    second, out2 = _build(selfhost, "cache_same", "print(1)\n")
    assert out1 == out2 == "1"
    assert "[cached]" not in first and "[cached]" in second


def test_same_length_edit_rebuilds(selfhost):
    """Regression: the cache keyed on file size only, so 'print(1)' -> 'print(2)' reused the old exe."""
    _, out1 = _build(selfhost, "cache_edit", "print(1)\n")
    log, out2 = _build(selfhost, "cache_edit", "print(2)\n")
    assert (out1, out2) == ("1", "2")
    assert "[cached]" not in log


def test_edit_to_local_import_rebuilds(selfhost):
    main = "import cache_helper\nprint(helper_value())\n"
    _, out1 = _build(selfhost, "cache_imp", main, {"cache_helper.nv": "def helper_value() { return 1 }\n"})
    _, out2 = _build(selfhost, "cache_imp", main, {"cache_helper.nv": "def helper_value() { return 2 }\n"})
    assert (out1, out2) == ("1", "2")
