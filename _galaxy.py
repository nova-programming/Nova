"""
Galaxy Package Manager for Nova
Standalone CLI: galaxy <command> [args]
Also: python -m galaxy, python -m tools.galaxy, nova galaxy <cmd>
"""

import sys
import os
import json
import base64
import hashlib
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import zipfile
import io
import webbrowser
import shutil
import re
from pathlib import Path

GALAXY_VERSION = "0.8.0"
REGISTRY_URL = "https://galaxy-registry.vercel.app"
REGISTRY_REPO = "nova-programming/galaxy-registry"
GALAXY_MODULES_DIR = "galaxy_modules"
MANIFEST_FILE = "galaxy.json"
LOCK_FILE = "galaxy.lock"
NOVA_ZIP_URL = "https://github.com/nova-programming/Nova/archive/refs/heads/main.zip"
ZIP_PREFIX = "Nova-main"
GALAXY_RELEASE_BASE = "https://github.com/nova-programming/Nova/releases/download"
USER_AGENT = f"Nova-Galaxy/{GALAXY_VERSION}"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
PACKAGE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(/[A-Za-z0-9][A-Za-z0-9_.-]*)?$")


# ---------------------------------------------------------------------------
# Signed registry metadata (Ed25519, RFC 8032)
#
# The registry publishes <file>.sig next to packages/index.json and every packages/<name>.json:
# the base64 Ed25519 signature of the exact file bytes. Galaxy verifies it before trusting the
# metadata, so a compromised web host cannot swap package hashes or download URLs.
# Only verification (plus signing for `galaxy keygen`/tests) is implemented here, in pure Python.
# ---------------------------------------------------------------------------

# Hex-encoded 32-byte Ed25519 public keys allowed to sign registry metadata (any listed key may
# sign, which allows rotation). While this list is empty (and GALAXY_REQUIRE_SIGNATURE is unset)
# verification is dormant. Generate a keypair with `galaxy keygen`.
REGISTRY_PUBLIC_KEYS = []

_ED_P = 2 ** 255 - 19
_ED_Q = 2 ** 252 + 27742317777372353535851937790883648493
_ED_D = -121665 * pow(121666, _ED_P - 2, _ED_P) % _ED_P
_ED_I = pow(2, (_ED_P - 1) // 4, _ED_P)


def _ed_recover_x(y, sign):
    if y >= _ED_P:
        return None
    x2 = (y * y - 1) * pow(_ED_D * y * y + 1, _ED_P - 2, _ED_P) % _ED_P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_ED_P + 3) // 8, _ED_P)
    if (x * x - x2) % _ED_P != 0:
        x = x * _ED_I % _ED_P
    if (x * x - x2) % _ED_P != 0:
        return None
    if (x & 1) != sign:
        x = _ED_P - x
    return x


_ED_GY = 4 * pow(5, _ED_P - 2, _ED_P) % _ED_P
_ED_GX = _ed_recover_x(_ED_GY, 0)
_ED_G = (_ED_GX, _ED_GY, 1, _ED_GX * _ED_GY % _ED_P)
_ED_ZERO = (0, 1, 1, 0)


def _ed_add(a, b):
    p = _ED_P
    t1 = (a[1] - a[0]) * (b[1] - b[0]) % p
    t2 = (a[1] + a[0]) * (b[1] + b[0]) % p
    t3 = 2 * a[3] * b[3] * _ED_D % p
    t4 = 2 * a[2] * b[2] % p
    e, f, g, h = t2 - t1, t4 - t3, t4 + t3, t2 + t1
    return (e * f % p, g * h % p, f * g % p, e * h % p)


def _ed_mul(scalar, point):
    result = _ED_ZERO
    while scalar > 0:
        if scalar & 1:
            result = _ed_add(result, point)
        point = _ed_add(point, point)
        scalar >>= 1
    return result


def _ed_equal(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % _ED_P == 0 and (a[1] * b[2] - b[1] * a[2]) % _ED_P == 0


def _ed_compress(point):
    zinv = pow(point[2], _ED_P - 2, _ED_P)
    x = point[0] * zinv % _ED_P
    y = point[1] * zinv % _ED_P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _ed_decompress(data):
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _ed_recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _ED_P)


def _ed_secret_expand(seed):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public_key(seed):
    """32-byte public key for a 32-byte seed."""
    a, _ = _ed_secret_expand(seed)
    return _ed_compress(_ed_mul(a, _ED_G))


def ed25519_sign(seed, message):
    """64-byte signature of message (used by `galaxy keygen` self-test and the tests)."""
    a, prefix = _ed_secret_expand(seed)
    public = _ed_compress(_ed_mul(a, _ED_G))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _ED_Q
    big_r = _ed_compress(_ed_mul(r, _ED_G))
    h = int.from_bytes(hashlib.sha512(big_r + public + message).digest(), "little") % _ED_Q
    return big_r + int.to_bytes((r + h * a) % _ED_Q, 32, "little")


def ed25519_verify(public, message, signature):
    """True if signature is a valid Ed25519 signature of message under the 32-byte public key."""
    if len(public) != 32 or len(signature) != 64:
        return False
    a_point = _ed_decompress(public)
    r_point = _ed_decompress(signature[:32])
    if a_point is None or r_point is None:
        return False
    s_int = int.from_bytes(signature[32:], "little")
    if s_int >= _ED_Q:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), "little") % _ED_Q
    return _ed_equal(_ed_mul(s_int, _ED_G), _ed_add(r_point, _ed_mul(h, a_point)))


