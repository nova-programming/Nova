# Agent Session Summary

## Global Lock
- None

## Current State
- **Galaxy Package Manager**: Fully implemented and live at [galaxy-registry.vercel.app](https://galaxy-registry.vercel.app)
- **Compiler**: Stable, tree-shaking + variable-to-register promotion + self-hosted bootstrap working
- **Installer**: Native `install.sh` (bash, uses only curl+tar) + `install.ps1` (PowerShell) + `install.py` (Python fallback) — no dependencies required
- **Version System**: `nova --version` / `galaxy --version` + `nova update` / `galaxy update` self-update commands powered by registry version endpoints

## What Was Accomplished

### Package Manager (Galaxy)
- **galaxy-registry** static website on Vercel with tier-filtered package grid, detail views, documentation, admin dashboard
- **`_galaxy.py`** — single-file CLI (750+ lines) with `init`, `install`, `publish`, `list`, `search`, `info`, `update` (self-update), `upgrade` (package update), `remove`, `--version`
- **Three trust tiers**: Core (inbuilt), Verified (human-reviewed), Community (auto-published)
- **Template system**: `galaxy init library` scaffolds project structure
- **Publishing**: `galaxy publish` validates manifest, computes SHA-256, opens GitHub Issue
- **galaxy.json schema**: name, version, description, author, license, repository, keywords, main, dependencies
- **GitHub Actions**: PR validation, auto-quarantine (5+ flags), promotion queue (50+ upvotes)
- **19 CLI tests** all passing

### Unified Installer (`install.py`)
- Downloads Nova repo zip from GitHub, extracts only essential files (39 files across 8 directories)
- Installs both `nova` and `galaxy` launchers globally
- Adds to user PATH (Windows via Registry, Unix via shell config)
- Progress reporting during download, zip integrity verification
- Supports `--uninstall`
- Hosted at `https://galaxy-registry.vercel.app/install.py` for one-command install

### Version & Self-Update System
- **`nova --version` / `galaxy --version`** — displays current version from constants (`NOVA_VERSION`, `GALAXY_VERSION`)
- **`nova update`** — self-updates Nova compiler: checks registry endpoint, downloads repo zip, extracts only compiler files
- **`galaxy update`** — self-updates Galaxy CLI: checks registry endpoint, downloads repo zip, extracts only galaxy files
- **`galaxy upgrade [pkg]`** — updates installed packages (replaces old `galaxy update <pkg>` naming)
- **Version endpoints** at `galaxy-registry.vercel.app/versions/nova.json` and `versions/galaxy.json` — static JSON files served by Vercel
- Update flow: compares versions → shows diff → prompts "Update to vX.Y.Z? (Y/n)" with default Y → replaces only necessary files
- No app/cli templates — only `library` template remains in codebase

### Self-Hosted Bootstrap Fixed (This Session)
- **`_fopen` "wb" mode bug** (`codegen_x86.py:1222`): `_fopen` used `_strcmp` to match mode strings against "w", "w+", "r+", "a" but NOT "wb". `sys_open(path, "wb")` fell through to default read mode (OPEN_EXISTING/GENERIC_READ), so the PE output file was never created. Fixed by checking first char of mode string instead of exact match — handles all mode variants (w, wb, w+, w+b, r, rb, r+, a, ab, etc.).
- **`_fputs` HANDLE dereference bug** (`codegen_x86.py:1272-1273`, `codegen.nv:3824-3825`): `_fputs` executed `mov eax, [ebp + 12]; push dword ptr [eax]` — dereferencing the HANDLE as if it were a pointer to a HANDLE. `_fputc` and `_fwrite` correctly passed the HANDLE directly. This caused `STATUS_ACCESS_VIOLATION` (0xC0000005) when `compile_to_exe` called `sys_write(fd, string)` during assembly file output. Fixed by changing to `push dword ptr [ebp + 12]` (direct HANDLE, no dereference).
- **Result**: `nova.exe build <file.nv>` now works end-to-end. Full self-hosted bootstrap: reads source → tokenizes → parses → type-checks → generates assembly → writes `.s` file → assembles → links → produces working PE executable. Both `nova.exe assemble-link` and `nova.exe build` commands are functional.
- **Cross-drive relpath fix** (`main.py:131-136`): `os.path.relpath()` raises `ValueError` when source and destination are on different Windows drives (e.g., GCC on C:, project on D:). Caught exception and falls back to absolute paths.

### Compiler Codegen Fixes (Previous Session)
- **`_is_string_expr` bug** (`codegen_x86.py:144,146`): `self.is_pure_expression` → `self.is_leaf_expr` (referenced undefined method on `X86Codegen`, blocking all `nova build`).
- **Entry point name** (`codegen_x86.py:270`): `_nova_start:` → `_main:` — GCC couldn't find the entry symbol since `.global _main` was declared but `_main:` never defined.
- **`GetCommandLineA` stdcall decoration** (`codegen_x86.py:197,2007` + `codegen.nv:873,3946`): Call and extern now consistently use `_GetCommandLineA@0` (with `@0` suffix), matching MinGW's kernel32 import library.

### GCC Bundling (This Session)
- **`main.py`**: New `_find_gcc()` — checks bundled `gcc/bin/gcc.exe` first, then system PATH. Clear platform-specific install instructions when missing. Cross-drive `relpath` fix.
- **`install.ps1`**: Downloads portable winlibs MinGW-w64 (~130MB) into `<InstallDir>/gcc/` if `gcc` not on PATH. Handles silent extraction of the `.zip` archive.
- **`install.py`**: Same GCC bundling logic — downloads winlibs on Windows, warns with package manager instructions on Unix.
- **`install.sh`**: Detects GCC presence after extraction, warns if missing with platform-specific install commands.
- **`nova build` auto-fallback**: Tries `nova.exe assemble-link` first (verifies output exists), falls back to system/bundled GCC.

### Version Bump
- **NOVA_VERSION**: `0.5.0` → `0.6.0`

### GitHub Release Automation
- **`.github/workflows/release.yml`** — triggers on `nova-v*` or `galaxy-v*` tags
- Builds production-only `.zip` + `.tar.gz` archives containing only the files needed
- Creates GitHub Release with archives attached
- Auto-updates `versions/nova.json` or `versions/galaxy.json` in the galaxy-registry repo
- Update commands (`nova update`, `galaxy update`) prefer release archives (lean download), fall back to full repo zip

### SHA-256 Verification
- **`galaxy install`** verifies file hashes against registry metadata after extraction
- Registry package JSONs expanded with per-version file-level SHA-256 hashes
- Warns on hash mismatch or missing files

### Transitive Dependency Resolution
- **`galaxy install pkg`** recursively installs dependencies from package metadata
- Cycle detection via visited set — skips already-installed or in-progress packages
- Dependencies installed before the parent package

### Serverless Search API
- **`api/search.js`** — Vercel Edge Function at `galaxy-registry.vercel.app/api/search?q=query`
- Filters `packages/index.json` server-side, returns only matching results
- `galaxy search` uses it by default, falls back to client-side index download

### Website Documentation
- **index.html**: Hero with one-liner install, Getting Started guide, tiered library browser, package detail views
- **documentation.html**: Full Galaxy CLI reference (install, commands, templates, manifest, publishing)
- **templates.html**: Dedicated template reference page with file structures, examples, schema
- **admin.html**: Login-gated admin dashboard with tab system and GitHub Issues-based moderation

### Infrastructure
- `nova_ast/` renamed from `ast/` to fix Python stdlib collision
- `_galaxy.py` is canonical CLI source; `galaxy/__init__.py`, `tools/galaxy.py` are thin re-export shims
- `galaxy.cmd` updated as manual fallback wrapper
- `pyproject.toml` console_scripts entry for `pip install`
- GitHub foundry cross-repo linking (nova-programming/Nova + galaxy-registry)

## Commands Reference
```powershell
# One-command install
curl -O https://galaxy-registry.vercel.app/install.sh && bash install.sh

# Usage after install
nova build hello.nv        # Compile Nova program
nova --version             # Check Nova version
nova update                # Update Nova compiler
galaxy init library my-lib # Create a library
galaxy install pkg         # Install from registry
galaxy --version           # Check Galaxy version
galaxy update              # Update Galaxy CLI
galaxy upgrade [pkg]       # Update installed packages
galaxy publish             # Publish to registry
```
