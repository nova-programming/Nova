"""Shared fixtures: a self-hosted (stage-1) Nova compiler built once per test session."""
import os
import platform
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "bootstrap", "main.py")
EXE = ".exe" if os.name == "nt" else ""


@pytest.fixture(autouse=True)
def _restore_environ():
    """Some tests (installer logic) mutate os.environ["PATH"]; that used to hide GCC from later
    native tests, silently skipping them in full runs. Restore the environment after every test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def gcc_env():
    """Return an env whose first gcc is 64-bit, or None if there isn't one."""
    env = dict(os.environ)
    dirs = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(os.path.join(local, "nova", "gcc", "bin"))
    dirs.append(os.path.join(os.path.expanduser("~"), ".nova", "gcc", "bin"))
    dirs.append(os.path.join(ROOT, "gcc", "bin"))
    for d in dirs:
        if os.path.isdir(d):
            env["PATH"] = d + os.pathsep + env.get("PATH", "")
            break
    gcc = shutil.which("gcc", path=env["PATH"])
    if not gcc:
        return None
    out = subprocess.run([gcc, "-dumpmachine"], capture_output=True, text=True).stdout
    if "x86_64" not in out and "amd64" not in out.lower():
        return None
    return env


@pytest.fixture(scope="session")
def selfhost(tmp_path_factory):
    """(stage1 exe, work dir, env): the self-hosted compiler built from the current sources."""
    if platform.machine().lower() not in ("amd64", "x86_64"):
        pytest.skip("x86_64 host required")
    env = gcc_env()
    if env is None:
        pytest.skip("64-bit GCC not found")
    work = tmp_path_factory.mktemp("selfhost")
    shutil.copytree(os.path.join(ROOT, "stdlib"), work / "stdlib")
    for name in ("nova.nv", "runtime.c"):
        shutil.copy(os.path.join(ROOT, name), work / name)
    stage1 = work / ("stage1" + EXE)
    r = subprocess.run(
        [sys.executable, MAIN_PY, "build", os.path.join(ROOT, "nova.nv"), "-o", str(stage1)],
        capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
    )
    assert r.returncode == 0 and stage1.exists(), r.stdout[-2000:] + r.stderr[-2000:]
    return stage1, work, env


@pytest.fixture(scope="session")
def selfhost_run(selfhost):
    """Callable: compile + run a program with the self-hosted compiler -> (CompletedProcess, asm text)."""
    stage1, work, env = selfhost

    def run(source, name):
        src = work / (name + ".nv")
        src.write_text(source, encoding="utf-8")
        exe = work / (name + EXE)
        if exe.exists():
            exe.unlink()
        b = subprocess.run([str(stage1), "build", str(src)], capture_output=True, text=True,
                           timeout=300, cwd=work, env=env)
        assert exe.exists(), b.stdout[-2000:] + b.stderr[-2000:]
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60, cwd=work)
        asm_path = work / (name + ".nv.s")
        return r, asm_path.read_text() if asm_path.exists() else ""

    return run


@pytest.fixture(scope="session")
def stage2(selfhost, tmp_path_factory):
    """(stage2 exe, work dir, env): the compiler as built by the self-hosted compiler itself.

    Stage 1 is compiled by the Python bootstrap, stage 2 by stage 1. Bugs in how the self-hosted
    code generator compiles the compiler's own sources only show up here (e.g. parser desugars that
    misparse the compiler's source), so shipped behavior is tested against stage 2 as well.
    """
    stage1, work1, env = selfhost
    work = tmp_path_factory.mktemp("stage2")
    shutil.copytree(work1 / "stdlib", work / "stdlib")
    for name in ("nova.nv", "runtime.c"):
        shutil.copy(work1 / name, work / name)
    r = subprocess.run([str(stage1), "build", str(work / "nova.nv"), "-o", str(work / ("stage2" + EXE))],
                       capture_output=True, text=True, timeout=600, cwd=work, env=env)
    exe = work / ("stage2" + EXE)
    assert exe.exists(), r.stdout[-2000:] + r.stderr[-2000:]
    return exe, work, env
