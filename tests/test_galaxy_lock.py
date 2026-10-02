"""galaxy.lock records a content hash of each installed package; tampering is detected."""
import io
import os
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture()
def galaxy(tmp_path, monkeypatch):
    import _galaxy
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_galaxy, "GALAXY_MODULES_DIR", "galaxy_modules")
    return _galaxy


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr("repo-main/" + name, text)
    return buf.getvalue()


def _install(galaxy, monkeypatch, files, version="1.0.0", force=False):
    """Run _install_package against a fake registry entry and download."""
    import hashlib
    data = {
        "package": "demo", "version": version, "github_repo": "o/demo",
        "download_url": "https://example.invalid/demo.zip",
        "versions": [{"version": version, "sha256": "x",
                      "files": [{"path": n, "sha256": hashlib.sha256(t.encode()).hexdigest()}
                                for n, t in files.items()]}],
    }
    monkeypatch.setattr(galaxy, "registry_fetch_pkg", lambda name: data)

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(galaxy.urllib.request, "urlopen", lambda req, timeout=30: Resp(_zip(files)))
    return galaxy._install_package("demo", force=force)


def test_tree_hash_is_stable_and_content_sensitive(galaxy, tmp_path):
    d = tmp_path / "pkg"
    (d / "sub").mkdir(parents=True)
    (d / "a.nv").write_text("x")
    (d / "sub" / "b.nv").write_text("y")
    first = galaxy.compute_tree_hash(str(d))
    assert galaxy.compute_tree_hash(str(d)) == first
    (d / "sub" / "b.nv").write_text("z")
    assert galaxy.compute_tree_hash(str(d)) != first


def test_install_records_tree_hash_and_verify_detects_tampering(galaxy, monkeypatch, capsys):
    files = {"galaxy.json": "{}", "src/main.nv": "print(1)\n"}
    assert _install(galaxy, monkeypatch, files)
    lock = galaxy.load_lock()
    assert lock["packages"]["demo"]["tree_sha256"]
    galaxy.cmd_verify([])
    assert "[OK]   demo" in capsys.readouterr().out
    with open(os.path.join("galaxy_modules", "demo", "src", "main.nv"), "w") as f:
        f.write("print(666)\n")
    with pytest.raises(SystemExit):
        galaxy.cmd_verify([])
    assert "[FAIL] demo" in capsys.readouterr().out


def test_reinstall_with_changed_contents_is_refused(galaxy, monkeypatch):
    import shutil
    files = {"galaxy.json": "{}", "src/main.nv": "print(1)\n"}
    assert _install(galaxy, monkeypatch, files)
    shutil.rmtree(os.path.join("galaxy_modules", "demo"))
    # same version, but the upstream archive changed after it was locked
    changed = {"galaxy.json": "{}", "src/main.nv": "print('evil')\n"}
    assert _install(galaxy, monkeypatch, changed) is None
    assert not os.path.exists(os.path.join("galaxy_modules", "demo"))


def test_force_accepts_new_contents(galaxy, monkeypatch):
    import shutil
    files = {"galaxy.json": "{}", "src/main.nv": "print(1)\n"}
    assert _install(galaxy, monkeypatch, files)
    shutil.rmtree(os.path.join("galaxy_modules", "demo"))
    changed = {"galaxy.json": "{}", "src/main.nv": "print(2)\n"}
    assert _install(galaxy, monkeypatch, changed, force=True)
