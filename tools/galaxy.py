"""
Galaxy Package Manager for Nova
Standalone CLI: galaxy <command> [args]
Also: python -m tools.galaxy <command> [args]  or  nova galaxy <command>
"""

import sys
import os
import json
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import zipfile
import io
import textwrap
import webbrowser
from pathlib import Path

REGISTRY_URL = "https://galaxy-registry.vercel.app"
REGISTRY_REPO = "nova-programming/galaxy-registry"
GALAXY_MODULES_DIR = "galaxy_modules"
MANIFEST_FILE = "galaxy.json"


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "init":    cmd_init,
        "install": cmd_install,
        "list":    cmd_list,
        "search":  cmd_search,
        "info":    cmd_info,
        "publish": cmd_publish,
        "update":  cmd_update,
        "remove":  cmd_remove,
    }

    if cmd in commands:
        commands[cmd](args)
    elif cmd in ("-h", "--help", "help"):
        print_usage()
    else:
        print(f"Unknown command: {cmd}")
        print_usage()


def print_usage():
    print("Galaxy Package Manager for Nova")
    print()
    print("Usage:")
    print("  galaxy init [template] [name]   Create a package")
    print("                       Templates: library, app, cli")
    print("  galaxy install <pkg>           Install a package")
    print("  galaxy list              List installed packages")
    print("  galaxy search <query>    Search the registry")
    print("  galaxy info <pkg>        Show package details")
    print("  galaxy publish           Publish current package to registry")
    print("  galaxy update [pkg]      Update installed packages")
    print("  galaxy remove <pkg>      Remove an installed package")
    print()
    print("Examples:")
    print("  galaxy init my-lib")
    print("  galaxy init library my-lib")
    print("  galaxy init app my-app")
    print("  galaxy init cli my-tool")
    print("  galaxy install nova-math")
    print("  galaxy install owner/repo")
    print("  galaxy search http")
    print("  galaxy publish")


# ---------------------------------------------------------------------------
# galaxy.json manifest schema
# ---------------------------------------------------------------------------

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
    with open(mf, "r") as f:
        return json.load(f)


