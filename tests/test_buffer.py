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

def test_buffer_basic_ops(tmp_path):
    src = """import buffer

buf = new_buffer(1024)
buf.set_u8(0, 65)
buf.set_u8(1, 66)
buf.set_u8(2, 67)

b0 = buf.get_u8(0)
b1 = buf.get_u8(1)
b2 = buf.get_u8(2)

buf.set_i32(10, 12345678)
v = buf.get_i32(10)

print(b0)
print(b1)
print(b2)
print(v)
buf.release()
"""
    res = _run_build_and_exec(tmp_path, src, "test_buf_basic")
    assert res.returncode == 0
    lines = res.stdout.strip().split()
    assert lines == ["65", "66", "67", "12345678"]

def test_buffer_slicing_and_unaligned_words(tmp_path):
    src = """import buffer

buf = new_buffer(32)
# Unaligned 16-bit word at byte offset 3
buf.set_u16(3, 4660) # 0x1234
w = buf.get_u16(3)
print(w)

# Unaligned 32-bit word at byte offset 5
buf.set_i32_unaligned(5, 305419896) # 0x12345678
dw = buf.get_i32_unaligned(5)
print(dw)

# Safe slice of 10 bytes starting at byte offset 3
sub = buf.slice(3, 10)
print(sub.size)
w_sub = sub.get_u16(0)
print(w_sub)

sub.release()
buf.release()
"""
    res = _run_build_and_exec(tmp_path, src, "test_buf_slice")
    assert res.returncode == 0
    lines = res.stdout.strip().split()
    assert lines == ["4660", "305419896", "10", "4660"]

def test_buffer_out_of_bounds_panic(tmp_path):
    src = """import buffer

buf = new_buffer(16)
# Attempt to read past capacity (index 20 in 16-byte buffer)
v = buf.get_u8(20)
print(v)
"""
    res = _run_build_and_exec(tmp_path, src, "test_buf_oob")
    assert res.returncode != 0
    assert "[Nova Runtime Panic] Buffer boundary violation during buf_get_u8" in res.stderr

def test_buffer_10m_writes_benchmark(tmp_path):
    """Benchmark 10 million 32-bit pixel/sample writes to verify C-speed throughput."""
    src = """import buffer
import time

count = 10000000
size_bytes = count * 4
buf = new_buffer(size_bytes)

# Fast bulk fill
t0 = time_now_us()
buf.fill_i32(count, 16711850)
t1 = time_now_us()

diff_ms = (t1 - t0) / 1000
print("FILL_TIME_MS=" + str(diff_ms))

first = buf.get_i32(0)
last = buf.get_i32(count - 1)
print("FIRST=" + str(first))
print("LAST=" + str(last))
buf.release()
"""
    res = _run_build_and_exec(tmp_path, src, "test_buf_bench")
    assert res.returncode == 0
    assert "FIRST=16711850" in res.stdout
    assert "LAST=16711850" in res.stdout
    
    # Extract fill time
    for line in res.stdout.splitlines():
        if "FILL_TIME_MS=" in line:
            ms = float(line.split("=")[1])
            print(f"10M 32-bit fill completed in {ms:.2f} ms")
            assert ms < 25.0, f"Fill took {ms:.2f} ms, expected < 25.0 ms"
