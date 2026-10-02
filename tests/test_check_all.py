"""Guards: every shipped .nv source type-checks, and the self-hosted driver honors -o."""
import glob
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "bootstrap", "main.py")

SOURCES = sorted(
    glob.glob(os.path.join(ROOT, "stdlib", "*.nv"))
    + glob.glob(os.path.join(ROOT, "stdlib", "backend", "*", "*.nv"))
    + glob.glob(os.path.join(ROOT, "examples", "*.nv"))
    + glob.glob(os.path.join(ROOT, "tests", "*.nv"))
    + [os.path.join(ROOT, "nova.nv")]
)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: os.path.relpath(p, ROOT))
def test_source_checks_clean(path):
    r = subprocess.run([sys.executable, MAIN_PY, "check", path], capture_output=True, text=True,
                       cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]


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
