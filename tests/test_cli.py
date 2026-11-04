import os
import subprocess
import sys
import tempfile
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_EXE = os.path.join(REPO_ROOT, "nova.exe")

@pytest.fixture(scope="module")
def nova_bin():
    assert os.path.isfile(NOVA_EXE), f"nova.exe not found at {NOVA_EXE}"
    return NOVA_EXE

def test_version_flags(nova_bin):
    for arg in ["--version", "version", "-v"]:
        res = subprocess.run([nova_bin, arg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert res.returncode == 0
        assert "Nova v0.8.0" in res.stdout

def test_help_flags(nova_bin):
    for arg in ["--help", "help", "-h"]:
        res = subprocess.run([nova_bin, arg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert res.returncode == 0
        assert "Usage: nova <command>" in res.stdout
        assert "build <file.nv>" in res.stdout
        assert "check <file.nv>" in res.stdout

def test_no_args_shows_help(nova_bin):
    res = subprocess.run([nova_bin], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0
    assert "Usage: nova <command>" in res.stdout

def test_unknown_command(nova_bin):
    res = subprocess.run([nova_bin, "nonexistent-cmd"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode != 0
    assert "Unknown command: nonexistent-cmd" in res.stdout

def test_check_valid_and_invalid(nova_bin, tmp_path):
    valid_file = tmp_path / "valid.nv"
    valid_file.write_text('x = 42\nprint(str(x))\n', encoding="utf-8")
    
    res_valid = subprocess.run([nova_bin, "check", str(valid_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_valid.returncode == 0
    assert "Checked " in res_valid.stdout

    invalid_file = tmp_path / "invalid.nv"
    invalid_file.write_text('if { print("bad syntax")\n', encoding="utf-8")
    
    res_invalid = subprocess.run([nova_bin, "check", str(invalid_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_invalid.returncode != 0

def test_build_custom_output_and_bench(nova_bin, tmp_path):
    src_file = tmp_path / "hello.nv"
    src_file.write_text('print("CLI test ok")\n', encoding="utf-8")
    out_exe = tmp_path / "custom_app.exe"
    
    res_build = subprocess.run(
        [nova_bin, "build", "-b", "-o", str(out_exe), str(src_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert res_build.returncode == 0
    assert "[Benchmark]" in res_build.stdout
    assert out_exe.is_file()

    res_run = subprocess.run([str(out_exe)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_run.returncode == 0
    assert "CLI test ok" in res_run.stdout