def save_manifest(manifest, path="."):
    mf = os.path.join(path, MANIFEST_FILE)
    with open(mf, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def validate_manifest(manifest):
    errors = []
    for field, spec in MANIFEST_SCHEMA.items():
        if spec["required"]:
            val = manifest.get(field)
            if not val:
                errors.append(f"Missing required field: {field} ({spec['desc']})")
            elif not isinstance(val, spec["type"]):
                errors.append(f"Field '{field}' must be {spec['type'].__name__}")
    if errors:
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def registry_fetch(path):
    url = f"{REGISTRY_URL}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Nova-Galaxy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
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


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

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
    "desc": "Reusable library package (default)",
    "scaffold": {
        "src/main.nv": 'import "os"\n\nprint("Hello from {name}!")\n',
        "tests/test_main.nv": '# Tests for {name}\nprint("All tests passed!")\n',
    },
}
TEMPLATES["app"] = {
    "desc": "Standalone application",
    "scaffold": {
        "src/main.nv": (
            'import "os"\nimport "cli"\n\n'
            "fn main() {{\n"
            '    args = os.args()\n'
            '    print("Welcome to {name}!")\n'
            '    print("Args:", args)\n'
            "}}\n\n"
            "main()\n"
        ),
        "src/lib.nv": (
            "pub fn version() -> string {{\n"
            '    return "0.1.0"\n'
            "}}\n"
        ),
        "README.md": "# {name}\n\nA Nova application.\n\n## Usage\n\n```\nnova run src/main.nv\n```\n",
        "tests/test_main.nv": '# Tests for {name}\nprint("All tests passed!")\n',
    },
}
TEMPLATES["cli"] = {
    "desc": "Command-line tool with argument parsing",
    "scaffold": {
        "src/main.nv": (
            'import "os"\nimport "cli"\n\n'
            "fn main() {{\n"
            '    args = cli.parse("{name} [command] --verbose")\n'
            "    if args.verbose {{\n"
            '        print("Verbose mode")\n'
            "    }}\n"
            '    print("Hello from {name}!")\n'
            "}}\n\n"
            "main()\n"
        ),
        "src/commands.nv": (
            "pub fn handle_install(args) {{\n"
            '    print("Install command")\n'
            "}}\n\n"
            "pub fn handle_build(args) {{\n"
            '    print("Build command")\n'
            "}}\n"
        ),
        "tests/test_cli.nv": '# CLI tests for {name}\nprint("CLI tests passed!")\n',
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


# ---------------------------------------------------------------------------
# COMMAND: galaxy init [template] [name]
# ---------------------------------------------------------------------------

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
                f.write(content_template.format(name=manifest["name"]))

    display_name = name or os.path.basename(os.getcwd())
    print(f"Initialized {template_name} package '{manifest['name']}'")
    print(f"  Template: {template_name} ({template['desc']})")
    for rel_path in sorted(template["scaffold"].keys()):
        print(f"  {rel_path}")
    print()
    if not manifest["repository"]:
        print("Next steps:")
        print(f"  1. Edit {MANIFEST_FILE} and set your repository URL")
        print("  2. Write your code in src/")
        print("  3. Run 'galaxy publish' to submit to the registry")


# ---------------------------------------------------------------------------
# COMMAND: galaxy install <pkg>
# ---------------------------------------------------------------------------

def cmd_install(args):
    if not args:
        print("Usage: galaxy install <pkg>")
        print("  <pkg> can be a registry name (e.g. nova-math)")
        print("  or a GitHub repo (e.g. owner/repo)")
        return

    pkg_name = args[0]
    print(f"Resolving '{pkg_name}'...")

    # Determine download source
    github_repo = None
    download_url = None
    version = None

    if "/" in pkg_name and not pkg_name.startswith("nova-"):
        # GitHub shorthand: owner/repo
        github_repo = pkg_name
        download_url = github_download_url(github_repo)
        print(f"  Source: GitHub ({github_repo})")
    else:
        # Look up in registry
        data = registry_fetch_pkg(pkg_name)
        if data:
            github_repo = data.get("github_repo", pkg_name)
            download_url = data.get("download_url") or github_download_url(github_repo)
            version = data.get("version")
            print(f"  Source: Registry ({data.get('tier', 'community')} tier, v{version})")
        else:
            # Fallback: try as GitHub repo
            github_repo = pkg_name
            download_url = github_download_url(github_repo)
            print(f"  Source: GitHub (fallback, {github_repo})")

    if not download_url:
        print("Error: Could not resolve download URL.")
        return

    # Download zip
    os.makedirs(GALAXY_MODULES_DIR, exist_ok=True)
    dest_dir = os.path.join(GALAXY_MODULES_DIR, pkg_name.replace("/", "_"))

    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": "Nova-Galaxy/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            zip_data = r.read()

        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            # Strip top-level directory from zip (GitHub wraps in repo-branch folder)
            members = z.infolist()
            top_dir = os.path.commonprefix([m.filename for m in members]).split("/")[0]

            if os.path.exists(dest_dir):
                import shutil
                shutil.rmtree(dest_dir)

            for m in members:
                # Strip the top directory
                rel_path = m.filename[len(top_dir)+1:]
                if not rel_path:
                    continue
                target = os.path.join(dest_dir, rel_path)
                if m.is_dir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(m) as src, open(target, "wb") as dst:
                        dst.write(src.read())

        # Update manifest dependencies
        manifest = load_manifest() if os.path.exists(MANIFEST_FILE) else create_default_manifest()
        if "dependencies" not in manifest:
            manifest["dependencies"] = {}
        manifest["dependencies"][pkg_name] = version or github_repo
        save_manifest(manifest)

        print(f"Successfully installed '{pkg_name}'")
        print(f"  Location: {dest_dir}")
        print(f"  Added to {MANIFEST_FILE}")

    except urllib.error.HTTPError as e:
        print(f"Error: Download failed (HTTP {e.code})")
        if e.code == 404:
            print(f"  Check that '{github_repo}' exists on GitHub")
    except Exception as e:
        print(f"Error installing package: {e}")


# ---------------------------------------------------------------------------
# COMMAND: galaxy list
# ---------------------------------------------------------------------------

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
        pkg_dir = os.path.join(GALAXY_MODULES_DIR, pkg)
        installed = "installed" if os.path.exists(pkg_dir) else "not installed"
        print(f"  {pkg:<20} {installed:<30}")
        print(f"  {'':<20} {source:<30}")

    print()
    if os.path.exists(GALAXY_MODULES_DIR):
        nv_count = len(list(Path(GALAXY_MODULES_DIR).rglob("*.nv")))
        print(f"  {nv_count} .nv files in {GALAXY_MODULES_DIR}/")


# ---------------------------------------------------------------------------
# COMMAND: galaxy search <query>
# ---------------------------------------------------------------------------

def cmd_search(args):
    if not args:
        print("Usage: galaxy search <query>")
        return

    query = " ".join(args).lower()
    print(f"Searching registry for '{query}'...")
    print()

    packages = registry_fetch_all()
    if not packages:
        print("Could not reach registry. Try again later.")
        return

    results = []
    for p in packages:
        name = p.get("name", "").lower()
        desc = p.get("description", "").lower()
        keywords = [k.lower() for k in p.get("keywords", [])]
        author = p.get("author", "").lower()

        if (query in name or query in desc or query in author or
            any(query in kw for kw in keywords)):
            results.append(p)

    if not results:
        print(f"No packages found matching '{query}'")
        return

    print(f"Found {len(results)} package(s):")
    print()
    for p in results:
        tier_tag = f"[{p.get('tier', 'unknown').upper()}]"
        kw = ", ".join(p.get("keywords", [])[:3])
        print(f"  {p['name']:<15} {tier_tag:<10} v{p.get('version', '?')}")
        print(f"  {'':<15} {p.get('description', '')[:70]}")
        if kw:
            print(f"  {'':<15} keywords: {kw}")
        print()


# ---------------------------------------------------------------------------
# COMMAND: galaxy info <pkg>
# ---------------------------------------------------------------------------

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

    # Show install hint
    print(f"Install: galaxy install {pkg_name}")


# ---------------------------------------------------------------------------
# COMMAND: galaxy publish
# ---------------------------------------------------------------------------

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

    # Show manifest
    print(f"Package:     {manifest['name']}")
    print(f"Version:     {manifest['version']}")
    print(f"Author:      {manifest.get('author', '(not set)')}")
    print(f"Repository:  {manifest['repository']}")
    print(f"License:     {manifest.get('license', 'MIT')}")
    print(f"Description: {manifest.get('description', '(none)')}")
    print()

    # Compute SHA-256 hashes of source files
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

    # Build metadata JSON for submission
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

    # Build GitHub Issue
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

    # Ask and open
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


# ---------------------------------------------------------------------------
# COMMAND: galaxy update [pkg]
# ---------------------------------------------------------------------------

def cmd_update(args):
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

        latest = data.get("version")
        print(f"  Installed: {source}  Registry: {latest}")
        if latest and latest != source:
            answer = input(f"  Update to v{latest}? (y/N): ").strip().lower()
            if answer in ("y", "yes"):
                print(f"  Reinstalling '{pkg}' v{latest}...")
                cmd_install([pkg])
            else:
                print(f"  Skipped")
        else:
            print(f"  Already up to date")
        print()


# ---------------------------------------------------------------------------
# COMMAND: galaxy remove <pkg>
# ---------------------------------------------------------------------------

def cmd_remove(args):
    if not args:
        print("Usage: galaxy remove <pkg>")
        return

    pkg = args[0]
    removed = False

    # Remove from filesystem
    pkg_dir = os.path.join(GALAXY_MODULES_DIR, pkg)
    if os.path.exists(pkg_dir):
        import shutil
        shutil.rmtree(pkg_dir)
        print(f"Removed {pkg_dir}/")
        removed = True

    # Handle underscore variant (from owner/repo installs)
    alt_dir = os.path.join(GALAXY_MODULES_DIR, pkg.replace("/", "_"))
    if os.path.exists(alt_dir):
        import shutil
        shutil.rmtree(alt_dir)
        removed = True

    # Remove from manifest
    if os.path.exists(MANIFEST_FILE):
        manifest = load_manifest()
        deps = manifest.get("dependencies", {})
        if pkg in deps:
            del deps[pkg]
            manifest["dependencies"] = deps
            save_manifest(manifest)
            print(f"Removed from {MANIFEST_FILE}")
            removed = True

    if removed:
        print(f"Package '{pkg}' removed.")
    else:
        print(f"Package '{pkg}' not found.")


# ---------------------------------------------------------------------------
# Entry point for standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
