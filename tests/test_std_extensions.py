import os
import subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_EXE = os.path.join(ROOT, "nova.exe" if os.name == "nt" else "nova")

def _run_build_and_exec(tmp_path, src_code: str, exe_name: str = "prog"):
    assert os.path.isfile(NOVA_EXE), f"nova.exe missing: {NOVA_EXE}"
    src_file = tmp_path / f"{exe_name}.nv"
    src_file.write_text(src_code, encoding="utf-8")
    out_exe = tmp_path / (f"{exe_name}.exe" if os.name == "nt" else exe_name)

    env = dict(os.environ)
    gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
    if os.path.isdir(gcc_bin):
        env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")

    build_res = subprocess.run(
        [NOVA_EXE, "build", str(src_file), "-o", str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert build_res.returncode == 0, f"Build failed:\nSTDOUT:\n{build_res.stdout}\nSTDERR:\n{build_res.stderr}"
    assert out_exe.exists(), "Output binary was not created"

    run_res = subprocess.run(
        [str(out_exe)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    return run_res

def test_text_and_path_extensions(tmp_path):
    src = """import text
import path

# Test string slicing view helper
s = "Hello Nova World"
sub1 = str_slice(s, 6, 4)
sub2 = str_slice(s, 0, 5)
sub_clamp = str_slice(s, 11, 100)

print(sub1)
print(sub2)
print(sub_clamp)

# Test cross-platform path normalization
p = path_to_forward("C:\\\\Users\\\\Nova\\\\stdlib\\\\compiler.nv")
print(p)
"""
    res = _run_build_and_exec(tmp_path, src, "test_text_path")
    assert res.returncode == 0
    lines = res.stdout.strip().splitlines()
    assert lines[0] == "Nova"
    assert lines[1] == "Hello"
    assert lines[2] == "World"
    assert lines[3] == "C:/Users/Nova/stdlib/compiler.nv"

def test_atomic_file_write(tmp_path):
    src = """import fs

target = "atomic_data.txt"
ok = fs_write_atomic(target, "NOVA_ATOMIC_VERIFIED_12345")
print(ok)

content = fs_read(target)
print(content)
"""
    res = _run_build_and_exec(tmp_path, src, "test_fs_atomic")
    assert res.returncode == 0
    lines = res.stdout.strip().splitlines()
    assert lines[0] == "1"
    assert lines[1] == "NOVA_ATOMIC_VERIFIED_12345"

def test_streaming_json_tokenizer(tmp_path):
    src = """import json

lb = "{"
rb = "}"
q = "\\""
raw_json = lb + q + "name" + q + ": " + q + "Nova" + q + ", " + q + "version" + q + ": 1, " + q + "ready" + q + ": true" + rb
c = json_cursor_new(raw_json)

# Token 1: {
t1 = json_next_token(c)
k1 = json_token_kind(t1)
print(k1)

# Token 2: "name"
t2 = json_next_token(c)
s2 = json_token_text(t2)
print(s2)

# Token 3: :
t3 = json_next_token(c)
k3 = json_token_kind(t3)
print(k3)

# Token 4: "Nova"
t4 = json_next_token(c)
s4 = json_token_text(t4)
print(s4)
"""
    res = _run_build_and_exec(tmp_path, src, "test_json_stream")
    assert res.returncode == 0
    lines = res.stdout.strip().splitlines()
    assert lines[0] == "1" # Object start '{'
    assert lines[1] == "name"
    assert lines[2] == "5" # Colon ':'
    assert lines[3] == "Nova"

def test_compiler_caret_diagnostic(tmp_path):
    # Syntax error with known column offset
    bad_code = "x = 10 + *\n"
    bad_file = tmp_path / "bad.nv"
    bad_file.write_text(bad_code, encoding="utf-8")

    res = subprocess.run(
        [NOVA_EXE, "check", str(bad_file)],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    # Must contain caret pointer (^~~~)
    assert "^~~~" in res.stdout or "^~~~" in res.stderr
