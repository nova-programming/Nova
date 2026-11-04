import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_DIR = ROOT
STAGE_DIR = os.path.join(os.environ["TEMP"], "nova_phase1_selfhost")

print(f"Root: {ROOT}")
print(f"Staging to: {STAGE_DIR}")

if os.path.exists(STAGE_DIR):
    shutil.rmtree(STAGE_DIR)
os.makedirs(STAGE_DIR, exist_ok=True)

# Copy necessary files to STAGE_DIR
shutil.copytree(os.path.join(NOVA_DIR, "stdlib"), os.path.join(STAGE_DIR, "stdlib"))
shutil.copy2(os.path.join(NOVA_DIR, "nova.nv"), os.path.join(STAGE_DIR, "nova.nv"))
shutil.copy2(os.path.join(NOVA_DIR, "runtime.c"), os.path.join(STAGE_DIR, "runtime.c"))

env = dict(os.environ)
gcc_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova", "gcc", "bin")
if os.path.isdir(gcc_bin):
    env["PATH"] = gcc_bin + os.pathsep + env.get("PATH", "")

def run_cmd(cmd, cwd=STAGE_DIR):
    print(f">> Running: {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
        sys.exit(r.returncode)
    return r

# 1. Python bootstrap -> s1.exe
main_py = os.path.join(NOVA_DIR, "bootstrap", "main.py")
s1_exe = os.path.join(STAGE_DIR, "s1.exe")
run_cmd([sys.executable, main_py, "build", "nova.nv", "-o", s1_exe])
assert os.path.isfile(s1_exe), "s1.exe not created"
print(f"s1.exe size: {os.path.getsize(s1_exe)}")

# 2. s1.exe -> s2.exe
s2_exe = os.path.join(STAGE_DIR, "s2.exe")
run_cmd([s1_exe, "build", "nova.nv", "-o", s2_exe])
assert os.path.isfile(s2_exe), "s2.exe not created"
s2_s = os.path.join(STAGE_DIR, "s2.s")
shutil.copy2(os.path.join(STAGE_DIR, "nova.nv.s"), s2_s)
print(f"s2.exe size: {os.path.getsize(s2_exe)}, s2.s size: {os.path.getsize(s2_s)}")

# Remove cache if any
cache_txt = os.path.join(STAGE_DIR, ".nova_cache.txt")
if os.path.isfile(cache_txt):
    os.remove(cache_txt)

# 3. s2.exe -> s3.exe
s3_exe = os.path.join(STAGE_DIR, "s3.exe")
run_cmd([s2_exe, "build", "nova.nv", "-o", s3_exe])
assert os.path.isfile(s3_exe), "s3.exe not created"
s3_s = os.path.join(STAGE_DIR, "s3.s")
shutil.copy2(os.path.join(STAGE_DIR, "nova.nv.s"), s3_s)
print(f"s3.exe size: {os.path.getsize(s3_exe)}, s3.s size: {os.path.getsize(s3_s)}")

h_s2_s = hashlib.sha256(open(s2_s, "rb").read()).hexdigest()
h_s3_s = hashlib.sha256(open(s3_s, "rb").read()).hexdigest()
print(f"s2.s SHA256: {h_s2_s}")
print(f"s3.s SHA256: {h_s3_s}")

assert h_s2_s == h_s3_s, f"Stage 2 and Stage 3 assembly mismatch!\ns2.s: {h_s2_s}\ns3.s: {h_s3_s}"
print("SUCCESS: Stage 2 == Stage 3 assembly byte-for-byte identical!")

# Update nova/nova.exe with s2.exe
dest_nova_exe = os.path.join(NOVA_DIR, "nova.exe")
shutil.copy2(s2_exe, dest_nova_exe)
print(f"Updated {dest_nova_exe}")

# Rebuild novalsp.exe with verified nova.exe
lsp_nv = os.path.join(NOVA_DIR, "lsp", "server.nv")
lsp_exe = os.path.join(NOVA_DIR, "novalsp.exe")
run_cmd([dest_nova_exe, "build", lsp_nv, "-o", lsp_exe], cwd=NOVA_DIR)
assert os.path.isfile(lsp_exe), "novalsp.exe not built"
print(f"Updated {lsp_exe}")
