import os
import subprocess
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDIO_EXE = os.path.join(REPO_ROOT, "examples", "nova_studio.exe")
NOVA_EXE = os.path.join(REPO_ROOT, "nova.exe")

@pytest.fixture(scope="module")
def studio_bin():
    src = os.path.join(REPO_ROOT, "examples", "nova_studio.nv")
    env = dict(os.environ)
    gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
    if os.path.isdir(gcc_bin):
        env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")
    
    # Rebuild to ensure fresh compilation
    res = subprocess.run([NOVA_EXE, "build", src, "-o", STUDIO_EXE], env=env, capture_output=True, text=True, timeout=90)
    assert res.returncode == 0, f"Failed to build nova_studio.exe: {res.stdout}\n{res.stderr}"
    
    strip_bin = os.path.join(gcc_bin, "strip.exe") if os.path.isdir(gcc_bin) else "strip"
    try:
        subprocess.run([strip_bin, "--strip-all", STUDIO_EXE], check=False)
    except Exception:
        pass
    assert os.path.isfile(STUDIO_EXE)
    return STUDIO_EXE

def test_studio_binary_size_under_250kb(studio_bin):
    size_bytes = os.path.getsize(studio_bin)
    size_kb = size_bytes / 1024.0
    print(f"nova_studio.exe size: {size_kb:.2f} KB ({size_bytes} bytes)")
    assert size_kb < 250.0, f"Binary exceeds 250KB limit: {size_kb:.2f} KB"

def test_studio_headless_benchmark(studio_bin):
    res = subprocess.run([studio_bin, "--headless-bench", "200"], capture_output=True, text=True, timeout=15)
    assert res.returncode == 0, f"Benchmark failed with returncode {res.returncode}:\n{res.stderr}"
    assert "NOVA STUDIO HEADLESS BENCHMARK" in res.stdout
    assert "Diagnostic Check: PASS (0 errors, Clean)" in res.stdout
    assert "STATUS: BENCHMARK COMPLETED SUCCESSFULLY" in res.stdout
    
    m = re.search(r"Throughput \(FPS\):\s*(\d+)", res.stdout)
    assert m is not None, f"Could not parse FPS from output:\n{res.stdout}"
    fps = int(m.group(1))
    print(f"nova_studio throughput: {fps} FPS")
    assert fps > 60, f"Benchmark FPS too low: {fps} (expected > 60 FPS)"

