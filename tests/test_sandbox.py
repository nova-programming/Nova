import os
import subprocess
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANDBOX_EXE = os.path.join(REPO_ROOT, "examples", "nova_sandbox.exe")
NOVA_EXE = os.path.join(REPO_ROOT, "nova.exe")

@pytest.fixture(scope="module")
def sandbox_bin():
    if not os.path.isfile(SANDBOX_EXE):
        src = os.path.join(REPO_ROOT, "examples", "nova_sandbox.nv")
        env = dict(os.environ)
        gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
        if os.path.isdir(gcc_bin):
            env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")
        res = subprocess.run([NOVA_EXE, "build", src, "-o", SANDBOX_EXE], env=env, capture_output=True, text=True)
        assert res.returncode == 0, f"Failed to build nova_sandbox.exe: {res.stdout}\n{res.stderr}"
        strip_bin = os.path.join(gcc_bin, "strip.exe") if os.path.isdir(gcc_bin) else "strip"
        try:
            subprocess.run([strip_bin, "--strip-all", SANDBOX_EXE], check=False)
        except Exception:
            pass
    assert os.path.isfile(SANDBOX_EXE)
    return SANDBOX_EXE

def test_sandbox_binary_size_under_250kb(sandbox_bin):
    size_bytes = os.path.getsize(sandbox_bin)
    size_kb = size_bytes / 1024.0
    print(f"nova_sandbox.exe size: {size_kb:.2f} KB ({size_bytes} bytes)")
    assert size_kb < 250.0, f"Binary exceeds 250KB limit: {size_kb:.2f} KB"

def test_sandbox_headless_benchmark(sandbox_bin):
    res = subprocess.run([sandbox_bin, "--headless-bench", "300"], capture_output=True, text=True, timeout=10)
    assert res.returncode == 0, f"Benchmark failed with returncode {res.returncode}:\n{res.stderr}"
    assert "[Headless Benchmark] 300 frames completed in" in res.stdout
    
    # Extract milliseconds and FPS from output
    # Format: [Headless Benchmark] 300 frames completed in <X> ms (<Y> FPS)
    m = re.search(r"(\d+)\s*ms\s*\((\d+)\s*FPS\)", res.stdout)
    assert m is not None, f"Could not parse benchmark timings from output:\n{res.stdout}"
    
    elapsed_ms = int(m.group(1))
    fps = int(m.group(2))
    print(f"nova_sandbox benchmark: {elapsed_ms} ms, {fps} FPS")
    
    assert elapsed_ms < 500, f"Benchmark took too long: {elapsed_ms} ms (expected < 500 ms)"
    assert fps > 600, f"Benchmark FPS too low: {fps} (expected > 600 FPS)"

