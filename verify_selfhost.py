"""Self-host gate: the compiler must reproduce itself byte for byte.

    python verify_selfhost.py              build stage1 (Python bootstrap) -> stage2 -> stage3, compare stage2/stage3
    python verify_selfhost.py --install    also copy stage3 over nova.exe when the check passes

Stage 2 and stage 3 are built from the same sources by different compilers (stage1, stage2); their generated assembly
(nova.nv.s) must be identical. A difference means a codegen change that is not stable yet. Run this after every change to
the compiler, the runtime, or the calling convention (see CLAUDE.md, "Two-Stage ABI Rule").
Work happens in a temporary folder, so the checkout is never left half built. Exit code 0 = identical.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE = ".exe" if os.name == "nt" else ""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def run(cmd, cwd, env, what):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(f"FAILED: {what}\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
        sys.exit(2)


def main():
    env = dict(os.environ)
    gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
    if os.path.isdir(gcc_bin):                       # the 64-bit toolchain (see CLAUDE.md), never C:\MinGW
        env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")
    work = tempfile.mkdtemp(prefix="nova_selfhost_")
    try:
        shutil.copytree(os.path.join(ROOT, "stdlib"), os.path.join(work, "stdlib"))
        for name in ("nova.nv", "runtime.c"):
            shutil.copy(os.path.join(ROOT, name), os.path.join(work, name))

        run([sys.executable, os.path.join(ROOT, "bootstrap", "main.py"), "build", "nova.nv", "-o", "stage1" + EXE],
            work, env, "stage 1 (Python bootstrap builds the compiler)")
        digests = {}
        prev = "stage1"
        for stage in ("stage2", "stage3"):
            for stale in (f for f in os.listdir(work) if f.startswith(".nova_cache")):
                os.remove(os.path.join(work, stale))                 # never reuse the previous stage's cache
            run([os.path.join(work, prev + EXE), "build", "nova.nv", "-o", stage + EXE], work, env,
                f"{stage} (built by {prev})")
            digests[stage] = sha256(os.path.join(work, "nova.nv.s"))
            prev = stage

        print(f"stage2 assembly sha256: {digests['stage2']}")
        print(f"stage3 assembly sha256: {digests['stage3']}")
        if digests["stage2"] != digests["stage3"]:
            print("SELF-HOST MISMATCH: stage2 and stage3 differ - the compiler does not reproduce itself.")
            return 1
        print("SELF-HOST OK: stage2 == stage3")
        if "--install" in sys.argv:
            target = os.path.join(ROOT, "nova" + EXE)
            shutil.copy(os.path.join(work, "stage3" + EXE), target)
            print(f"installed stage3 as {target}")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