def _registry_keys():
    keys = list(REGISTRY_PUBLIC_KEYS)
    extra = os.environ.get("GALAXY_REGISTRY_KEYS", "")
    keys += [k.strip() for k in extra.split(",") if k.strip()]
    return keys


def verify_registry_signature(path, raw, sig_text):
    """Check the base64 signature text for registry file bytes against the configured keys."""
    try:
        signature = base64.b64decode(sig_text.strip(), validate=True)
    except Exception:
        return False
    for key_hex in _registry_keys():
        try:
            public = bytes.fromhex(key_hex)
        except ValueError:
            continue
        if ed25519_verify(public, raw, signature):
            return True
    return False


def cmd_keygen(args):
    """Create a registry signing keypair. Keep the seed secret; publish the public key."""
    seed = os.urandom(32)
    public = ed25519_public_key(seed)
    print("Galaxy registry signing key (Ed25519)")
    print(f"  public key (add to REGISTRY_PUBLIC_KEYS in _galaxy.py): {public.hex()}")
    print(f"  private seed (store as the GALAXY_SIGNING_KEY secret, never commit): {seed.hex()}")


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in ("-v", "--version", "version"):
        print(f"Galaxy v{GALAXY_VERSION}")
        return

    commands = {
        "init":      cmd_init,
        "install":   cmd_install,
        "list":      cmd_list,
        "verify":    cmd_verify,
        "keygen":    cmd_keygen,
        "test":      cmd_test,
        "search":    cmd_search,
        "info":      cmd_info,
        "publish":   cmd_publish,
        "update":    cmd_update,
        "upgrade":   cmd_upgrade,
        "remove":    cmd_remove,
        "uninstall": cmd_remove,
    }

    if cmd in commands:
        commands[cmd](args)
    elif cmd in ("-h", "--help", "help"):
        print_usage()
    else:
        print(f"Unknown command: {cmd}")
        print_usage()


def cmd_verify(args):
    """Check installed packages against the content hashes recorded in galaxy.lock."""
    lock = load_lock()
    failures = 0
    checked = 0
    for name, entry in sorted(lock["packages"].items()):
        expected = entry.get("tree_sha256") if isinstance(entry, dict) else None
        path = os.path.join(GALAXY_MODULES_DIR, name.replace("/", "_"))
        if not expected:
            print(f"  [SKIP] {name}: no content hash recorded (reinstall to record one)")
            continue
        if not os.path.isdir(path):
            print(f"  [MISSING] {name}: not installed in {GALAXY_MODULES_DIR}/")
            failures += 1
            continue
        checked += 1
        if compute_tree_hash(path) == expected:
            print(f"  [OK]   {name}")
        else:
            print(f"  [FAIL] {name}: contents differ from {LOCK_FILE}")
            failures += 1
    print(f"Verified {checked} package(s); {failures} problem(s).")
    if failures:
        sys.exit(1)


def print_usage():
    print("Galaxy Package Manager for Nova")
    print(f"Version: {GALAXY_VERSION}")
    print()
    print("Usage:")
    print("  galaxy --version              Show version")
    print("  galaxy init library <name>   Create a library package")
    print("  galaxy install <pkg>         Install a package")
    print("  galaxy list                  List installed packages")
    print("  galaxy verify                Check installed packages against galaxy.lock")
    print("  galaxy keygen                Create a registry signing keypair (maintainers)")
    print("  galaxy search <query>        Search the registry")
    print("  galaxy info <pkg>            Show package details")
    print("  galaxy test [--vm] [name]    Run library tests (--vm for faster VM mode)")
    print("  galaxy publish               Publish current package to registry")
    print("  galaxy update                Update Galaxy CLI itself")
    print("  galaxy upgrade [pkg]         Update installed packages")
    print("  galaxy remove <pkg>          Remove an installed package")
    print("  galaxy uninstall <pkg>       Alias for remove")
    print()
    print("Examples:")
    print("  galaxy init library my-lib")
    print("  galaxy init my-lib")
    print("  galaxy install nova-math")
    print("  galaxy install owner/repo")
    print("  galaxy search http")
    print("  galaxy publish")
    print("  galaxy update                Update Galaxy to latest version")


MANIFEST_SCHEMA = {
    "name":        {"type": str, "required": True,  "desc": "Package name (lowercase, hyphens)"},
    "version":     {"type": str, "required": True,  "desc": "Semantic version (e.g. 1.0.0)"},
    "description": {"type": str, "required": False, "desc": "Short description"},
    "author":      {"type": str, "required": False, "desc": "Author name"},
    "license":     {"type": str, "required": False, "desc": "License (e.g. MIT)"},
    "repository":  {"type": str, "required": False, "desc": "GitHub repo (owner/repo)"},
    "keywords":    {"type": list, "required": False, "desc": "Search keywords"},
    "main":        {"type": str, "required": False, "desc": "Entry file (e.g. src/main.nv)"},
    "dependencies": {"type": dict, "required": False, "desc": "Dependency name -> version"},
}


def create_default_manifest(name=None):
    if name is None:
        name = os.path.basename(os.getcwd())
    return {
        "name": name.lower().replace(" ", "-"),
        "version": "0.1.0",
        "description": "",
        "author": "",
        "license": "MIT",
        "repository": "",
        "keywords": [],
        "main": "src/main.nv",
        "dependencies": {},
    }


