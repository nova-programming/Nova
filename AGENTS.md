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

### Language Features (This Session — June 2026)
- **Switch/match**: `switch expr { case val { body } else { body } }` syntax, desugars at parse time to if-elif-else chain. No AST/codegen changes needed. Both Python parser (`parser/parser.py:755-777`) and self-hosted parser (`stdlib/parser.nv:978-1032`) implement this.
- **HashMap/Dictionary**: Existing `{"key": val}` literal syntax enhanced with `get(key)`, `set(key, val)`, `items()` methods + `len()` for dict. Dict literal parsing added to self-hosted `parser.nv` (interleaved key-value pairs in `args` list). Works in `nova dev` (VM); native codegen emits placeholder comment + `push 0`.
- **VM dict methods** (`vm/machine.py:518-552`): `has`, `get`, `set`, `remove`, `keys`, `values`, `items` — all backed by Python `dict`.
- **Dict in codegen** (`stdlib/codegen_expr.nv:1063-1074`): `node_to_asm` formats dicts, `compile_expr` emits placeholder for native.

### Self-Hosted Compiler Refactoring (This Session)
- **`match_keyword` → `switch`** (`stdlib/lexer.nv:32-82`): Replaced 49-line if-chain with single switch statement covering all 44 Nova keywords
- **Two-char operator matching → `switch`** (`stdlib/lexer.nv:225-242`): `==`, `!=`, `<=`, `>=`, `->`, `>>`, `<<` matched via switch instead of 7 separate if-blocks
- **Single-char operator matching → `switch`** (`stdlib/lexer.nv:248-272`): 22 operator characters (+, -, *, /, %, =, &, |, ^, ~, <, >, (, ), {, }, [, ], ,, :, ., ;) matched via switch
- **`parse_primary` → `elif` chain** (`stdlib/parser.nv:57-274`): Flattened deeply nested `} else { if ... }` pyramid spanning 200+ lines into clean flat `if/elif/else` chain. Every token type (NUMBER, STRING, TRUE, FALSE, LBRACK, LBRACE, LEN, STR, SIZEOF, OPENF, READ, WRITE, CLOSE, ALLOC, FREE, IDENT, LPAREN, SELF, RBRACE, COMMA) has its own elif branch
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

### Code Quality Fixes (This Session — June 2026)
- **`_sys_write_raw` byte loop → `_fwrite`** (`codegen_x86.py:1555-1623`, `codegen.nv:469-537`): Replaced per-byte `_fputc` loop (150K calls for typical output) with buffer allocation + single `_fwrite` call. Allocates `malloc(length)` buffer, copies all bytes from list into buffer, calls `_fwrite(buf, 1, length, stream)`, then frees buffer. Eliminates 149,999 unnecessary function calls per output file.
- **`_call_string_builtin` if-chain → dict dispatch** (`vm/machine.py:69-114`): Replaced 9 `if func_name == "..."` blocks with dict dispatch (`_STRING_HANDLERS`), each handler defined as a standalone module-level function. O(1) dispatch instead of O(n) linear scan.
- **`peephole.py` removed** (`compiler/peephole.py`): Dead file — nothing imported it. Codegen has its own inline `peephole()` method.
- **`compiler.nv` line-reading/writing dedup** (`stdlib/compiler.nv`): Extracted `write_lines(lines, path)` and `read_lines(path)` helper functions. Eliminated 4 copies of asm-write loop and 2 copies of file-reading + line-splitting logic. `compile_to_file`, `compile_to_exe`, `compile_to_bare`, `assemble_bare_file`, `assemble_link_file` all simplified.
- **Lexer O(n²) string building fixed** (`stdlib/lexer.nv:185-213`): Replaced char-by-char concatenation in string literal parsing with `str_sub(src, start, i)` — O(n) instead of O(n²).
- **Double-negative offset bug** (`codegen_x86.py:1812,1858`, `codegen.nv:710,756`): `mov eax, [ebp - -12]` → `mov eax, [ebp + 12]`. Root cause: variable store in Python codegen didn't handle negative offsets.
- **Dead epilogue blocks removed** (`codegen_x86.py:4284-4440`): 17 dead `pop/pop/mov/pop/ret` sequences eliminated from `_emit_win32_runtime`.
- **`_is_string_expr()` heuristics cleaned** (`codegen_x86.py:144,146`): Removed hardcoded variable name list (15 names) and field name list (15 names). Now relies solely on `inferred_type` and `struct_defs`.
- **`string_vars` init fixed** (`codegen_x86.py:__init__`): Moved `self.string_vars = set()` to `__init__`, removed all `getattr(self, 'string_vars', set())` fallback patterns.
- **Debug print removed** (`codegen_x86.py:get_prop_offset`): Removed `print(f"  REG: {name} -> offset {self.prop_offsets[name]}")`.
- **Compiler.nv dedup**: 216→170 lines (21% reduction). Total diff: 176 insertions, 368 deletions across 7 files.

### Installer PATH Fix (Previous Session)
- **Root cause**: `_add_to_path_windows()` wrote PATH to registry + broadcast `WM_SETTINGCHANGE`, but child processes inherit the parent's environment block — they never re-read the registry. So `nova`/`galaxy` remained unavailable even in new terminal tabs until Explorer itself restarted.
- **`install.py` fix**: After writing registry PATH, also updates `os.environ["PATH"]` so child processes of the installer see the change immediately.
- **`use_nova.bat` helper**: New batch file in both `install.py` and `install.ps1` that prepends `%~dp0` to the current cmd.exe session's PATH. Created alongside `nova.bat`/`galaxy.bat`.
- **Output improvement**: Both installers now print one-liners for immediate PATH refresh:
  - cmd.exe: `call "%LOCALAPPDATA%\nova\use_nova.bat"`
  - PowerShell: `$env:PATH = "$env:LOCALAPPDATA\nova;$env:PATH"`
- **Test fix**: `test_launcher_execution_simulated` updated to skip `use_nova.bat` (helper script, not a python launcher).
- **Registry cleanup**: Stale unit-test PATH entries (9 `nova-test-*` dirs) cleaned from registry.
- **Website docs updated**: reference.html (enums, switch, dict, hex/bin, string interp, stringlib table) + examples.html (5 new examples). Committed + pushed to both repos on June 7, 2026.

## Commands Reference
```powershell
# One-command install
curl -O https://galaxy-registry.vercel.app/install.sh && bash install.sh

# Use immediately without restarting terminal (Windows)
call "%LOCALAPPDATA%\nova\use_nova.bat"    # cmd.exe
$env:PATH = "$env:LOCALAPPDATA\nova;$env:PATH"   # PowerShell

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
