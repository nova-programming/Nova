"""Shared fixtures: a self-hosted (stage-1) Nova compiler built once per test session."""
import os
import platform
import shutil
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "bootstrap", "main.py")
EXE = ".exe" if os.name == "nt" else ""


def run_built(args, exe_path, **kwargs):
    """subprocess.run(args, **kwargs), retrying briefly if `exe_path` doesn't exist right after a
    build that reported success. On Windows, antivirus real-time scanning can hold a freshly
    linked .exe's file handle for tens of milliseconds right after GCC's linker closes it, which
    otherwise shows up as a flaky, unrelated-looking test failure (missing file, or a transient
    permission error launching it) under a full, long-running suite. Not needed on a real build
    failure: this only retries a build that *looks* like it already produced its binary."""
    result = subprocess.run(args, **kwargs)
    if not os.path.exists(exe_path):
        for _ in range(3):
            time.sleep(0.08)
            if os.path.exists(exe_path):
                break
    return result


def run_exe(args, **kwargs):
    """subprocess.run(args, **kwargs), retrying a couple of times on the transient
    FileNotFoundError / PermissionError that antivirus scanning a just-linked .exe can cause."""
    last = None
    for attempt in range(3):
        try:
            return subprocess.run(args, **kwargs)
        except (FileNotFoundError, PermissionError) as e:
            last = e
            time.sleep(0.08)
    raise last


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
    r = run_built(
        [sys.executable, MAIN_PY, "build", os.path.join(ROOT, "nova.nv"), "-o", str(stage1)],
        str(stage1), capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
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
        b = run_built([str(stage1), "build", str(src)], str(exe), capture_output=True, text=True,
                      timeout=300, cwd=work, env=env)
        assert exe.exists(), b.stdout[-2000:] + b.stderr[-2000:]
        r = run_exe([str(exe)], capture_output=True, text=True, timeout=60, cwd=work)
        asm_path = work / (name + ".nv.s")
        return r, asm_path.read_text() if asm_path.exists() else ""

    return run


@pytest.fixture(scope="session")
def bootstrap_native_run(tmp_path_factory):
    """Callable: compile + run a program with the Python-bootstrap native x86_64 backend
    directly (bootstrap/compiler/backend/x86_64/codegen.py), bypassing the self-hosted
    compiler entirely. The self-hosted compiler is itself built BY this backend, so a bug here
    affects every native Nova program compiled via `python bootstrap/main.py build`, not just
    ones built with a self-hosted stage1/stage2 -- distinct from `selfhost_run`, which only
    exercises the self-hosted compiler's own codegen (stdlib/backend/x86_64/codegen.nv)."""
    if platform.machine().lower() not in ("amd64", "x86_64"):
        pytest.skip("x86_64 host required")
    env = gcc_env()
    if env is None:
        pytest.skip("64-bit GCC not found")
    work = tmp_path_factory.mktemp("bootstrap_native")

    def run(source, name):
        src = work / (name + ".nv")
        src.write_text(source, encoding="utf-8")
        exe = work / (name + EXE)
        if exe.exists():
            exe.unlink()
        b = run_built([sys.executable, MAIN_PY, "build", str(src)], str(exe), capture_output=True,
                      text=True, timeout=300, cwd=work, env=env)
        assert exe.exists(), b.stdout[-2000:] + b.stderr[-2000:]
        return run_exe([str(exe)], capture_output=True, text=True, timeout=60, cwd=work)

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
    exe = work / ("stage2" + EXE)
    r = run_built([str(stage1), "build", str(work / "nova.nv"), "-o", str(exe)], str(exe),
                  capture_output=True, text=True, timeout=600, cwd=work, env=env)
    assert exe.exists(), r.stdout[-2000:] + r.stderr[-2000:]
    return exe, work, env