def load_manifest(path="."):
    mf = os.path.join(path, MANIFEST_FILE)
    if not os.path.exists(mf):
        print(f"Error: {MANIFEST_FILE} not found in {os.path.abspath(path)}")
        print("Run 'galaxy init' to create one.")
        sys.exit(1)
    try:
        with open(mf, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: Could not read {mf}: {exc}")
        sys.exit(1)
    if not isinstance(manifest, dict):
        print(f"Error: {mf} must contain a JSON object")
        sys.exit(1)
    return manifest


def save_manifest(manifest, path="."):
    mf = os.path.join(path, MANIFEST_FILE)
    with open(mf, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def load_lock(path="."):
    lock_path = os.path.join(path, LOCK_FILE)
    if not os.path.exists(lock_path):
        return {"lockfileVersion": 1, "packages": {}}
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            lock = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: Could not read {lock_path}: {exc}")
        sys.exit(1)
    if not isinstance(lock, dict) or lock.get("lockfileVersion") != 1:
        print(f"Error: {lock_path} has an unsupported lockfile format")
        sys.exit(1)
    if not isinstance(lock.get("packages"), dict):
        print(f"Error: {lock_path} must contain a packages object")
        sys.exit(1)
    return lock


def save_lock(lock, path="."):
    lock_path = os.path.join(path, LOCK_FILE)
    temporary = lock_path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(temporary, lock_path)


def compute_tree_hash(directory):
    """Deterministic SHA-256 over every file (relative path + content hash) under directory."""
    h = hashlib.sha256()
    base = os.path.abspath(directory)
    entries = []
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            entries.append((rel, compute_sha256(full)))
    for rel, digest in sorted(entries):
        h.update(f"{rel}\0{digest}\n".encode("utf-8"))
    return h.hexdigest()


def _lock_package(pkg_name, data, version_entry, tree_hash=None):
    lock = load_lock()
    entry = {
        "version": data.get("version", "") if data else "",
        "source": data.get("download_url") or data.get("github_repo", "") if data else "",
    }
    if version_entry and version_entry.get("sha256"):
        entry["sha256"] = version_entry["sha256"]
    if tree_hash:
        entry["tree_sha256"] = tree_hash
    lock["packages"][pkg_name] = entry
    save_lock(lock)


def validate_manifest(manifest):
    errors = []
    for field, spec in MANIFEST_SCHEMA.items():
        if spec["required"]:
            val = manifest.get(field)
            if not val:
                errors.append(f"Missing required field: {field} ({spec['desc']})")
            elif not isinstance(val, spec["type"]):
                errors.append(f"Field '{field}' must be {spec['type'].__name__}")
    if isinstance(manifest.get("name"), str) and not PACKAGE_REF_RE.fullmatch(manifest["name"]):
        errors.append("Field 'name' must contain only letters, numbers, '.', '_' or '-'")
    if isinstance(manifest.get("keywords"), list) and not all(isinstance(k, str) for k in manifest["keywords"]):
        errors.append("Field 'keywords' must contain only strings")
    if isinstance(manifest.get("dependencies"), dict):
        for dependency in manifest["dependencies"]:
            if not isinstance(dependency, str) or not PACKAGE_REF_RE.fullmatch(dependency):
                errors.append(f"Invalid dependency name: {dependency!r}")
    if errors:
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)


def _signature_checks_enabled():
    if os.environ.get("GALAXY_ALLOW_UNSIGNED") == "1":
        return False
    return bool(_registry_keys()) or os.environ.get("GALAXY_REQUIRE_SIGNATURE") == "1"


def _fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def registry_fetch(path):
    url = f"{REGISTRY_URL}/{path}"
    try:
        raw = _fetch_bytes(url)
        if path.startswith("packages/") and _signature_checks_enabled():
            try:
                sig_text = _fetch_bytes(url + ".sig").decode("ascii", "replace")
            except urllib.error.HTTPError:
                sig_text = ""
            if not verify_registry_signature(path, raw, sig_text):
                print(f"Error: registry metadata '{path}' has a missing or invalid signature; refusing to use it.")
                print("       Set GALAXY_ALLOW_UNSIGNED=1 only if you trust this network and registry.")
                sys.exit(1)
        return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception as e:
        print(f"Warning: Could not reach registry ({e})")
        return None


def registry_fetch_all():
    data = registry_fetch("packages/index.json")
    return data.get("packages", []) if data else []


def registry_fetch_pkg(name):
    return registry_fetch(f"packages/{name}.json")


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_nv_files(root):
    nv_files = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".nv"):
                nv_files.append(os.path.relpath(os.path.join(dirpath, fn), root))
    return sorted(nv_files)


def github_download_url(repo):
    return f"https://github.com/{repo}/archive/refs/heads/main.zip"


