"""Guards: every shipped .nv source type-checks, and the self-hosted driver honors -o."""
import glob
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "bootstrap", "main.py")

# Fixtures that intentionally use self-hosted-only syntax (null, named/default arguments) are
# excluded here: per the Bootstrap Freeze rule in CLAUDE.md, bootstrap/*.py never gains new
# syntax for a self-hosted-only feature, so these can never "check clean" under it by design.
# They still get real compiler coverage from test_selfhost_feature_fixtures_run (below), which
# runs them through the self-hosted compiler instead.
BOOTSTRAP_INCOMPATIBLE = {"test_null.nv", "test_phase2_features.nv", "test_first_class_functions.nv", "test_enums_and_match.nv", "test_concurrency_tasks.nv", "test_baremetal_hardware.nv", "test_baremetal_allocator.nv", "test_struct_defaults.nv", "ui.nv", "ui_counter.nv", "ui_widgets.nv"}   # ui_counter.nv / ui_widgets.nv: a ui program (named arguments, trailing blocks), built and run by tests/test_ui_host.py. ui.nv: Nova OS app library, uses default arguments; compiled for real by baremetal_os/build.ps1 (user/counter_ui.nv)

SOURCES = sorted(
    p for p in (
        glob.glob(os.path.join(ROOT, "stdlib", "*.nv"))
        + glob.glob(os.path.join(ROOT, "stdlib", "backend", "*", "*.nv"))
        + glob.glob(os.path.join(ROOT, "examples", "*.nv"))
        + glob.glob(os.path.join(ROOT, "tests", "*.nv"))
        + [os.path.join(ROOT, "nova.nv")]
    )
    if os.path.basename(p) not in BOOTSTRAP_INCOMPATIBLE
)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: os.path.relpath(p, ROOT))
def test_source_checks_clean(path):
    r = subprocess.run([sys.executable, MAIN_PY, "check", path], capture_output=True, text=True,
                       cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]


@pytest.mark.parametrize("name", sorted(
    ["test_null.nv", "test_phase2_features.nv", "test_arc_lifecycle.nv", "test_first_class_functions.nv", "test_enums_and_match.nv", "test_concurrency_tasks.nv", "test_baremetal_hardware.nv", "test_baremetal_allocator.nv", "test_struct_defaults.nv"]
))
def test_selfhost_feature_fixtures_run(selfhost, name):
    """Regression coverage for the self-hosted-only feature fixtures: null, named/default
    arguments, and dict subscript access/ARC container ops. These can't go through
    test_source_checks_clean (the frozen bootstrap never learns this syntax, by design), so
    this runs each one through the self-hosted compiler and checks it actually executes."""
    stage1, work, env = selfhost
    src_path = os.path.join(ROOT, "tests", name)
    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()
    src = work / name
    src.write_text(source, encoding="utf-8")
    exe = work / (os.path.splitext(name)[0] + (".exe" if os.name == "nt" else ""))
    if exe.exists():
        exe.unlink()
    b = subprocess.run([str(stage1), "build", str(src)], capture_output=True, text=True,
                       timeout=120, cwd=work, env=env)
    assert exe.exists(), b.stdout[-1500:] + b.stderr[-1500:]
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30, cwd=work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASSED" in r.stdout or "Complete" in r.stdout, r.stdout + r.stderr


def test_selfhosted_build_honors_output_flag(selfhost):
    stage1, work, env = selfhost
    src = work / "o_flag.nv"
    src.write_text('print("o-flag")\n', encoding="utf-8")
    out = work / ("custom_out" + (".exe" if os.name == "nt" else ""))
    if out.exists():
        out.unlink()
    subprocess.run([str(stage1), "build", str(src), "-o", str(out)], capture_output=True, text=True,
                   timeout=300, cwd=work, env=env)
    assert out.exists()
    assert not (work / "custom_out..exe").exists()
    r = subprocess.run([str(out)], capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "o-flag"
