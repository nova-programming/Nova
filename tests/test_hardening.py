"""Regression tests for the security/robustness hardening batch."""
import importlib.util
import io
import os
import re
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bootstrap"))


def _load_bootstrap_main():
    spec = importlib.util.spec_from_file_location("nova_bootstrap_main", os.path.join(ROOT, "bootstrap", "main.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buf.getvalue()


# ---- nova update extraction -------------------------------------------------

@pytest.fixture(scope="module")
def nova_main():
    return _load_bootstrap_main()


def test_update_extracts_allowed_files(nova_main, tmp_path):
    data = _zip([("Nova-main/stdlib/ok.nv", "x = 1"), ("Nova-main/nova.nv", "y"), ("Nova-main/README.md", "skipped")])
    assert nova_main.extract_update_archive(data, str(tmp_path)) == 2
    assert (tmp_path / "stdlib" / "ok.nv").read_text() == "x = 1"
    assert not (tmp_path / "README.md").exists()


@pytest.mark.parametrize("name", [
    "Nova-main/stdlib/../../evil.txt",
    "stdlib/../../evil.txt",
    "Nova-main/stdlib/a/../../../evil.txt",
    "Nova-main/stdlib/C:/evil.txt",
])
def test_update_rejects_path_traversal(nova_main, tmp_path, name):
    install = tmp_path / "install"
    install.mkdir()
    data = _zip([("Nova-main/stdlib/ok.nv", "x"), (name, "pwned")])
    with pytest.raises(ValueError):
        nova_main.extract_update_archive(data, str(install))
    assert not (tmp_path / "evil.txt").exists()
    # validation happens before any write
    assert not (install / "stdlib" / "ok.nv").exists()


def test_update_rejects_symlink(nova_main, tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("Nova-main/stdlib/link")
        info.external_attr = (0o120777 << 16)
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(ValueError):
        nova_main.extract_update_archive(buf.getvalue(), str(tmp_path))


def test_update_rejects_oversized_archive(nova_main, tmp_path, monkeypatch):
    monkeypatch.setattr(nova_main, "MAX_UPDATE_ARCHIVE_BYTES", 10)
    with pytest.raises(ValueError):
        nova_main.extract_update_archive(_zip([("Nova-main/nova.nv", "x" * 100)]), str(tmp_path))


# ---- galaxy hash policy -----------------------------------------------------

@pytest.fixture()
def galaxy():
    import _galaxy
    return _galaxy


def test_missing_hashes_fail_by_default(galaxy, tmp_path, monkeypatch):
    monkeypatch.delenv("GALAXY_ALLOW_UNVERIFIED", raising=False)
    assert galaxy._verify_hashes(str(tmp_path), {"version": "1.0.0"}, "pkg") is False


def test_missing_hashes_allowed_for_direct_github_ref(galaxy, tmp_path, monkeypatch):
    monkeypatch.delenv("GALAXY_ALLOW_UNVERIFIED", raising=False)
    assert galaxy._verify_hashes(str(tmp_path), None, "owner/repo", allow_unverified=True) is True


def test_missing_hashes_env_override(galaxy, tmp_path, monkeypatch):
    monkeypatch.setenv("GALAXY_ALLOW_UNVERIFIED", "1")
    assert galaxy._verify_hashes(str(tmp_path), None, "pkg") is True


def test_hash_mismatch_still_fails(galaxy, tmp_path):
    (tmp_path / "a.nv").write_text("hi")
    entry = {"files": [{"path": "a.nv", "sha256": "0" * 64}]}
    assert galaxy._verify_hashes(str(tmp_path), entry, "pkg") is False


def test_hash_match_passes(galaxy, tmp_path):
    f = tmp_path / "a.nv"
    f.write_text("hi")
    entry = {"files": [{"path": "a.nv", "sha256": galaxy.compute_sha256(str(f))}]}
    assert galaxy._verify_hashes(str(tmp_path), entry, "pkg") is True


# ---- runtime.c printf shim --------------------------------------------------

def test_runtime_printf_float_buffer_is_bounded():
    src = open(os.path.join(ROOT, "runtime.c"), encoding="utf-8").read()
    assert not re.search(r'sprintf\(buf,\s*"%\.6f"', src), "unbounded sprintf for %f"
    assert 'snprintf(buf, sizeof(buf), "%.6f"' in src


# ---- packaging --------------------------------------------------------------

def test_pyproject_uses_valid_build_backend():
    text = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
    assert 'build-backend = "setuptools.build_meta"' in text
    assert "setuptools.backends" not in text