TEMPLATES = {}
TEMPLATES["library"] = {
    "desc": "Reusable Nova library package (default)",
    "scaffold": {
        "src/main.nv": """\
# {name} — main entry point
# Public API exported from this module.
# Other Nova programs import this via: import {name}

# Import the system library for I/O and OS operations
import system

# --- Public API ---
def greet(name: string) -> string {
    return "Hello, " + name + "!"
}

def add(a: int, b: int) -> int {
    return a + b
}

def is_even(n: int) -> bool {
    return n % 2 == 0
}
""",
        "src/types.nv": """\
# {name} — data type definitions
# Define your custom data structures here.
# Import this in main.nv: import types

# Example: a Point data type
data Point {
    x: int
    y: int
}

# Example: a Color enum
data Color {
    Red
    Green
    Blue
}

def make_point(x: int, y: int) -> Point {
    p = Point()
    p.x = x
    p.y = y
    return p
}

def distance(p: Point) -> int {
    dx = p.x * p.x
    dy = p.y * p.y
    return dx + dy
}
""",
        "tests/test_main.nv": """\
# Tests for {name}
# Run: galaxy test
# Or:  python bootstrap/main.py dev tests/test_main.nv

import system
import src.main as lib

# Test greet
result = lib.greet("Nova")
if result == "Hello, Nova!" {
    system.file_write(2, "PASS: greet\\n")
} else {
    system.file_write(2, "FAIL: greet got " + result + "\\n")
}

# Test add
if lib.add(2, 3) == 5 {
    system.file_write(2, "PASS: add\\n")
} else {
    system.file_write(2, "FAIL: add\\n")
}

# Test is_even
if lib.is_even(4) == true and lib.is_even(5) == false {
    system.file_write(2, "PASS: is_even\\n")
} else {
    system.file_write(2, "FAIL: is_even\\n")
}

system.file_write(2, "All {name} tests passed!\\n")
""",
        "tests/test_types.nv": """\
# Tests for {name} data types

import src.types as types

p = types.make_point(3, 4)
if p.x == 3 and p.y == 4 {
    system.file_write(2, "PASS: make_point\\n")
} else {
    system.file_write(2, "FAIL: make_point\\n")
}

d = types.distance(p)
if d == 25 {
    system.file_write(2, "PASS: distance\\n")
} else {
    system.file_write(2, "FAIL: distance\\n")
}
""",
        "examples/demo.nv": """\
# {name} — usage example
# Run: python bootstrap/main.py dev examples/demo.nv

import src.main as lib

name = "World"
print(lib.greet(name))
print(lib.add(10, 20))
print(lib.is_even(7))
""",
        "README.md": """# {name}

A Nova library.

## Usage

```bash
import {name}
```

## API

- `greet(name)` — Returns a greeting string
- `add(a, b)` — Adds two integers
- `is_even(n)` — Checks if a number is even

## Development

```bash
# Run tests
galaxy test

# Or directly
python bootstrap/main.py dev tests/test_main.nv
python bootstrap/main.py dev tests/test_types.nv

# Run example
python bootstrap/main.py dev examples/demo.nv
```
""",
    },
}
TEMPLATES["lib"] = {"desc": "Alias for library template", "alias": "library"}


def get_template(name):
    if name in TEMPLATES:
        t = TEMPLATES[name]
        if "alias" in t:
            return get_template(t["alias"])
        return t
    return None


