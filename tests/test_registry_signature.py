"""Ed25519-signed registry metadata: RFC 8032 vectors, tamper detection and the rollout policy."""
import base64
import json
import os
import sys
import urllib.error

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import _galaxy as galaxy  # noqa: E402

SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PUBLIC = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
SIG_EMPTY = bytes.fromhex(
    "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")


def test_rfc8032_vector_1():
    assert galaxy.ed25519_public_key(SEED) == PUBLIC
    assert galaxy.ed25519_sign(SEED, b"") == SIG_EMPTY
    assert galaxy.ed25519_verify(PUBLIC, b"", SIG_EMPTY)


def test_verify_rejects_tampering_and_bad_inputs():
    assert not galaxy.ed25519_verify(PUBLIC, b"x", SIG_EMPTY)
    bad_sig = bytearray(SIG_EMPTY)
    bad_sig[10] ^= 1
    assert not galaxy.ed25519_verify(PUBLIC, b"", bytes(bad_sig))
    assert not galaxy.ed25519_verify(PUBLIC, b"", SIG_EMPTY[:63])
    assert not galaxy.ed25519_verify(PUBLIC[:31], b"", SIG_EMPTY)
    # s >= group order must be rejected (signature malleability)
    malleable = SIG_EMPTY[:32] + (int.from_bytes(SIG_EMPTY[32:], "little") + galaxy._ED_Q).to_bytes(32, "little")
    assert not galaxy.ed25519_verify(PUBLIC, b"", malleable)


def test_cross_check_with_cryptography_library():
    ed = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    from cryptography.hazmat.primitives import serialization
    for i in range(3):
        seed = os.urandom(32)
        key = ed.Ed25519PrivateKey.from_private_bytes(seed)
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        message = os.urandom(50 + i)
        assert galaxy.ed25519_public_key(seed) == public
        assert galaxy.ed25519_verify(public, message, key.sign(message))   # library signs, we verify
        assert galaxy.ed25519_sign(seed, message) == key.sign(message)     # deterministic: identical


# ---- registry policy -----------------------------------------------------------------

DOC = json.dumps({"package": "demo", "version": "1.0.0"}).encode()


def _serve(monkeypatch, files):
    """Fake the registry: files maps URL suffix -> bytes (missing -> HTTP 404)."""
    def fetch(url):
        for suffix, data in files.items():
            if url.endswith(suffix):
                return data
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)
    monkeypatch.setattr(galaxy, "_fetch_bytes", fetch)


def _sig(raw):
    return base64.b64encode(galaxy.ed25519_sign(SEED, raw))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("GALAXY_REGISTRY_KEYS", "GALAXY_ALLOW_UNSIGNED", "GALAXY_REQUIRE_SIGNATURE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(galaxy, "REGISTRY_PUBLIC_KEYS", [])


def test_dormant_without_keys(monkeypatch):
    _serve(monkeypatch, {"packages/demo.json": DOC})
    assert galaxy.registry_fetch("packages/demo.json")["package"] == "demo"


def test_valid_signature_accepted(monkeypatch):
    monkeypatch.setenv("GALAXY_REGISTRY_KEYS", PUBLIC.hex())
    _serve(monkeypatch, {"packages/demo.json.sig": _sig(DOC), "packages/demo.json": DOC})
    assert galaxy.registry_fetch("packages/demo.json")["version"] == "1.0.0"


def test_tampered_metadata_rejected(monkeypatch, capsys):
    monkeypatch.setenv("GALAXY_REGISTRY_KEYS", PUBLIC.hex())
    tampered = DOC.replace(b"1.0.0", b"9.9.9")
    _serve(monkeypatch, {"packages/demo.json.sig": _sig(DOC), "packages/demo.json": tampered})
    with pytest.raises(SystemExit):
        galaxy.registry_fetch("packages/demo.json")
    assert "invalid signature" in capsys.readouterr().out


def test_missing_signature_rejected_when_keys_configured(monkeypatch):
    monkeypatch.setattr(galaxy, "REGISTRY_PUBLIC_KEYS", [PUBLIC.hex()])
    _serve(monkeypatch, {"packages/demo.json": DOC})
    with pytest.raises(SystemExit):
        galaxy.registry_fetch("packages/demo.json")


def test_signature_from_unknown_key_rejected(monkeypatch):
    other_public = galaxy.ed25519_public_key(bytes(range(32)))
    monkeypatch.setenv("GALAXY_REGISTRY_KEYS", other_public.hex())
    _serve(monkeypatch, {"packages/demo.json.sig": _sig(DOC), "packages/demo.json": DOC})
    with pytest.raises(SystemExit):
        galaxy.registry_fetch("packages/demo.json")


def test_allow_unsigned_override_and_non_package_paths(monkeypatch):
    monkeypatch.setenv("GALAXY_REGISTRY_KEYS", PUBLIC.hex())
    _serve(monkeypatch, {"packages/demo.json": DOC, "versions/nova.json": DOC})
    assert galaxy.registry_fetch("versions/nova.json")           # only packages/* are signed
    monkeypatch.setenv("GALAXY_ALLOW_UNSIGNED", "1")
    assert galaxy.registry_fetch("packages/demo.json")


def test_require_signature_flag_enforces_without_keys(monkeypatch):
    monkeypatch.setenv("GALAXY_REQUIRE_SIGNATURE", "1")
    _serve(monkeypatch, {"packages/demo.json": DOC})
    with pytest.raises(SystemExit):
        galaxy.registry_fetch("packages/demo.json")


def test_keygen_prints_a_working_keypair(capsys):
    galaxy.cmd_keygen([])
    out = capsys.readouterr().out
    public_hex = out.split("REGISTRY_PUBLIC_KEYS in _galaxy.py): ")[1].split()[0]
    seed_hex = out.split("never commit): ")[1].split()[0]
    sig = galaxy.ed25519_sign(bytes.fromhex(seed_hex), b"hello")
    assert galaxy.ed25519_verify(bytes.fromhex(public_hex), b"hello", sig)
