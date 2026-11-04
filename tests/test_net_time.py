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

def test_high_res_time(tmp_path):
    src = """import time

t0_us = time_now_us()
t0_ms = time_now_ms()

# Sleep for 15ms
sleep_ms(15)

t1_us = time_now_us()
t1_ms = time_now_ms()

elapsed_us = t1_us - t0_us
elapsed_ms = t1_ms - t0_ms

print("ELAPSED_US=" + str(elapsed_us))
print("ELAPSED_MS=" + str(elapsed_ms))
"""
    res = _run_build_and_exec(tmp_path, src, "test_time")
    assert res.returncode == 0
    assert "ELAPSED_US=" in res.stdout
    assert "ELAPSED_MS=" in res.stdout

def test_tcp_loopback_delivery(tmp_path):
    src = """import net
import buffer

ok = net_init()
print("NET_INIT=" + str(ok))

listener = tcp_listen(19898, 5)
client = tcp_connect("127.0.0.1", 19898)
server_conn = listener.accept()

send_buf = new_buffer(64)
send_buf.set_u8(0, 78)
send_buf.set_u8(1, 79)
send_buf.set_u8(2, 86)
send_buf.set_u8(3, 65)
send_buf.set_u8(4, 33)
s = client.send(send_buf.handle, 5)

recv_buf = new_buffer(64)
bytes_recvd = server_conn.recv(recv_buf.handle, 64)
print("BYTES_RECVD=" + str(bytes_recvd))

c0 = recv_buf.get_u8(0)
c1 = recv_buf.get_u8(1)
c2 = recv_buf.get_u8(2)
c3 = recv_buf.get_u8(3)
c4 = recv_buf.get_u8(4)

print("DATA=" + str(c0) + " " + str(c1) + " " + str(c2) + " " + str(c3) + " " + str(c4))

client.close()
server_conn.close()
listener.close()
send_buf.release()
recv_buf.release()
"""
    res = _run_build_and_exec(tmp_path, src, "test_net")
    assert res.returncode == 0
    assert "NET_INIT=1" in res.stdout
    assert "BYTES_RECVD=5" in res.stdout
    assert "DATA=78 79 86 65 33" in res.stdout