def cmd_init(args):
    name = None
    template_name = "library"

    if not args:
        pass
    elif len(args) == 1:
        if args[0] in TEMPLATES:
            template_name = args[0]
        else:
            name = args[0]
    else:
        template_name = args[0]
        name = args[1]

    template = get_template(template_name)
    if not template:
        valid = ", ".join(k for k, v in TEMPLATES.items() if "alias" not in v)
        print(f"Unknown template '{template_name}'. Available: {valid}")
        return

    target_dir = name if name else "."

    if os.path.exists(os.path.join(target_dir, MANIFEST_FILE)):
        print(f"Error: {MANIFEST_FILE} already exists in {target_dir}")
        return

    if name and not os.path.exists(target_dir):
        os.makedirs(target_dir)

    manifest = create_default_manifest(name)
    save_manifest(manifest, target_dir)

    for rel_path, content_template in template["scaffold"].items():
        full_path = os.path.join(target_dir, rel_path)
        dir_name = os.path.dirname(full_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        if not os.path.exists(full_path):
            with open(full_path, "w") as f:
                f.write(content_template.replace("{name}", manifest["name"]))

    display_name = name or os.path.basename(os.getcwd())
    print(f"Initialized {template_name} package '{manifest['name']}'")
    print(f"  Template: {template_name} ({template['desc']})")
    for rel_path in sorted(template["scaffold"].keys()):
        print(f"  {rel_path}")
    print()
    print("Next steps:")
    print(f"  1. Edit {MANIFEST_FILE} and set your repository URL")
    print("  2. Write your code in src/")
    print("  3. Run 'galaxy test' to run tests")
    print("  4. Run 'galaxy publish' to submit to the registry")


def _verify_hashes(dest_dir, version_data, pkg_name, allow_unverified=False):
    """Verify SHA-256 hashes of extracted files against registry metadata."""
    expected_files = version_data.get("files") if version_data else None
    if not expected_files:
        if allow_unverified or os.environ.get("GALAXY_ALLOW_UNVERIFIED") == "1":
            print(f"  [WARN] No file hashes in registry metadata for '{pkg_name}' — skipping verification")
            return True
        print(f"  [FAIL] Registry metadata for '{pkg_name}' has no file hashes; refusing to install unverified code.")
        print("         Set GALAXY_ALLOW_UNVERIFIED=1 to override.")
        return False

    ok = True
    for ef in expected_files:
        path = ef.get("path", "")
        expected_hash = ef.get("sha256", "")
        if not path or not expected_hash:
            continue
        full_path = os.path.abspath(os.path.join(dest_dir, path))
        if not full_path.startswith(os.path.abspath(dest_dir) + os.sep):
            print(f"  [FAIL] Invalid hash path: {path}")
            ok = False
            continue
        if not os.path.exists(full_path):
            print(f"  [WARN] Missing file: {path}")
            ok = False
            continue
        actual = compute_sha256(full_path)
        if actual == expected_hash:
            print(f"  [OK]   {path}")
        else:
            print(f"  [FAIL] {path} (hash mismatch)")
            ok = False

    if ok:
        print(f"  All file hashes verified for '{pkg_name}'")
    else:
        print(f"  [FAIL] Some files failed hash verification for '{pkg_name}'")
    return ok


def _validate_package_ref(pkg_name):
    return isinstance(pkg_name, str) and bool(PACKAGE_REF_RE.fullmatch(pkg_name))


def _extract_archive(zip_data, dest_dir):
    """Extract a GitHub archive without allowing path traversal or symlinks."""
    if len(zip_data) > MAX_ARCHIVE_BYTES:
        raise ValueError(f"archive exceeds {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB limit")
    staging_dir = dest_dir + ".tmp-" + str(os.getpid())
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir, exist_ok=True)
    backup_dir = None
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as archive:
            if archive.testzip() is not None:
                raise ValueError("archive contains corrupted data")
            members = [m for m in archive.infolist() if m.filename]
            if not members:
                raise ValueError("archive is empty")
            top_dir = members[0].filename.split("/", 1)[0]
            for member in members:
                parts = member.filename.replace("\\", "/").split("/")
                if not parts or parts[0] != top_dir:
                    raise ValueError("archive has unexpected layout")
                rel_path = "/".join(parts[1:])
                if not rel_path:
                    continue
                if any(part in ("", ".", "..") for part in rel_path.split("/")):
                    raise ValueError(f"unsafe archive path: {member.filename}")
                mode = (member.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise ValueError(f"archive contains symlink: {member.filename}")
                target = os.path.abspath(os.path.join(staging_dir, *rel_path.split("/")))
                if not target.startswith(os.path.abspath(staging_dir) + os.sep):
                    raise ValueError(f"unsafe archive path: {member.filename}")
                if member.is_dir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with archive.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        if os.path.exists(dest_dir):
            backup_dir = dest_dir + ".backup-" + str(os.getpid())
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            os.replace(dest_dir, backup_dir)
        os.replace(staging_dir, dest_dir)
        return backup_dir
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _install_package(pkg_name, visited=None, force=False):
    """Internal install — supports transitive dependency resolution."""
    if visited is None:
        visited = set()

    if not _validate_package_ref(pkg_name):
        print(f"  Error: Invalid package reference '{pkg_name}'")
        return None
    if pkg_name in visited:
        print(f"  (already visited '{pkg_name}' — skipping cycle)")
        return None
    visited.add(pkg_name)

    pkg_dir_name = pkg_name.replace("/", "_")
    installed_path = os.path.join(GALAXY_MODULES_DIR, pkg_dir_name)
    if os.path.exists(installed_path) and not force:
        print(f"  '{pkg_name}' already installed at {installed_path}")
        return None

    print(f"  Installing '{pkg_name}'...")

    if "/" in pkg_name and not pkg_name.startswith("nova-"):
        github_repo = pkg_name
        download_url = github_download_url(github_repo)
        data = None
    else:
        data = registry_fetch_pkg(pkg_name)
        if not data:
            print(f"  Error: Package '{pkg_name}' was not found in the registry")
            return None
        github_repo = data.get("github_repo", pkg_name)
        download_url = data.get("download_url") or github_download_url(github_repo)

    if not download_url:
        print(f"  Error: Could not resolve download URL for '{pkg_name}'")
        return None
    lock = load_lock()
    locked = lock["packages"].get(pkg_name)
    if locked and data and not force:
        locked_version = locked.get("version")
        current_version = data.get("version")
        if locked_version and current_version != locked_version:
            print(
                f"  Error: '{pkg_name}' is locked to v{locked_version}, "
                f"but the registry currently resolves v{current_version}."
            )
            print("  Run 'galaxy upgrade' to intentionally update it.")
            return None

    os.makedirs(GALAXY_MODULES_DIR, exist_ok=True)
    dest_dir = os.path.join(GALAXY_MODULES_DIR, pkg_dir_name)

    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            zip_data = r.read()
        backup_dir = _extract_archive(zip_data, dest_dir)

        # SHA-256 verification
        version_str = data.get("version", "") if data else ""
        version_entry = None
        if data and "versions" in data:
            for v in data["versions"]:
                if v.get("version") == version_str:
                    version_entry = v
                    break
        # Direct GitHub refs (owner/repo) have no registry metadata and are explicitly unverified.
        if not _verify_hashes(dest_dir, version_entry, pkg_name, allow_unverified=data is None):
            shutil.rmtree(dest_dir, ignore_errors=True)
            if backup_dir and os.path.exists(backup_dir):
                os.replace(backup_dir, dest_dir)
            return None
        tree_hash = compute_tree_hash(dest_dir)
        locked_tree = locked.get("tree_sha256") if locked else None
        if locked_tree and not force and locked_tree != tree_hash:
            print(f"  [FAIL] Contents of '{pkg_name}' differ from the hash recorded in {LOCK_FILE}.")
            print("         The package changed after it was locked. Review it, then run")
            print(f"         'galaxy upgrade {pkg_name}' (or reinstall with force) to accept the new contents.")
            shutil.rmtree(dest_dir, ignore_errors=True)
            if backup_dir and os.path.exists(backup_dir):
                os.replace(backup_dir, dest_dir)
            return None
        if backup_dir:
            shutil.rmtree(backup_dir, ignore_errors=True)
        _lock_package(pkg_name, data, version_entry, tree_hash)

        # Transitive dependencies
        deps = data.get("dependencies", {}) if data else {}
        if deps:
            print(f"  Resolving dependencies...")
            for dep_name in deps:
                _install_package(dep_name, visited)

        version = version_str or github_repo
        manifest = load_manifest() if os.path.exists(MANIFEST_FILE) else create_default_manifest()
        if "dependencies" not in manifest:
            manifest["dependencies"] = {}
        manifest["dependencies"][pkg_name] = version
        save_manifest(manifest)

        print(f"  Successfully installed '{pkg_name}'")
        return dest_dir

    except urllib.error.HTTPError as e:
        print(f"  Error: Download failed (HTTP {e.code})")
        if e.code == 404:
            print(f"    Check that '{github_repo}' exists on GitHub")
        return None
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        backup_dir = locals().get("backup_dir")
        if backup_dir and os.path.exists(backup_dir):
            os.replace(backup_dir, dest_dir)
        print(f"  Error installing '{pkg_name}': {e}")
        return None


def cmd_install(args):
    if not args:
        print("Usage: galaxy install <pkg>")
        print("  <pkg> can be a registry name (e.g. nova-math)")
        print("  or a GitHub repo (e.g. owner/repo)")
        print()
        print("Transitive dependencies are resolved automatically.")
        return

    pkg_name = args[0]
    result = _install_package(pkg_name)
    if result:
        print(f"  Location: {result}")
        print(f"  Added to {MANIFEST_FILE}")
    else:
        print(f"Failed to install '{pkg_name}'")


def cmd_list(args):
    print("Installed Packages")
    print()

    deps = {}
    if os.path.exists(MANIFEST_FILE):
        manifest = load_manifest()
        deps = manifest.get("dependencies", {})
    else:
        print("  (no galaxy.json found)")

    if not deps:
        print("  No packages installed.")
        if os.path.exists(MANIFEST_FILE):
            print("  Run 'galaxy install <pkg>' to add packages.")
        else:
            print("  Run 'galaxy init' to create a project first.")
        return

    print(f"  {'Package':<20} {'Source':<30}")
    print(f"  {'-'*20} {'-'*30}")
    for pkg, source in deps.items():
        pkg_dir = os.path.join(GALAXY_MODULES_DIR, pkg.replace("/", "_"))
        installed = "installed" if os.path.exists(pkg_dir) else "not installed"
        print(f"  {pkg:<20} {installed:<30}")
        print(f"  {'':<20} {source:<30}")

    print()
    if os.path.exists(GALAXY_MODULES_DIR):
        nv_count = len(list(Path(GALAXY_MODULES_DIR).rglob("*.nv")))
        print(f"  {nv_count} .nv files in {GALAXY_MODULES_DIR}/")


def cmd_search(args):
    if not args:
        print("Usage: galaxy search <query>")
        return

    query = " ".join(args)
    print(f"Searching registry for '{query}'...")
    print()

    url = f"{REGISTRY_URL}/api/search?q={urllib.parse.quote(query)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"Search failed ({e}). Falling back to client-side search...")
        results = _client_side_search(query)
        data = {"packages": results} if results else {"packages": []}
        data["count"] = len(results)

    results = data.get("packages", [])
    if not results:
        print(f"No packages found matching '{query}'")
        return

    print(f"Found {data.get('count', len(results))} package(s):")
    print()
    for p in results:
        name = p.get("name", p.get("package", "?"))
        tier_tag = f"[{p.get('tier', 'unknown').upper()}]"
        kw = ", ".join(p.get("keywords", [])[:3])
        print(f"  {name:<15} {tier_tag:<10} v{p.get('version', '?')}")
        print(f"  {'':<15} {p.get('description', '')[:70]}")
        if kw:
            print(f"  {'':<15} keywords: {kw}")
        print()


def _client_side_search(query):
    """Fallback search that downloads the full index and filters locally."""
    q = query.lower()
    packages = registry_fetch_all()
    if not packages:
        return []
    results = []
    for p in packages:
        name = p.get("name", "").lower()
        desc = p.get("description", "").lower()
        keywords = [k.lower() for k in p.get("keywords", [])]
        author = p.get("author", "").lower()
        if (q in name or q in desc or q in author or
            any(q in kw for kw in keywords)):
            results.append(p)
    return results


def _find_nova_compiler():
    """Locate the Nova compiler: check PATH, then repo root."""
    # Check PATH for 'nova'
    nova_path = shutil.which("nova")
    if nova_path:
        return nova_path
    # Check for bootstrap/main.py in current dir or parents
    for root in [os.getcwd()] + [os.path.dirname(os.getcwd())]:
        candidate = os.path.join(root, "bootstrap", "main.py")
        if os.path.exists(candidate):
            return candidate
    return None


def _compile_and_run(nv_file, compiler, use_vm):
    """Compile a .nv file and run it. Returns (exit_code, output_lines)."""
    if use_vm:
        cmd = [sys.executable, compiler, "dev", nv_file] if compiler.endswith(".py") else [compiler, "dev", nv_file]
    else:
        # Build native, then run
        build_cmd = [sys.executable, compiler, "build", nv_file] if compiler.endswith(".py") else [compiler, "build", nv_file]
        r = subprocess.run(build_cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return (r.returncode, r.stdout.splitlines() + r.stderr.splitlines())
        # Find output binary
        base = os.path.splitext(nv_file)[0]
        exe_path = base + (".exe" if sys.platform == "win32" else "")
        if not os.path.exists(exe_path):
            return (1, [f"Error: compiled binary not found at {exe_path}"])
        cmd = [exe_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return (r.returncode, r.stdout.splitlines() + r.stderr.splitlines())


def cmd_test(args):
    """Run all tests for the current library package.
    
    Usage: galaxy test [--vm] [test_name]
    
    --vm        Run in VM mode (faster, no native compilation)
    test_name   Run only tests matching this substring
    """
    use_vm = "--vm" in args
    filter_str = None
    for a in args:
        if a != "--vm":
            filter_str = a

    test_dir = "tests"
    if not os.path.isdir(test_dir):
        print("Error: no 'tests/' directory found")
        return

    test_files = sorted([f for f in os.listdir(test_dir) if f.endswith(".nv")])
    if filter_str:
        test_files = [f for f in test_files if filter_str in f]

    if not test_files:
        print("No tests found.")
        return

    compiler = _find_nova_compiler()
    if not compiler:
        print("Error: Nova compiler not found. Install Nova or run from repo root.")
        return

    mode = "VM" if use_vm else "native"
    print(f"Running {len(test_files)} test(s) ({mode})...\n")

    passed = 0
    failed = 0
    for tf in test_files:
        path = os.path.join(test_dir, tf)
        print(f"  [{tf}] ", end="", flush=True)
        exit_code, output = _compile_and_run(path, compiler, use_vm)
        if exit_code == 0:
            print("PASS")
            passed += 1
        else:
            print("FAIL")
            failed += 1
            for line in output:
                print(f"    {line}")

    total = passed + failed
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{total} passed", end="")
    if failed:
        print(f", {failed} failed", end="")
    print()

    if failed:
        sys.exit(1)


def cmd_info(args):
    if not args:
        print("Usage: galaxy info <pkg>")
        return

    pkg_name = args[0]
    data = registry_fetch_pkg(pkg_name)

    if not data:
        print(f"Package '{pkg_name}' not found in registry.")
        print(f"Check: {REGISTRY_URL}/packages/{pkg_name}.json")
        return

    print(f"Package:     {data.get('package', pkg_name)}")
    print(f"Tier:        {data.get('tier', '?')}")
    print(f"Version:     {data.get('version', '?')}")
    print(f"Author:      {data.get('author', '?')}")
    print(f"License:     {data.get('license', '?')}")
    print(f"Repository:  {data.get('github_repo', '?')}")
    print(f"Upvotes:     {data.get('upvotes', 0)}")
    print(f"Flags:       {data.get('flags', 0)}")
    print(f"Description: {data.get('description', '')}")
    print()

    kw = data.get("keywords", [])
    if kw:
        print(f"Keywords: {', '.join(kw)}")

    versions = data.get("versions", [])
    if versions:
        print(f"Versions ({len(versions)}):")
        for v in versions[-5:]:
            print(f"  {v['version']:<12} {v.get('sha256', '')[:16]}...")
        if len(versions) > 5:
            print(f"  ... and {len(versions) - 5} more")

    examples = data.get("examples", [])
    if examples:
        print(f"Examples ({len(examples)}):")
        for ex in examples[:2]:
            print(f"  {ex.get('title', 'Untitled')}")
            for line in ex.get("code", "").split("\n")[:3]:
                print(f"    {line}")

    print()
    if data.get("quarantined"):
        print("WARNING: This package is quarantined!")

    print(f"Install: galaxy install {pkg_name}")


PUBLISH_ISSUE_TEMPLATE = """\
## Package Submission

**This is an automated submission from `galaxy publish`.**

### Package Metadata

```json
{METADATA}
```

### Source Files

| File | SHA-256 |
|------|---------|
{FILE_HASHES}

### Checklist
- [ ] I have read the contribution guidelines
- [ ] My package does not duplicate existing functionality
- [ ] I have included a license file
- [ ] The package name is unique (lowercase, hyphens only)

---

*Submitted via Galaxy CLI*
"""


def cmd_publish(args):
    if not os.path.exists(MANIFEST_FILE):
        print(f"Error: {MANIFEST_FILE} not found.")
        print("Run 'galaxy init' first.")
        return

    manifest = load_manifest()
    validate_manifest(manifest)

    if not manifest.get("repository"):
        print("Error: 'repository' field is required in galaxy.json")
        print("Set it to your GitHub repo (e.g. your-username/your-repo)")
        return

    print("Preparing package for submission...")
    print()

    print(f"Package:     {manifest['name']}")
    print(f"Version:     {manifest['version']}")
    print(f"Author:      {manifest.get('author', '(not set)')}")
    print(f"Repository:  {manifest['repository']}")
    print(f"License:     {manifest.get('license', 'MIT')}")
    print(f"Description: {manifest.get('description', '(none)')}")
    print()

    nv_files = find_nv_files(".")
    if not nv_files:
        print("Warning: No .nv files found in current directory")
    else:
        print(f"Source files ({len(nv_files)}):")
        file_hashes = []
        for nvf in nv_files:
            sha = compute_sha256(nvf)
            file_hashes.append((nvf, sha))
            print(f"  {nvf:<30} {sha[:16]}...")
        print()

    submission = {
        "package": manifest["name"],
        "version": manifest["version"],
        "description": manifest.get("description", ""),
        "author": manifest.get("author", ""),
        "license": manifest.get("license", "MIT"),
        "github_repo": manifest["repository"],
        "keywords": manifest.get("keywords", []),
        "dependencies": manifest.get("dependencies", {}),
        "files": [{"path": f, "sha256": s} for f, s in file_hashes] if file_hashes else [],
    }

    metadata_json = json.dumps(submission, indent=2)
    file_hashes_md = "\n".join(
        f"| `{f}` | `{s[:16]}...` |" for f, s in (file_hashes or [])
    ) or "| (none) | - |"

    issue_body = PUBLISH_ISSUE_TEMPLATE.format(
        METADATA=metadata_json,
        FILE_HASHES=file_hashes_md,
    )

    issue_title = f"Submission: {manifest['name']} v{manifest['version']}"
    params = f"title={urllib.parse.quote(issue_title)}&body={urllib.parse.quote(issue_body)}&labels=submission"
    issue_url = f"https://github.com/{REGISTRY_REPO}/issues/new?{params}"

    print("Submission Summary:")
    print(f"  Package:    {manifest['name']} v{manifest['version']}")
    print(f"  Repository: {manifest['repository']}")
    print(f"  Files:      {len(file_hashes)} .nv source files")
    print(f"  Registry:   {REGISTRY_URL}")
    print()

    answer = input("Open a GitHub Issue to submit? (Y/n): ").strip().lower()
    if answer in ("", "y", "yes"):
        print(f"Opening {issue_url}")
        webbrowser.open(issue_url)
        print()
        print("After submitting, an admin will review your package.")
        print("Track it at: https://github.com/{REGISTRY_REPO}/issues")
    else:
        print("Cancelled. You can manually submit here:")
        print(f"  {issue_url}")


def _detect_install_dir():
    """Detect the Galaxy installation directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "_galaxy.py")):
        return script_dir
    known = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "nova"),
        os.path.join(os.path.expanduser("~"), ".nova"),
    ]
    for p in known:
        if p and os.path.exists(os.path.join(p, "_galaxy.py")):
            return p
    return script_dir


def cmd_update(args):
    """Update Galaxy CLI itself."""
    print(f"Galaxy v{GALAXY_VERSION}")
    print()

    if args:
        cmd_upgrade(args)
        return

    try:
        data = registry_fetch("versions/galaxy.json")
        if not data:
            print("Could not check for updates. Check your connection.")
            return
        latest = data.get("version", "")
    except Exception as e:
        print(f"Could not check for updates ({e})")
        return

    if latest == GALAXY_VERSION:
        print(f"Already up to date (v{GALAXY_VERSION}).")
        return

    print(f"Latest version: v{latest}  (current: v{GALAXY_VERSION})")
    answer = input(f"Update to v{latest}? (Y/n): ").strip().lower()
    if answer not in ("", "y", "yes"):
        print("Update cancelled.")
        return

    install_dir = _detect_install_dir()
    print(f"Install directory: {install_dir}")
    print("Downloading...")

    url = f"{GALAXY_RELEASE_BASE}/galaxy-v{latest}/galaxy-v{latest}.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nova-Galaxy/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            zip_data = r.read()
    except Exception as e:
        print(f"Download failed ({e}). Falling back to full repo zip...")
        try:
            req = urllib.request.Request(NOVA_ZIP_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                zip_data = r.read()
        except Exception as e2:
            print(f"Download failed: {e2}")
            return

    print("Extracting...")
    count = 0
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        bad = zf.testzip()
        if bad is not None:
            print(f"Corrupted archive: {bad}")
            return
        for name in zf.namelist():
            rel = name
            if rel.startswith(ZIP_PREFIX + "/"):
                rel = rel[len(ZIP_PREFIX) + 1:]
            if not rel or rel.endswith("/"):
                continue
            parts = rel.split("/")
            top = parts[0]
            if top in ("_galaxy.py",) or top == "galaxy" or rel.startswith("galaxy/"):
                dst = os.path.join(install_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(name) as src, open(dst, "wb") as df:
                    shutil.copyfileobj(src, df)
                count += 1

    print(f"Updated {count} files.")
    print(f"Galaxy has been updated to v{latest}.")
    print("Restart your terminal or run 'galaxy --version' to confirm.")


def cmd_upgrade(args):
    if not os.path.exists(MANIFEST_FILE):
        print(f"Error: {MANIFEST_FILE} not found.")
        return

    manifest = load_manifest()
    deps = manifest.get("dependencies", {})

    if not deps:
        print("No packages installed.")
        return

    target = args[0] if args else None
    to_update = {k: v for k, v in deps.items() if not target or k == target}

    if not to_update:
        if target:
            print(f"Package '{target}' not found in dependencies.")
        return

    for pkg, source in to_update.items():
        print(f"Checking '{pkg}'...")
        data = registry_fetch_pkg(pkg)
        if not data:
            print(f"  Could not check registry for '{pkg}'")
            continue

        latest = data.get("newestVersion") or data.get("version")
        print(f"  Installed: {source}  Registry: {latest}")
        if latest and latest != source:
            answer = input(f"  Update to v{latest}? (y/N): ").strip().lower()
            if answer in ("y", "yes"):
                print(f"  Reinstalling '{pkg}' v{latest}...")
                _install_package(pkg, force=True)
            else:
                print(f"  Skipped")
        else:
            print(f"  Already up to date")
        print()


def cmd_remove(args):
    if not args:
        print("Usage: galaxy remove <pkg>")
        return

    pkg = args[0]
    if not _validate_package_ref(pkg):
        print(f"Invalid package reference '{pkg}'.")
        return
    removed = False

    pkg_dir = os.path.abspath(os.path.join(GALAXY_MODULES_DIR, pkg.replace("/", "_")))
    modules_root = os.path.abspath(GALAXY_MODULES_DIR)
    if pkg_dir.startswith(modules_root + os.sep) and os.path.exists(pkg_dir):
        shutil.rmtree(pkg_dir)
        print(f"Removed {pkg_dir}/")
        removed = True

    if os.path.exists(MANIFEST_FILE):
        manifest = load_manifest()
        deps = manifest.get("dependencies", {})
        if pkg in deps:
            del deps[pkg]
            manifest["dependencies"] = deps
            save_manifest(manifest)
            print(f"Removed from {MANIFEST_FILE}")
            removed = True
    lock = load_lock()
    if pkg in lock["packages"]:
        del lock["packages"][pkg]
        save_lock(lock)
        print(f"Removed from {LOCK_FILE}")
        removed = True

    if removed:
        print(f"Package '{pkg}' removed.")
    else:
        print(f"Package '{pkg}' not found.")


if __name__ == "__main__":
    main()
