"""End-to-end tests for the language server (`lsp/server.nv`).

These build the actual `novalsp` binary with the self-hosted compiler and talk to it the way
an editor would: once through the `--check` CLI, once over JSON-RPC on stdin/stdout.

The regression they pin down: the type checker used to emit its warnings with an empty
filename (`errors.warn("Type", "", ...)`), because `TypeChecker` had no filename field.
`novalsp --check` therefore printed `:2:12: warning [Type] ...` with no file to blame, and
the server treats a filename-less diagnostic as belonging to *every* open document -- so a
type warning in one file was re-published for unrelated, clean files. Threading the
filename through `TypeChecker` fixes both; these tests fail if it regresses.
"""

import json
import os
import platform
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = ".exe" if os.name == "nt" else ""

TYPE_ERROR_SOURCE = 'def run() {\n    x = "s" + 1\n    print(x)\n}\nrun()\n'
CLEAN_SOURCE = "def run() {\n    print(\"ok\")\n}\nrun()\n"


@pytest.fixture(scope="module")
def novalsp(selfhost):
    """Build lsp/server.nv with the stage-1 self-hosted compiler -> (exe, env)."""
    stage1, work, env = selfhost
    exe = work / ("novalsp" + EXE)
    if not exe.exists():
        r = subprocess.run(
            [str(stage1), "build", str(os.path.join(ROOT, "lsp", "server.nv")), "-o", str(exe)],
            capture_output=True, text=True, timeout=600, cwd=work, env=env,
        )
        assert r.returncode == 0 and exe.exists(), r.stdout[-2000:] + r.stderr[-2000:]
    return exe, env


def test_check_type_warning_names_the_file(novalsp, tmp_path):
    """`novalsp --check` must attribute a type warning to the file it came from."""
    exe, env = novalsp
    src = tmp_path / "typeerr.nv"
    src.write_text(TYPE_ERROR_SOURCE, encoding="utf-8")

    r = subprocess.run(
        [str(exe), "--check", str(src)],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "warning [Type]" in r.stdout
    # Before the fix this line started with ":", the empty filename slot.
    assert str(src) + ":" in r.stdout
    assert not r.stdout.lstrip().startswith(":")


def _frame(message):
    body = json.dumps(message).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body


def _parse_frames(data):
    messages = []
    pos = 0
    while pos < len(data):
        header_end = data.find(b"\r\n\r\n", pos)
        if header_end < 0:
            break
        length = None
        for line in data[pos:header_end].decode("ascii", "replace").split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
        if length is None:
            break
        start = header_end + 4
        messages.append(json.loads(data[start:start + length].decode("utf-8")))
        pos = start + length
    return messages


def test_open_document_diagnostics_do_not_leak_to_other_files(novalsp, tmp_path):
    """A type warning in one open document must not be published for another one."""
    exe, env = novalsp
    bad_uri = (tmp_path / "bad.nv").as_uri()
    clean_uri = (tmp_path / "clean.nv").as_uri()

    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": bad_uri, "languageId": "nova", "version": 1,
                             "text": TYPE_ERROR_SOURCE}}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": clean_uri, "languageId": "nova", "version": 1,
                             "text": CLEAN_SOURCE}}},
        {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None},
        {"jsonrpc": "2.0", "method": "exit", "params": None},
    ]
    payload = b"".join(_frame(m) for m in messages)
    r = subprocess.run(
        [str(exe), "--stdio", "--diag-file", str(tmp_path / "diag.jsonl")],
        input=payload, capture_output=True, timeout=120, env=env,
    )
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-2000:]

    replies = _parse_frames(r.stdout)
    published = [m for m in replies
                 if m.get("method") == "textDocument/publishDiagnostics"]

    by_uri = {}
    for m in published:
        by_uri.setdefault(m["params"]["uri"], []).append(m["params"]["diagnostics"])

    assert bad_uri in by_uri and clean_uri in by_uri
    bad_diags = by_uri[bad_uri][0]
    clean_diags = by_uri[clean_uri][0]
    assert any("expected string but got int" in d["message"] for d in bad_diags)
    # The bug: the filename-less type warning matched every document, so the clean file
    # received the other file's warning as well.
    assert clean_diags == []
