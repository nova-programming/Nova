"""Automated test verifying that `nova.exe` can compile and run programs from any directory outside the repo."""

import os
import subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_EXE = os.path.join(ROOT, "nova.exe" if os.name == "nt" else "nova")

PORTABLE_PROGRAM = """import text
import json

def run() {
    s = text_lower("HELLO NOVA FROM ANYWHERE")
    data = json_parse("{\\"msg\\":\\"" + s + "\\"}")
    res = json_as_string(json_get(data, "msg"))
    print("RESULT: " + res)
}
run()
"""

EXTERNAL_HELPER = """def get_custom_val() -> string {
    return "NOVA_PATH_RESOLVED"
}
"""

PROGRAM_WITH_NOVA_PATH = """import custom_helper

def run() {
    print("EXTRA: " + custom_helper.get_custom_val())
}
run()
"""

def test_compile_and_run_from_external_directory(tmp_path):
    """Run `nova.exe` from a completely external cwd without repo-relative stdlib."""
    assert os.path.isfile(NOVA_EXE), f"nova.exe missing: {NOVA_EXE}"

    src_file = tmp_path / "test_prog.nv"
    src_file.write_text(PORTABLE_PROGRAM, encoding="utf-8")
    out_exe = tmp_path / ("test_prog.exe" if os.name == "nt" else "test_prog")

    env = dict(os.environ)
    gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
    if os.path.isdir(gcc_bin):
        env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")

    # Execute build with cwd=tmp_path (outside the repo root)
    r = subprocess.run(
        [NOVA_EXE, "build", str(src_file), "-o", str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert r.returncode == 0, f"Compilation failed:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
    assert out_exe.is_file(), "Target executable was not produced"

    # Run the compiled executable
    r_run = subprocess.run([str(out_exe)], capture_output=True, text=True, timeout=30, cwd=str(tmp_path))
    assert r_run.returncode == 0, f"Execution failed:\n{r_run.stdout}\n{r_run.stderr}"
    assert "RESULT: hello nova from anywhere" in r_run.stdout


def test_nova_path_environment_resolution(tmp_path):
    """Verify that NOVA_PATH allows importing modules from custom external locations."""
    ext_dir = tmp_path / "custom_lib"
    ext_dir.mkdir()
    (ext_dir / "custom_helper.nv").write_text(EXTERNAL_HELPER, encoding="utf-8")

    src_file = tmp_path / "prog_env.nv"
    src_file.write_text(PROGRAM_WITH_NOVA_PATH, encoding="utf-8")
    out_exe = tmp_path / ("prog_env.exe" if os.name == "nt" else "prog_env")

    env = dict(os.environ)
    env["NOVA_PATH"] = str(ext_dir)
    gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
    if os.path.isdir(gcc_bin):
        env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")

    r = subprocess.run(
        [NOVA_EXE, "build", str(src_file), "-o", str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert r.returncode == 0, f"Compilation with NOVA_PATH failed:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
    assert out_exe.is_file(), "Target executable was not produced"

    r_run = subprocess.run([str(out_exe)], capture_output=True, text=True, timeout=30, cwd=str(tmp_path))
    assert r_run.returncode == 0, f"Execution failed:\n{r_run.stdout}\n{r_run.stderr}"
    assert "EXTRA: NOVA_PATH_RESOLVED" in r_run.stdout

