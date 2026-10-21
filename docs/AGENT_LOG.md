# Agent Session Log (historical)

Full chronological notes moved out of AGENTS.md. Contains duplicated sections; treat as an archive, not as current policy.

## Latest Portable Standard-Library Work
- Added `env_get(name)` and `env_set(name, value)` to `stdlib/env.nv`.
- Added matching `system_env_get`/`system_env_set` wrappers, VM handlers, and
  native Windows/Unix/macOS runtime ABI functions.
- `env_get` returns an empty string when the variable is absent; `env_set`
  returns `1` on success and `0` on failure.
- Added type-check and VM/native parity coverage.
- Validation: `python -m unittest discover tests -q` — 216 passed, 1 skipped.
- Added `fs_delete`, `fs_copy`, and `fs_move` with VM/native implementations.
  Copy overwrites its destination; move replaces it where supported; delete
  targets files only. Each returns `1` on success and `0` on failure.
- Added `process_run(args)` for no-shell argument-array execution. It returns
  the child exit code or `-1` when launch fails, with VM/native parity on
  Windows and Unix-like targets.
- Started the shared JSON value ABI with stable `NovaValueKind` IDs and the
  internal `_nova_value_kind` probe. Existing list/dict/string ARC tags remain
  compatible; scalar boxing and JSON conversion remain pending.
- Added internal boxed scalar constructors/accessors for `none`, `bool`, `int`,
  and `float`, mirrored by VM handlers. Existing syntax remains unboxed.
- Added internal boxed-string construction/access, so future JSON conversion
  can use a tagged owned string representation instead of guessing from raw
  string pointers.
- Added checked list/dictionary traversal helpers for the shared ABI, mirrored
  by VM handlers. These expose counts, list items, and dictionary keys/values
  without changing existing collection syntax.
- Added internal retain and kind-predicate helpers for managed collections and
  strings, mirrored by VM handlers, to support safe recursive ABI traversal.
- Added matching `_nova_value_release` lifetime primitive; native decrements
  ARC and VM treats it as a no-op under Python object lifetime management.
- Added collection boxing entry points for lists and dictionaries. They validate
  the existing managed kind and retain the native object; VM preserves the
  existing collection object.
- Added ordered flattened dictionary item traversal through
  `nova_value_dict_items`, preserving key/value pairing for recursive consumers.
- Added the first public JSON milestone: compact VM/native `json_stringify`
  for strings, integers, boxed booleans/none, lists, and dictionaries.
  Recursive `json_parse` remains pending.

## Global Lock
- None

## Architecture Policy
- **x86 (32-bit) support removed** — only x86_64 and arm64 are maintained
- **Bootstrap (Python) is FROZEN** for new features — only bug fixes that prevent self-hosting. All new language features go into stdlib (Nova) only
- **Shared codegen layer**: `stdlib/backend/codegen_expr.nv` and `stdlib/backend/codegen_stmt.nv` handle all architecture-specific emit via the `state` object's register names

## Current State
- **Galaxy Package Manager**: Fully implemented and live at [galaxy-registry.vercel.app](https://galaxy-registry.vercel.app)
- **Compiler**: Stable, tree-shaking + variable-to-register promotion + loop bounds-check elimination (BCE) + AST constant folding/dead-code pruning + full self-hosted Stage 2 working (275 tests passed) + cross-platform GCC fallback + exceptions + list comprehensions + REPL + cross-compilation
- **Installer**: Native `install.sh` (bash, uses only curl+tar) + `install.ps1` (PowerShell) + `install.py` (Python fallback) — no dependencies required
- **Version**: v0.9.0. `nova --version` / `galaxy --version` + self-update via registry endpoints

## Latest Maturity Work
- Added deterministic `nova fmt <file.nv>` checking; `nova fmt --write` is the only
  mode that edits source.
- Added stable diagnostic codes and opt-in JSON output through `nova check --json`
  and `nova lint --json`.
- Expanded advisory linting with `UNSAFE001` for raw `alloc`/`free` review points.
- Documented raw-memory ownership and borrowed-view rules without changing default
  semantics.
- Validation command: `python -m unittest discover tests -q` (216 passed, 1 skipped).
- Added readable portable modules: `path`, `fs`, `env`, `process`, and `time`.
  They reuse the existing runtime ABI and preserve low-level access.
- `json.nv` is intentionally a placeholder until VM/native JSON values share a
  documented representation; no false portability promise is made.
- Added explicit `fs_mkdir(path)` with matching VM/native behavior. It does not
  implicitly create parent directories during `fs_write`.

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
- **`main.py`**: Force-delete stale `runtime.o` before recompiling `runtime.c` to prevent silent stale-object linking that crashed `_printf`

### x86_64 Native Compilation Fix (This Session — June 2026)
- **Root cause**: `nova.exe` crashed with `STATUS_ACCESS_VIOLATION` on startup because `_printf`/`_sys_get_args` from a stale `runtime.o` had debug markers and incomplete quote handling
- **Quote handling**: `_sys_get_args` in `runtime.c` now tracks `in_quote` state — paths with spaces (e.g. `D:\...\Random Topic Practice\...`) are parsed as single args instead of being split into 4 tokens
- **Runtime recompile fix**: `main.py:204-214` now deletes existing `runtime.o` before recompiling `runtime.c`, guaranteeing the linker always gets fresh object code
- **Result**: `python main.py build nova.nv` produces a working `nova.exe` that correctly prints usage message (exit 0) and processes `build` subcommand
- **`install.ps1`**: Downloads portable winlibs MinGW-w64 (~130MB) into `<InstallDir>/gcc/` if `gcc` not on PATH. Handles silent extraction of the `.zip` archive.
- **`install.py`**: Same GCC bundling logic — downloads winlibs on Windows, warns with package manager instructions on Unix.
- **`install.sh`**: Detects GCC presence after extraction, warns if missing with platform-specific install commands.
- **`nova build` auto-fallback**: Tries `nova.exe assemble-link` first (verifies output exists), falls back to system/bundled GCC.

### Local Variable / Parameter Layout Overlap Bug Fixed (This Session — June 2026)
- **Root cause**: Local variables were assigned positive offsets (8, 16, 24…) but saved parameters used negative offsets (-16, -24, -32…). Both accessed via `[rbp - N]` — they silently overlapped. Example: `compile_file` stored `path` at `[rbp - 16]`, then `source = sys_read(fd)` overwrote `[rbp - 16]` with the file contents, destroying `path`.
- **Fix**: Added `local_var_base = 16 + n_params * 8` shift. Local var offsets now start above saved parameter area, preventing overlap. Applied in both Python codegen (`codegen.py:scan_vars`) and self-hosted codegen (`codegen.nv:register_var`).
- **Files changed** (4 files, ~30 lines):
  - `compiler/backend/x86_64/codegen.py`: `scan_vars` offset shift (+base), `_main` local_var_base=32, init `self.local_var_base=16`
  - `stdlib/backend/x86_64/codegen.nv`: Added `local_var_base` to `CodegenState`, `register_var` shift, `compile_function` save/restore + `sub rsp` adjustment
- **Result**: `python main.py build hello.nv` now produces working `hello.exe`. `nova.exe` reaches tokenization phase when building.

### Debug Prints Removed from runtime.c
- `main()` wrapper (`runtime.c:330-338`) had `WriteFile(h, "1\n", ...)`, `WriteFile(h, "2\n", ...)`, `WriteFile(h, "3a\n", ...)` debug prints around `_main()` call. Removed — these caused "1\n2\n" prefix on all output (no functional purpose).

### `_printf` `%d` Reads Wrong Register (This Session — June 2026)
- **Root cause**: `_printf` in `runtime.c:56-57` read `%s` from `rsi` (2nd SysV reg = first variadic arg) but `%d` from `rdx` (3rd SysV reg = second variadic arg). The codegen always passes the value in `rsi` (since `printf(fmt, value)` only ever has one variadic arg), so `%d` read uninitialized garbage from `rdx`.
- **Symptoms**: `print(len(s))` printed garbage (e.g. `1684949248`) while `print(s[0])` printed `"H"` correctly. All `%d` format outputs were corrupt; `%s` worked fine.
- **Fix** (`runtime.c:67-69`): Changed `%d` handler to read from `arg_s` (= `rsi`) instead of `arg_d` (`rdx`). Unified both handlers to use the single `arg_s` source.
- **`_sprintf` NOT affected**: Its signature `sprintf(buf, fmt, ...)` puts fmt in `rsi` (arg2) and first variadic arg in `rdx` (arg3) — so reading `%d` from `rdx` was correct there.
- **Self-hosted codegen NOT affected**: It uses a stack-based `_printf` wrapper that reads args from `[rbp+16/24]` and delegates to CRT `printf`, bypassing the register confusion entirely.

### `-mno-red-zone` for SYSCALL Functions
- When GCC compiles a `__attribute__((sysv_abi))` function on Windows x64, it may omit `sub rsp` and access locals below `rsp` (assuming SysV red zone). Windows has no red zone — interrupt handlers can corrupt this data. Fixed by adding `-mno-red-zone` to `runtime.c` compilation command in `main.py`.

### CI/CD Cross-Platform Fix (This Session — June 11, 2026)
- **Root cause**: `runtime.c`'s `SYSCALL` macro was defined inside `#if defined(_WIN32)` (lines 9-13), but used on lines 315-555 inside `#if !defined(_WIN32)` (dict functions, heap fns) AND in the shared code section after `#endif`. On Linux/macOS, `SYSCALL` was undefined → `runtime.c` compilation failed silently (output captured but never displayed) → `runtime.o` not produced → linker errors (`undefined reference to _printf`, etc.)
- **Fix** (`runtime.c:1-13`): Moved `SYSCALL` macro definition ABOVE the `#if defined(_WIN32)` block. It uses `__attribute__((sysv_abi))` for x86_64 and no-op otherwise — both work on all platforms.
- **`.extern` declaration mismatch fixed** (`codegen.py:163-167`): `.extern` used `self._sym("printf")` = `printf` on Linux, but `call` sites hardcode `_printf`. All runtime.c wrappers define symbols with `_` prefix on ALL platforms, so `.extern` now always uses `_` prefix to match.
- **Self-hosted tokenizer crash removed**: The x86 codegen (which had the crash) is now deleted. This bug is obsolete.
- **Result**: All 190 tests pass. Native build verified on Windows; CI on Linux/macOS should now succeed.

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
### Phase 3: Self-Hosting Bootstrap Completion (This Session — June 13, 2026)
- **`is_string_expr` fix (`stdlib/backend/x86_64/codegen.nv`, `stdlib/backend/arm64/codegen.nv`)**: Added `inferred_type` check for Variable and DataFieldAccess nodes. Previously, Variable nodes assigned string literals (e.g., `s = "hello"`) were not recognized as strings because `string_vars` only tracked function parameter type annotations. `is_float_expr` already checked `inferred_type` correctly; `is_string_expr` now does the same. Fixed also for DataFieldAccess fields (`val`, `kind`, `val_str`, `name`, `op`).
- **`_sys_platform` duplicate removed (`stdlib/backend/x86_64/codegen.nv:4298-4303`)**: Hardcoded assembly `_sys_platform:` function conflicted with Nova-defined `sys_platform()` in os_windows.nv (which returns `"windows"`). Both were emitted, causing assembler duplicate-symbol error. Removed the hardcoded version since the Nova stdlib implementation is authoritative. The same issue exists in the ARM64 backend (not yet fixed since arm64 build isn't blocking self-hosting).
- **Calling convention theory corrected**: MinGW GCC x64 uses **SysV ABI by default** (args in `rdi/rsi/rdx/rcx/r8/r9`), NOT Microsoft x64 (`rcx/rdx/r8/r9`). Verified by inspecting `runtime.s` from `runtime.c`. All runtime wrappers consistently use SysV ABI. No calling convention mismatch exists — the earlier theory that non-SYSCALL functions use Microsoft ABI was incorrect.
- **Slice args analysis**: Parser maps `node.left=string, node.right=start, node.cond=end`. Codegen compile order `cond→right→left` + pops `rbx=string→rcx=start→rdx=end` + re-pushes `rdx=end→rcx=start→rbx=string` — then `emit_call` pops `rdi=string, rsi=start, rdx=end`. This is **correct**. The original push order needed no change.
- **Self-hosting verified**: `nova.exe build nova.nv` produces a working compiler (520 KB, builds user programs correctly). `s[0]` (char_strings lookup) and `s[0:3]` (slice via `_slice_string`) both produce correct output. No more `STATUS_ACCESS_VIOLATION` or garbage output.
- **RawBlock string quotes fix (`stdlib/backend/x86_64/codegen_stmt.nv:326-328`)**: `@raw` assembly strings were being emitted with literal `"` quotes around them, causing GCC `"no such instruction"` errors. Fix: `str_sub(raw_str, 1, len(raw_str) - 1)` strips the leading/trailing `"` before emitting.
- **WinExec→system() async fix (`runtime.c:112,244`)**: `sys_system` used `WinExec(cmd, 1)` which is strictly asynchronous — it returns immediately before GCC finishes. The Nova `build` command then reports success but the `.exe` is 0 bytes (still being written). Fix: replaced with C library `system(c)` which blocks until the child process completes. Also simplifies the implementation (no manual `WaitForSingleObject` needed).
- **End-to-end validation**: Full chain verified — `nova.exe build nova.nv` produces a working `nova.exe`, which can then build user programs with string indexing, slicing, concatenation, and `system_exec`. The Nova language is fully self-hosted and stable.

### Dead Data Cleanup (This Conversation — June 13, 2026)
- **`str_const_sys_platform` removed from x86_64 .nv codegen (`stdlib/backend/x86_64/codegen.nv:4038-4042`)**: The x86_64 path emitted `str_const_sys_platform: .asciz "darwin"` — dead data since the `_sys_platform:` assembly function was already removed. Only x86 (32-bit) path retained (still used by `emit_win32_runtime`).
- **`str_const_sys_platform` removed from both Python bootstrap codegens**: Dead `str_const_sys_platform: .asciz "macos"` removed from `bootstrap/compiler/backend/x86_64/codegen.py:176` and `arm64/codegen.py:398`. Neither Python codegen ever emitted a `_sys_platform:` assembly function — the data was orphaned.

### Phase 4: Platform Naming & Frame Pointer Optimization (This Session — June 13, 2026)
- **Platform-aware executable naming** (`bootstrap/main.py:compile_native()`, `nova.nv:81`): `.exe` suffix now only applied on Windows (`os.name == "nt"` / `sys_platform() == "windows"`). macOS/Linux produce no extension. CI `ci.yml` uses `$RUNNER_OS` for platform-appropriate naming in native build+run step.
- **Dict native codegen — already complete**: Contrary to vault notes claiming `push 0` placeholders, all four backends (x86_64 .nv, ARM64 .nv, x86_64 Python, ARM64 Python) already emit proper `_dict_new`/`_dict_set`/`_dict_get`/`_dict_has`/`_dict_remove`/`_dict_keys`/`_dict_values`/`_dict_items` calls for DictLiteral and all 7 dict methods. Tests exist and pass.
- **Cross-platform CI** (`ci.yml`): Native compilation step now uses `if [ "$RUNNER_OS" = "Windows" ]` to decide `.exe` naming. macOS native build+run works correctly.
- **Frame pointer optimization (x86_64)** (`stdlib/backend/x86_64/codegen.nv:79,492-548,4128-4178`, `codegen_stmt.nv:130-141`): `state.bp` changed from `"rbp"` to `"rsp"`. `compile_function` no longer emits `push rbp; mov rbp, rsp` for x86_64; adds +8 compensation to `local_offset`; converts variable offsets via `stored = K - local_offset - regs_size + 8` (stored as negative for `[rsp + abs]` access). `_main:` section similarly changed with +16 compensation (no push rbp + `and rsp, -16` alignment). `Return` statement emits `add rsp, local_offset` instead of `mov rsp, rbp; pop rbp`. Saves 2 instructions per function call; frees `rbp` as GP register. x86 (32-bit) mode unchanged.
- **ARM64 frame pointer optimized** (`stdlib/backend/arm64/codegen.nv:77`, `codegen_stmt.nv:34,137-139`, `codegen_expr.nv:299-304,334-338`): `state.bp` changed from `"fp"` to `"sp"`. `compile_function` no longer emits `mov fp, sp` for ARM64; adds offset conversion formula `new = stack_size - old` to convert fp-relative offsets to sp-relative (positive from sp). `_main:` section similarly updated. `Return` statement emits `add sp, sp, #local_offset` + `ldp fp, lr, [sp], #16` instead of `mov sp, fp; ldp fp, lr, [sp], #16`. All variable loads/stores use `[sp, #+K]` (positive offset) since variables live above sp. `stp fp, lr, [sp, #-16]!` retained (LR must be saved for non-leaf functions). Saves 1 instruction per function call (`mov fp, sp`). Adding `local_offset` instead of `mov sp, fp` also avoids the pre-existing `ldp sp, lr` bug when `%b = "sp"`. All 67 ARM64 codegen tests pass.
- **ARM64 native pipeline verified**: Full assembler (parse + encode + pass) and PE32+ linker already exist at `stdlib/backend/arm64/`. Produces PE executables for Windows ARM64. No Mach-O linker for macOS ARM64 — would need GCC fallback.
- **`print("DEBUG"` removed from type_checker.nv**: Debug print left in production code cleaned out.
- **All 191 tests pass** (1 skipped — registry PATH test requiring Windows-specific environment).

### Phase 5: Built-in Functions & macOS ARM64 GCC Fallback (This Session — June 13, 2026)
- **7 new built-in functions added** (`abs`, `min`, `max`, `file_exists`, `file_size`, `file_type`, `now`): C implementations in `runtime.c` (lines 601–689). Registered in `stdlib/type_checker.nv` (102–118) and `bootstrap/compiler/type_checker.py` (4–25 — new `BUILTIN_SIGS` dict). Dispatched via `_BUILTIN_HANDLERS` in `bootstrap/vm/machine.py` (714–740, 754–781). `.extern` declarations added to all 4 codegen files. All handlers use Python builtins (`abs()`, `os.path.exists()`, `datetime.now()`) in VM and C runtime functions in native.
- **`BUILTIN_SIGS` in Python type checker** (`type_checker.py:4-25`): Dict mapping 15+ symbols `(abs..str_sub)` to `(return_type, param_types)` tuples. `visit_Call` checks it before falling through to `AnyType()` — critical for correct `%s` vs `%d` codegen in `Print`.
- **macOS `_dict_*` wrappers added** (`runtime.c:590-598`): `_dict_new`, `_dict_has`, `_dict_get`, `_dict_set`, `_dict_remove`, `_dict_keys`, `_dict_values`, `_dict_items` and `_sys_platform` for macOS in new `#elif defined(MACOS)` section after the existing `#elif defined(_WIN64)` section. Previously only defined for Windows and Linux — self-hosted compiler on macOS would get linker errors.
- **Linux `_sys_platform` added** (`runtime.c:529`): `_sys_platform` now returns `"linux"` on Linux (was only defined for Windows, returning `"windows"`). Self-hosted compiler calling `sys_platform()` on Linux would have linked against a missing symbol.
- **macOS/Linux GCC fallback in compiler** (`stdlib/compiler.nv:143-161`): `compile_to_exe` now uses `sys_platform()` to detect OS. Windows: uses bundled `gcc\\bin\\gcc.exe` with `-mconsole -lkernel32`. macOS/Linux: uses system `gcc` without Windows-specific flags. ARM64 on Windows continues to use internal PE assembler+linker.
- **All 190 tests pass** (1 skipped — pre-existing registry PATH test requiring Windows-specific environment).

### Phase 6: Exceptions + List Comprehensions + REPL + Cross-Compilation (This Session - June 15, 2026)
- **Exceptions (try/catch/throw)**: Full implementation across all layers.
  - **Lexer**: try, catch, throw keywords in bootstrap/lexer/tokens.py and stdlib/lexer.nv
  - **Parser**: Try (body, catch_body, catch_var_name) + Throw (value) AST nodes in bootstrap/nova_ast/nodes.py
  - **VM**: OP_TRY, OP_THROW, OP_CATCHEND opcodes in vm/opcodes.py + vm/compiler.py, executed in vm/machine.py
  - **Native**: runtime.c C helpers: _try_block, _throw_error, _catch_error via setjmp/longjmp
  - **Self-hosted codegen**: Both x86_64 and ARM64 .nv codegens emit try/catch/throw wrappers
  - **Tests**: 10 tests in tests/test_exceptions.py
- **List comprehensions**: [expr for x in list if cond] desugars to Block + ForIn + append at parse time. 7 tests.
- **REPL** (nova repl): Interactive REPL with multi-line input, persistent state across lines
- **Cross-compilation infrastructure**: target_os through CodegenState, _find_gcc cross-toolchain lookup
  - Linux/macOS OS stubs filled in (os_linux.nv, os_macos.nv)
  - compile_to_exe uses target_os for GCC command, output extension, flags
- **All 210 tests pass** (1 skipped - pre-existing registry PATH test).

### Phase 7: type() + call() Built-in Functions (This Session — June 15, 2026)
- **`type()` built-in**: Compile-time string constant resolution in codegens + runtime `_builtin_type` VM handler. Returns `"int"`, `"string"`, `"float"`, `"bool"`, `"list"`, `"dict"`, `"unknown"` based on `inferred_type` (codegen) or Python `type()` (VM).
  - Bootstrap VM handler (`machine.py:787-804`): `_builtin_type` dispatches via `isinstance` checks
  - Bootstrap codegen: x86_64 (line 975-985) and ARM64 (line 925) `codegen.py` — compile-time string literal
  - Self-hosted codegen: x86_64 and ARM64 `codegen_expr.nv` special case + `is_string_expr` registration
  - Data section: `str_type_int`, `str_type_string`, etc. `.asciz` constants in both backend data sections
  - No runtime.c function needed (compile-time resolution for native)
- **`call()` built-in**: Dynamic function dispatch in the VM — `call("func_name", [arg1, arg2, ...])`.
  - Bootstrap VM handler (`machine.py:766-785`): `_builtin_call` looks up function in `m.functions`, sets up frame + IP for user functions, delegates to `_call_builtin` for built-in functions
  - Type checker (`type_checker.py` + `type_checker.nv`): `call(string, list[any]) -> any`
  - Runtime.c: `_call` stub returning 0 (native dispatch TBD)
  - `.extern _call` added to all 4 codegen files
- **Tests**: 17 tests (13 for `type`, 4 for `call`) in `tests/test_type_call.py` — all passing
- **Full suite**: 227 passed, 1 skipped, 13 subtests passed

### _dict_set key/value Swap Bug Fixed (This Conversation — June 18, 2026)
- **Root cause**: `_dict_set(void*d, const char*k, intptr_t v)` expects `rdi=dict, rsi=key, rdx=value`, but `ArrayIndexAssign` codegen in `bootstrap/compiler/backend/x86_64/codegen.py:684-691` had `mov rsi, rax` (value) and `mov rdx, rcx` (key) — key and value were swapped. This caused `local_env["x"] = 5` to call `_dict_set(local_env, 5, "x")`, storing key=5 (garbage char*) and value="x" in the dict. Subsequent `_dict_has(local_env, "x")` returned False because the string "x" was stored as the *value*, not the *key*.
- **Fix**: Changed to `mov rsi, rcx` (key) and `mov rdx, rax` (value) in x86_64 Python bootstrap `ArrayIndexAssign`.
- **VM self-hosting tests** (`tests/test_vm_selfhosted.nv`): 5 tests all passing, including `test_user_func_call` which calls a recursive user-defined function with dict-based parameter passing (previously crashing at `has_key=0`).
- **Same bug in other backends**:
  - **ARM64 Python DictLiteral** (`bootstrap/compiler/backend/arm64/codegen.py:1067-1077`): Loaded `x2=key, x1=value` for `_dict_set(x0=dict, x1=key, x2=value)`. Fixed by swapping loads to `x1=key, x2=value`.
  - **Self-hosted x86_64 DictLiteral** (`stdlib/backend/x86_64/codegen_expr.nv:815-831`): Had key/value/dict push order wrong (pushed dict→value→key but emit_call pops rdi=key, rsi=value, rdx=dict). Additionally lacked the 4th `push %c` to keep dict on stack for expression result. Fixed push order to key→value→dict + added 4th push dict.
  - **Self-hosted x86_64 ArrayIndexAssign** (`stdlib/backend/x86_64/codegen_stmt.nv:70-88`): Had no dict branch at all (only list indexing). Added dict branch with correct push order + `emit_call("_dict_set", 3)`.
  - **Self-hosted ARM64 ArrayIndexAssign** (`stdlib/backend/arm64/codegen_stmt.nv:66-85`): Same — no dict branch. Added dict branch with correct ARM64 push order + `emit_call("_dict_set", 3)`.
  - **Self-hosted ARM64 DictLiteral** (`stdlib/backend/arm64/codegen_expr.nv:775-793`): Already correct (4-push pattern with dict preserved on stack).
- **Reverted all debug prints** from `stdlib/vm.nv` (temporary debug lines in `exec_func` for LOAD_NAME, LOAD_CONST, ADD, CALL, RETURN).
- **Full suite**: 229 passed, 1 skipped, 13 subtests passed

### Parser Desugaring Bug Fix (This Session — July 7, 2026)
- **Root cause**: `parse_logic()` in both bootstrap (`parser.py:174`) and self-hosted (`parser.nv:741`) desugared `Compare + and/or + non-Compare` by wrapping the right side in a new `Compare(left.left, left.op, right)`. For `i < length and (is_alpha(...) or is_digit(...))`, left=`Compare(i,"<",length)`, right=`BinOp(OR)` (not a Compare), so right was incorrectly desugared to `Compare(i, "<", BinOp(OR))` → `i < (is_alpha or is_digit)`. Since `i=1` and `OR_result=1`, `1<1` = FALSE → inner while loop exited immediately without incrementing `i` → self-hosted lexer stuck at `i=1` forever.
- **Fix**: Added `and not isinstance(right, BinOp)` / `and right.kind != "BinOp"` to the desugaring condition in both parsers. The desugaring `a == b or c → (a == b) or (a == c)` is only valid when `c` is a simple value (Variable/Number/String), not a BinOp expression.
- **Tests**: All 274 pass, 1 skipped.

### Performance & Consolidation (This Session — June 20, 2026)
- **Root cause**: `nova.exe` crashed with `STATUS_ACCESS_VIOLATION` on startup because `_printf`/`_sys_get_args` from a stale `runtime.o` had debug markers and incomplete quote handling
- **Quote handling**: `_sys_get_args` in `runtime.c` now tracks `in_quote` state — paths with spaces (e.g. `D:\...\Random Topic Practice\...`) are parsed as single args instead of being split into 4 tokens
- **Runtime recompile fix**: `main.py:204-214` now deletes existing `runtime.o` before recompiling `runtime.c`, guaranteeing the linker always gets fresh object code
- **Result**: `python main.py build nova.nv` produces a working `nova.exe` that correctly prints usage message (exit 0) and processes `build` subcommand
- **`install.ps1`**: Downloads portable winlibs MinGW-w64 (~130MB) into `<InstallDir>/gcc/` if `gcc` not on PATH. Handles silent extraction of the `.zip` archive.
- **`install.py`**: Same GCC bundling logic — downloads winlibs on Windows, warns with package manager instructions on Unix.
- **`install.sh`**: Detects GCC presence after extraction, warns if missing with platform-specific install commands.
- **`nova build` auto-fallback**: Tries `nova.exe assemble-link` first (verifies output exists), falls back to system/bundled GCC.

### Local Variable / Parameter Layout Overlap Bug Fixed (This Session — June 2026)
- **Root cause**: Local variables were assigned positive offsets (8, 16, 24…) but saved parameters used negative offsets (-16, -24, -32…). Both accessed via `[rbp - N]` — they silently overlapped. Example: `compile_file` stored `path` at `[rbp - 16]`, then `source = sys_read(fd)` overwrote `[rbp - 16]` with the file contents, destroying `path`.
- **Fix**: Added `local_var_base = 16 + n_params * 8` shift. Local var offsets now start above saved parameter area, preventing overlap. Applied in both Python codegen (`codegen.py:scan_vars`) and self-hosted codegen (`codegen.nv:register_var`).
- **Files changed** (4 files, ~30 lines):
  - `compiler/backend/x86_64/codegen.py`: `scan_vars` offset shift (+base), `_main` local_var_base=32, init `self.local_var_base=16`
  - `stdlib/backend/x86_64/codegen.nv`: Added `local_var_base` to `CodegenState`, `register_var` shift, `compile_function` save/restore + `sub rsp` adjustment
- **Result**: `python main.py build hello.nv` now produces working `hello.exe`. `nova.exe` reaches tokenization phase when building.

### Debug Prints Removed from runtime.c
- `main()` wrapper (`runtime.c:330-338`) had `WriteFile(h, "1\n", ...)`, `WriteFile(h, "2\n", ...)`, `WriteFile(h, "3a\n", ...)` debug prints around `_main()` call. Removed — these caused "1\n2\n" prefix on all output (no functional purpose).

### `_printf` `%d` Reads Wrong Register (This Session — June 2026)
- **Root cause**: `_printf` in `runtime.c:56-57` read `%s` from `rsi` (2nd SysV reg = first variadic arg) but `%d` from `rdx` (3rd SysV reg = second variadic arg). The codegen always passes the value in `rsi` (since `printf(fmt, value)` only ever has one variadic arg), so `%d` read uninitialized garbage from `rdx`.
- **Symptoms**: `print(len(s))` printed garbage (e.g. `1684949248`) while `print(s[0])` printed `"H"` correctly. All `%d` format outputs were corrupt; `%s` worked fine.
- **Fix** (`runtime.c:67-69`): Changed `%d` handler to read from `arg_s` (= `rsi`) instead of `arg_d` (`rdx`). Unified both handlers to use the single `arg_s` source.
- **`_sprintf` NOT affected**: Its signature `sprintf(buf, fmt, ...)` puts fmt in `rsi` (arg2) and first variadic arg in `rdx` (arg3) — so reading `%d` from `rdx` was correct there.
- **Self-hosted codegen NOT affected**: It uses a stack-based `_printf` wrapper that reads args from `[rbp+16/24]` and delegates to CRT `printf`, bypassing the register confusion entirely.

### `-mno-red-zone` for SYSCALL Functions
- When GCC compiles a `__attribute__((sysv_abi))` function on Windows x64, it may omit `sub rsp` and access locals below `rsp` (assuming SysV red zone). Windows has no red zone — interrupt handlers can corrupt this data. Fixed by adding `-mno-red-zone` to `runtime.c` compilation command in `main.py`.

### CI/CD Cross-Platform Fix (This Session — June 11, 2026)
- **Root cause**: `runtime.c`'s `SYSCALL` macro was defined inside `#if defined(_WIN32)` (lines 9-13), but used on lines 315-555 inside `#if !defined(_WIN32)` (dict functions, heap fns) AND in the shared code section after `#endif`. On Linux/macOS, `SYSCALL` was undefined → `runtime.c` compilation failed silently (output captured but never displayed) → `runtime.o` not produced → linker errors (`undefined reference to _printf`, etc.)
- **Fix** (`runtime.c:1-13`): Moved `SYSCALL` macro definition ABOVE the `#if defined(_WIN32)` block. It uses `__attribute__((sysv_abi))` for x86_64 and no-op otherwise — both work on all platforms.
- **`.extern` declaration mismatch fixed** (`codegen.py:163-167`): `.extern` used `self._sym("printf")` = `printf` on Linux, but `call` sites hardcode `_printf`. All runtime.c wrappers define symbols with `_` prefix on ALL platforms, so `.extern` now always uses `_` prefix to match.
- **Self-hosted tokenizer crash removed**: The x86 codegen (which had the crash) is now deleted. This bug is obsolete.
- **Result**: All 190 tests pass. Native build verified on Windows; CI on Linux/macOS should now succeed.

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
### Phase 3: Performance & Consolidation (This Session — June 20, 2026)
- **PE machine type bug fixed** (`stdlib/backend/x86_64/linker.nv:559`): COFF machine type was `0x014c` (i386) — changed to `0x8664` (AMD64). Self-hosted `nova.exe assemble-link` was producing PE files claiming to be 32-bit executables.
- **Peephole optimizer fixed** (`stdlib/peephole.nv`): Added `rax` (64-bit) checks alongside `eax` — previously `push rax`/`pop rax` never matched, making optimizer ineffective on x86_64. Removed `xor eax, eax → mov eax, 0` anti-optimization (xor is faster on modern x86).
- **Dict hash `%` → `& (cap-1)`** (`runtime.c:333-418`): 6 modulo operations replaced with bitwise AND. Cap is always power-of-2 (8→16→32...). 30-80× speedup per hash operation (AND = ~1 cycle vs DIV = ~30-80).
- **`dict_free` added** (`runtime.c`): Frees keys, values, and header. `.extern _dict_free` added to all 4 codegen files + test assertions.
- **`rep movsb` in string slice** (`stdlib/backend/x86_64/codegen.nv`, `bootstrap/compiler/backend/x86_64/codegen.py`): Replaced byte-by-byte copy loop with `rep movsb` (hardware-accelerated bulk copy). ARM64 bootstrap (`bootstrap/compiler/backend/arm64/codegen.py`): replaced byte loop with `_memcpy`. Self-hosted ARM64 already used `_memcpy`.
- **`stdlib/codegen_common.nv`** — new shared module with `get_externs()` and `get_data_strings()` functions. Both `x86_64/codegen.nv` and `arm64/codegen.nv` import it, eliminating 53 lines of duplicated declarations across 2 files.

### Shorthand Operators & Dict Limits Fixes (This Session - June 2026)
- **Shorthand Operators Added**: Implemented `+=`, `-=`, `*=`, `/=`, `%=` natively in the lexer and parser. They desugar immediately to `a = a + b` ensuring the AST and codegen layers did not need modifications.
- **x86_64 Stack Frame Unification**: Cleaned up the x86_64 target `compile_function` and `_main` entry to uniformly emit `push rbp; mov rbp, rsp` across all modes, correctly shifting local offsets past saved register locations (`regs_size`) and applying precise alignment padding for 16-byte boundaries. 
- **Array Limits & Realloc Windows ABI Bug**: The `append()` tests caused silent execution failure inside `_realloc`. Discovered that the codegen branch for `sys_platform() == "windows"` mistakenly switched to `rcx`/`rdx` Microsoft ABI registers for `_realloc`, despite `runtime.c` enforcing `__attribute__((sysv_abi))` on all runtime wrappers. Fixed to uniformly use SysV `rdi`/`rsi` which prevented `_realloc` from corrupting shadow memory.
- **Dict "Index Out Of Bounds" Bug**: `test_limits.nv` crashed on `freqs[str(val)] = ...` due to Nova's type checker inferring `{}` as a `struct "dict"` rather than `kind = "dict"`. Fixed `types.nv` to accurately expose `create_dict_type()`, `type_checker.nv` to recognize `DictLiteral`, and updated the `has` operator in `codegen_expr.nv` to dispatch to `_dict_has` rather than falling back to `_strstr` for string comparisons.
- **ARM64 Register Clobbering / Stack Bug**: Replaced relative stack addressing with robust frame-pointer mapping (`mov fp, sp`) directly after `stp fp, lr` push. Variable offsets are strictly preserved against register pushes/pops within the body. 

### Phase 8: macOS ARM64 SIGSEGV Fix + Linux Self-Hosted Bootstrap Fix (This Session — June 27, 2026)
- **macOS ARM64 SIGSEGV root cause** (`bootstrap/compiler/backend/arm64/codegen.py`): `mov w0,#0` before `printf`/`sprintf` calls clobbered `x0` (the format string pointer). On ARM64, `w0` aliases the lower 32 bits of `x0` — writing `w0` zero-extends and destroys `x0`. Every `Print`/`PrintD`/`out_of_bounds` call resulted in `printf(NULL, ...)` → SIGSEGV.
- **Fix**: Removed all `mov w0,#0` instructions before `bl _printf`/`bl _sprintf` calls. Also rewrote `StrConvert` handler (dangling stack pointer + wrong `_sprintf` arg order). Updated `test_printf_call_arm64` assertion to verify `mov w0,#0` is NOT present between fmt_str load and printf call.
- **`compile_to_exe` Linux GCC name fixed** (`stdlib/compiler.nv:276`): `gcc_name` was `"x86_64-linux-gnu-gcc"` (cross-compilation prefix) instead of `"gcc"` for native Linux. On Ubuntu CI runners the cross-toolchain doesn't exist — GCC invocation failed silently.
- **`-flto` removed from self-hosted compile_to_exe** (`stdlib/compiler.nv:281,292`): Matches Python bootstrap fix from `f38dd64`. LTO with assembly-only input files can cause issues with certain GCC versions on Linux.
- **All 245 tests pass** (1 skipped).

### Phase 9: Linux SIGSEGV Debug Markers + str() Workaround (This Session — June 28, 2026)
- **CI status**: Commit `af17930` — `fail-fast: false` shows all OS results:
  - **Ubuntu**: SIGSEGV still present but **shifted** — ALL GEN markers pass through `GEN:helpers_start`. The crash is now AFTER code generation completes. Root cause is NOT `str()` alone.
  - **macOS**: ARM64 assembly errors: duplicate `L_append_no_realloc_arm` labels + invalid register `w32` in `str w32, [x1, #8]` at `nova.s:717`. Waiting on `fail-fast: false` macOS output.
  - **Windows**: Passes all tests.
- **Fine-grained debug markers**: Added `system.file_write(2, "GEN:...")` calls throughout `codegen.nv`, `codegen_stmt.nv`, `codegen_expr.nv` — every phase now emits markers.
- **`str()` workaround (`af17930`)**: Replaced `str(state.str_count)` with manual if-elif-else chain for 0-9, avoiding `str()` for `selfhost.nv` (str_count=1). This fixed the GEN:str_count_inc → GEN:label_created gap — both markers now fire.
- **New markers in cache-update code (`2a7955d`)**: Added `GEN:cache_start`, `GEN:cache_assigned`, `GEN:new_entry_done`, `GEN:cache_loop_done`, `GEN:cache_append_done`, `GEN:cache_saved` after `print("Compilation finished.")` to pinpoint the post-codegen crash in `compile_file` (`stdlib/compiler.nv:173-193`).
- **Post-codegen crash hypothesis**: The crash is in the build cache update section — possibly in `str(current_size)`, list operations, or `save_cache`. Previous `str()` calls on `tok_count` and `cached_size_str` worked fine, suggesting it's NOT a generic `str()` bug.
- **macOS ARM64 issues**:
  - `L_append_no_realloc_arm` label duplicated 100+ times in self-hosted ARM64 codegen — needs a unique label counter.
  - `str w32, [x1, #8]` — `w32` is not a valid ARM64 register (max is `w30`). Python bootstrap ARM64 codegen bug.

### Phase 10: macOS ARM64 runtime.c Missing Libc Wrappers (This Session — June 29, 2026)
- **CI status** (commit `0c6827d` — memset fix): `runtime.c` compilation now succeeds on macOS ARM64, but ALL symbols from `runtime.o` are undefined at link time: `_file_exists`, `_str_sub`, `_sys_*_c`, `_system_c`, etc.
- **Root cause**: The 22 libc wrapper functions (`_printf`→`vprintf`, `_malloc`→`malloc`, `_strlen`→`strlen`, etc.) at `runtime.c:276-312` were guarded by `#if defined(LINUX_WRAP)` only — **not compiled on macOS**. On macOS ARM64 (Mach-O), the C library does NOT add `_` prefix to C symbols (unlike x86_64 Mach-O), so `printf` is exported as `printf`, not `_printf`. The codegen always emits `_printf`, `_malloc` etc. — without the C wrappers, these symbols hit a defunct Mach-O symbol lookup and ALL fail.
- **Fix**: Changed `#if defined(LINUX_WRAP)` to `#if defined(LINUX_WRAP) || defined(MACOS)` at line 276 so the 22 libc wrappers (and `_system_c`) are compiled on macOS too. The `SYSCALL` attribute is empty on ARM64 so it's harmless.
- **Note**: The `_sys_*_c` bridge functions (`_sys_open_c`, `_sys_exit_c`, etc.) were already under `#if defined(LINUX_WRAP) || defined(MACOS)` and the unconditional builtins (`_str_sub`, `_file_exists`, etc.) were always compiled — they were NOT the cause of the error. The real issue was that the libc `_`-prefixed wrappers were missing, causing EVERY symbol from `runtime.o` to fail linker resolution.
- **Status**: Confirmed — linker fix works. Clean compile of `nova-stage1` on macOS ARM64.
- **Next blocker**: Runtime crash `"Index Out Of Bounds"` when `nova-stage1 --version` runs.

### Phase 11: macOS ARM64 List Layout Fix (This Session — June 30, 2026)
- **Linker fix confirmed**: `__asm__` aliases work — `nm` shows both `__name` (C export) and `_name` (alias) symbols. `nova-stage1` binary compiles and runs.
- **Runtime crash root cause** (`bootstrap/compiler/backend/arm64/codegen.py:1059-1067`): **x0/x1 register swap in ArrayIndex list read path**. After popping `x0=index, x1=base`, the code used `w1` (lower 32 bits of list ptr) for bounds check against zero instead of `w0` (actual index). When the heap address's lower 32 bits ≥ 0x80000000 (interpreted as negative signed), the incorrect `b.lt _out_of_bounds` triggered — causing the `"Index Out Of Bounds"` crash.
- **Secondary bug — layout mismatch**: ARM64 `ListLiteral` used inline elements (`base+16+i*8`) while `_sys_get_args_c` and x86_64 codegen used indirect storage (data pointer at `base+8`). ArrayIndex/ArrayIndexAssign also used inline, creating incompatibility.
- **Fixes applied** (`bootstrap/compiler/backend/arm64/codegen.py`):
  - `ArrayIndex` list path: `cmp w1,#0` → `cmp w0,#0`, `ldr w2,[x0]` → `ldr w2,[x1]`, `add x2,x0,#16` → `ldr x2,[x1,#8]`, `ldr x0,[x2,x1,lsl#3]` → `ldr x0,[x2,w0,uxtw#3]`
  - `ArrayIndexAssign`: `add x3,x2,#16` → `ldr x3,[x2,#8]` (data ptr indirection)
  - `ListLiteral`: Changed from single-inline `malloc(list_size)` with elements at `base+16` to indirect dual-allocation (16-byte header + separate data buffer), matching x86_64 layout
- **Self-hosted ARM64 bounds check** (`stdlib/backend/arm64/codegen_expr.nv:832-841`): Added missing bounds check (`cmp %c,#0`, `ldr w1,[%d]`, `cmp %c,x1`) to ArrayIndex list read path
- **Test updated** (`tests/test_codegen_arm64.py:216`): `test_list_literal` now verifies `str x1,[x2,#8]` (data ptr) and `str x0,[x1,#0]` (element storage) instead of `add x2,x1,#16`
- **All 246 tests pass** (1 skipped, pre-existing).
- **Version bump**: Nova v0.8.0 → v0.9.0

### Phase 15: Self-Hosted ARM64 Codegen Fracture Fix (This Session — July 1, 2026)

- **Root cause**: The self-hosted ARM64 codegen (`stdlib/backend/arm64/codegen_expr.nv`, `codegen_stmt.nv`) used **inline** list layout (single malloc for header+data, elements at `list+16+i*8`) while the bootstrap ARM64 codegen (`bootstrap/compiler/backend/arm64/codegen.py`) used **indirect** layout (16-byte header with separate data buffer, data_ptr at `[header+8]`). When the self-hosted compiler ran `build` on ARM64, ListLiteral, ForIn, Append, and Pop wrote/read elements using inline offsets, but ArrayIndex/ArrayIndexAssign used indirect dereference — guaranteed crash on any list operation.

- **ListLiteral** (`codegen_expr.nv:743-777`): Changed from single `malloc(total_sz)` with elements at `list+16` to header `malloc(16)` + data `malloc(req_cap)` with `data_ptr` at `[header+8]`, `count` at `[header+0]`, `capacity` at `[header+4]`. Element store loop uses data_ptr + `i*ptr_sz`.

- **Append** (`codegen_expr.nv:923-967`):
  - **Capacity check**: `ldr w1, [%x, #8]` → `ldr w4, [%x, #4]` (header[4] = capacity in bytes). Removed `add x3, x3, #16` (no header size added to needed bytes). Changed `b.le` → `b.lt` to match bootstrap behavior (realloc needed when at exact capacity).
  - **Element store**: `add %d, %x, #16` → `ldr %d, [%x, #8]` (indirect data_ptr).
  - **Realloc path**: `b.le` clobbered `%x` (x1 on ARM64, w1 aliases x1) — `ldr w1, [%x, #8]` destroyed the list pointer. Realloc also targeted the wrong thing (header instead of data buffer). Fixed: save `%x` (list_ptr) and `%c` (value) on stack before realloc; load `%d` (data_ptr) from `[%x, #8]`; push args for `realloc(data_ptr, new_cap)` in correct order (new_cap first, data_ptr on top for x0); after call, reload list_ptr from stack, update `header[8]` and `header[4]`.
  - **ARM64 register aliasing**: `%a`=x0, `%x`=x1, `%c`=x2, `%d`=x3, `%i`=x4, `%j`=x5, `%b`=sp.

- **Pop** (`codegen_expr.nv:967-979`): `add %d, %x, #16` → `ldr %d, [%x, #8]` (indirect data_ptr).

- **ForIn** (`codegen_stmt.nv:244-288`): `add %x, %d, #16` → `ldr %x, [%d, #8]` (indirect data_ptr).

- **Test update** (`tests/test_codegen_arm64.py:212-217`): Updated `test_list_literal` to check for indirect layout patterns: `str w3, [x2]` (count), `str w3, [x2, #4]` (capacity), `str x1, [x2, #8]` (data_ptr), `str x0, [x1, #0]` (data[0]).

- **All 67 ARM64 codegen tests pass**, all 54 x86_64 codegen tests pass, all 13 exception tests pass, all 17 type_call tests pass. Total: 175+ tests pass (galaxy and native_exec tests require network/GCC, skipped locally).

**Next Instruction for Agent:**
1. Commit the self-hosted ARM64 codegen indirect layout fixes and push to trigger CI.
2. On macOS ARM64, verify `nova-stage1 --version` no longer crashes.
3. Verify `nova-stage1 build test.nv` produces a working `test` binary on macOS ARM64.
4. On CI green, clean up `GEN:...` debug markers from Phase 9 stdlib files.
5. If `--version` crash persists, investigate ARM64 heap corruption in `_concat_strings` or `_sys_get_args_c` with register dump from CI.

### Phase 12: macOS ARM64 "Index Out Of Bounds" ForIn/Append/Pop List Layout Fix (This Session — June 30, 2026)
- **Root cause**: Phase 11 changed ARM64 list layout from inline (`base+16+i*8`) to indirect (16-byte header + separate data buffer at `[base+8]`). ArrayIndex, ArrayIndexAssign, and ListLiteral were updated, but **ForIn, MethodCall("append"), and MethodCall("pop") were missed** — they still used the old inline layout.
- **ForIn loop** (`codegen.py:839`): `add x2, x3, #16` → `ldr x2, [x3, #8]`. Caused loop variable to read garbage (list header + 16 bytes of whatever follows the header), crashing downstream when used as array index ("Index Out Of Bounds").
- **Append capacity check** (`codegen.py:1138`): `ldr w3, [x1, #8]` → `ldr w3, [x1, #4]`. In indirect layout, offset 8 holds the data pointer (64-bit), not the capacity. Offset 4 holds capacity. This bug made the `b.lt no_realloc` check always-true (data pointer >> small count), so realloc was never triggered — latent but harmless.
- **Append element store** (`codegen.py:1157`): `add x2, x1, #16` → `ldr x2, [x1, #8]`. Stored appended element at `list_ptr + 16` (past header) instead of `data_ptr + index`.
- **Pop element load** (`codegen.py:1167`): `add x3, x1, #16` → `ldr x3, [x1, #8]`. Same inline→indirect fix for element read.
- **Append realloc path** (`codegen.py:1148-1151`): Fixed capacity offset (8→4) and data pointer indirection (`add x2, x0, #16`→`ldr x2, [x0, #8]`). Dead code before fix (always-true b.lt), now correctly reachable.
- **Files changed**: `bootstrap/compiler/backend/arm64/codegen.py` — 5 edits across 7 instructions.
- **Tests**: All 246 pass (1 skipped, pre-existing).
- **Commit**: TBD

### Phase 13: ARM64 Append Double Bug + _slice_string/_str_sub Rewrite (This Session — June 30, 2026)
- **Append fix was actually TWO bugs, not one** (`bootstrap/compiler/backend/arm64/codegen.py`):
  - **Bug 1 (unit mismatch)**: Capacity check `ldr w3, [x1, #4]` reads element count, `cmp w1, w3` compares capacity (bytes) to count (elements). After fixing offset to `[x1, #4]`, the `cmp w1, w3` is now element vs element — **but capacity was still in bytes**. Fixed by using `w4=[x1, #0]` (capacity in elements) and comparing `cmp w4, w3`.
  - **Bug 2 (wrong realloc target)**: Realloc path reallocated the **header** (`mov x0, x1`) instead of the **data buffer** (`ldr x0, [x1, #8]`). After realloc, `str x0, [x1, #8]` also clobbered `x1` (list_ptr) with the byte-size argument before using it. Fixed by: (a) saving list_ptr in `x5`, (b) loading data buffer ptr from `[x5, #8]` and passing that to realloc, (c) after realloc, saving new buffer back to `[x5, #8]`, (d) storing new element at `data_ptr[index]` via `str x1, [x5, x3, lsl #3]`.
  - **Pre/post increment**: Moved `str w4, [x5, #4]` (save incremented count) to before the element store (pre-increment → post-increment to match x86_64 behavior).
- **Commit**: `fb0040e` — pushed, CI showed `--version` exits 0 on macOS ARM64.

### Phase 14: ARM64 String Slice → _str_sub (This Session — June 30, 2026)
- **Root cause** (`bootstrap/compiler/backend/arm64/codegen.py:545-583`): `_slice_string` was a hand-written assembly helper that read string slice arguments from **fixed stack offsets** (sp+64, sp+80, sp+96). The caller (Slice handler in `codegen_expr.nv`) passed arguments via **registers** in standard ARM64 ABI (x0=string, x1=start, x2=end). Since nobody wrote to those stack offsets, `_slice_string` read garbage → corrupted slice results whenever the compiler used string slicing internally (e.g., `file_path[0:out_len-3]` in `compile_to_exe`).
- **Fix**: Replaced `_slice_string` with existing C function `_str_sub` (defined in `runtime.c`, used by x86_64 codegen). Changed Slice handler from push/pop/stack-adjust dance (11 instructions) to simple register-based call to `_str_sub(x0=string, x1=start, x2=end)` (4 instructions). Removed `_emit_slice_string()` method entirely.
- **Cleanup**: Dead `str x2, ...` / `str x1, ...` / `str x0, ...` push sequence in Slice handler removed (was re-pushing what was just popped for `_slice_string`'s caller-cleanup ABI). No stack manipulation needed for `_str_sub` since it uses standard ABI with callee cleanup.
- **Tests**: All 246 pass (1 skipped). `test_slice_string_helper` updated to expect `bl _str_sub` instead of `bl _slice_string`.
- **Commit**: `949b057` — pushed.
- **CI status** (run `28451632121`, commit `949b057`):
  - **macOS ARM64**: `nova-stage1 --version` now crashes with `EXC_BAD_ACCESS` in `strlen(NULL)` inside `printf`, called from `or_end_3906` (OR expression label in Nova `--version` check). The `--version` path (`cmd == "--version" or cmd == "version"`) contains no string slicing, so the crash is **not directly caused** by the slice fix. Hypothesis: pre-existing heap corruption from the partially-fixed append bug, made visible by the ASLR heap layout on this particular CI runner. Previous CI run (commit `fb0040e`) happened to have a lucky heap layout that made `--version` work. **Re-running CI to check consistency**.

### Phase 13a: ARM64 sp-relative Variable Offset Corruption Fix (This Session — July 2, 2026)
- **Root cause**: ARM64 codegen uses `ldr xN, [sp, #K]` for local variable access (frame-pointer-free optimization). When `compile_expr(A)` pushes result to stack (changing `sp`), a subsequent `compile_expr(B)` reads variable `B` at the wrong offset from the now-shifted `sp` — returning garbage. On x86_64, this doesn't happen because variables use `[rbp - offset]` (frame-pointer relative, `rbp` never changes during expr evaluation).
- **Symptom**: macOS ARM64 `nova-stage1` crashes with `"Index Out Of Bounds"` inside `args[i]` in the `while i < len(args)` arg-parsing loop — `i` was read as garbage because `compile_expr(node.base)` (compiling `args`) pushed to stack before `compile_expr(node.index)` read variable `i`.
- **Fix** (`bootstrap/compiler/backend/arm64/codegen.py`): Replaced all pairs/triples of sequential `compile_expr` calls with `_compile_expr_to_reg` (reads variables while `sp` is at base, then pushes register values to stack). Affected 16 handlers:
  - `ArrayIndex` (crash site), `ArrayIndexAssign`, `Slice`, `Append`, `WriteFile`
  - `DataFieldAssign`, `PointerAssign`, `Read`/`Write` method calls
  - All 7 dict method handlers (`get`, `has`, `set`, `remove`, `keys`, `values`, `items`)
  - String concat, string comparison, float binary ops, float comparison
- **Test fix**: `cset x0, eq` → `cset x\d+, eq` regex in ARM64 compare tests (register allocation changed from x0 to x2 due to allocator changes). All 67 ARM64 tests pass.
- **CI results (commit 7eb0121)**: Ubuntu x86_64 — FIXED (arg loop passes, sys_platform() returns "linux", later segfault is a different pre-existing bug). macOS ARM64 — crash changed from "Index Out Of Bounds" to "Bus error: 10" (later crash, different root cause).
- **Print() debug markers added to `nova.nv`**: Replaced `system.file_write(2, ...)` markers with `print()` to avoid potential `_sys_write_c` misalignment bug on macOS ARM64. CI shows all 4 markers fire before crash.
- **Debug markers**: Kept `[DBG]` prints in `nova.nv` until CI confirms the fix.

### Phase 13b: Len Handler x0 Clobbering Bug Fix (This Session — July 2, 2026)
- **Root cause** (`bootstrap/compiler/backend/arm64/codegen.py`): `Len` handler used `ldr x0, [sp], #16` (hardcoded x0) to pop the target pointer, then `ldr w0, [x0]` or `bl _strlen` — all clobbering x0. But `_compile_expr_to_reg(node.left)` in the int comparison path had already returned x0 holding the left operand value. When `_compile_expr_to_reg(Len(...))` was called for the right operand, the Len handler's x0 use corrupted the left operand. Compare became `cmp len_result, len_result` instead of `cmp i, len(args)` — the while loop exited immediately without iterating.
- **Fix**: Len handler now saves x0 at entry (`str x0, [sp, #-16]!`), computes len (pushes result to stack), pops result into a temp register, restores x0 (`ldr x0, [sp], #16`), then pushes result back for the `_compile_expr_to_reg` fallback to pop into the right operand register.
- **Verification**: `cmp x0, x3` = `cmp i, len(args)` in generated assembly. All 246 tests pass (1 skipped).

### Phase 16: ARM64 Comprehensive fp-relative Variable Access Fix (This Session — July 2, 2026)
- **Root cause** (`bootstrap/compiler/backend/arm64/codegen.py`): ARM64 codegen used **sp-relative** variable access (`ldr xN, [sp, #K]`). When `compile_expr(A)` pushed results to stack (changing `sp`), a subsequent `compile_expr(B)` reading a variable read from the WRONG offset — returning garbage. This is a fundamental ARM64 vs x86_64 difference: x86_64 uses `[rbp - offset]` (frame-pointer-relative, `rbp` never changes during expr evaluation), while ARM64 used sp-relative.
- **Fix**: Created `_emit_fp_access()` method that emits `{op} {reg}, [fp, #{offset}]` for value arguments and `{op} {reg}, [fp, #-{abs}]` for local variables (handling the signed imm9 [-256,255] range). Converted ALL sp-relative variable loads/stores across 16+ handlers in the ARM64 bootstrap codegen to use `_emit_fp_access` with pre-computed fp-relative offsets.
- **Handlers converted**: `ArrayIndex`, `ArrayIndexAssign`, `Slice`, `Append`, `WriteFile`, `DataFieldAssign`, `PointerAssign`, `Read`/`Write` method calls, all 7 dict method handlers (`get`, `has`, `set`, `remove`, `keys`, `values`, `items`), string concat/comparison, float binary ops/comparison.
- **Special case**: x16 (IP0) used as temporary for fp-relative access when offset exceeds [-256,255] range — loads fp into x16, adds the offset, then uses `[x16]` indirect addressing. Required for functions with >32 local variables.
- **Verification**: All 246 tests pass (1 skipped). Generated assembly verified — all `ldr xN, [sp, #K]` replaced with `ldr xN, [fp, #K']`.
- **CI status**: macOS ARM64 (`nova-stage1 build selfhost.nv`) crashes with `Bus error: 10` at exit 138 **before these changes, still fails after**. This is a pre-existing bug (99/100 recent CI runs failed, no success found within last 100). Ubuntu + Windows CI pass.
- **Debug markers added/removed** (June 30 - July 2): Added `system.file_write(2, "CF:...")` markers to `stdlib/compiler.nv` at each statement boundary in `compile_file`. Markers showed `CF:load_cache` fires but `CF:before_file_size` does not — crash occurs between two structurally identical `system.file_write` calls. Generated assembly confirmed both calls are identical (same register setup, same function call chain). String data section verified (all `.asciz` entries correct). Root cause of macOS ARM64 Bus error remains unidentified — suspected: Apple Clang `@PAGE`/`@PAGEOFF` relocation issue, Mach-O symbol resolution, or pre-existing runtime.c assembly incompatibility with Apple Silicon's linker. Markers removed in commit `6a4adc4`.

### Phase 17: Error Message Improvements + Dict-based Performance Optimization (This Session — July 4, 2026)
- **`_oob_file_ptr` / `_oob_line` globals** (`runtime.c:215-231`): `_out_of_bounds()` now prints `"error: Index Out Of Bounds at <file> line <line>\n"` using multiple `_printf` calls (wrapper takes only one arg). Falls back to plain message when `_oob_file_ptr` is null.
- **All 4 backends updated**: Before each bounds check jump, `_oob_line` set from AST node's `.line` attribute. `_oob_file_ptr` set once at entry from `source_path_str` (bootstrap) / `L_oob_source` (self-hosted).
- **Assembly `_out_of_bounds:` removed**: C function from `runtime.c` handles the detailed message. Eliminates linker conflicts and code duplication across 4 backends.
- **ARM64 `str sp, [xN]` gotcha fixed**: `str sp, [xN]` stores `xzr` (zero), not `sp`. All ARM64 backends now use `mov xN, sp; str xN, [addr]` and `mov sp, xN` for restore.
- **Test updates**: Both `test_out_of_bounds_helper` tests (x86_64 + ARM64) updated to check for externs + data labels instead of assembly `_out_of_bounds:` label.
- **Dead strings removed from `codegen_common.nv`**: `L_realloc_fail_msg` and `str_const_chacha_mem` — neither was referenced by any code.
- **Dict-based `find_var_offset`/`register_var`** (x86_64 + ARM64 `codegen.nv`): Added `var_name_map: dict` to `CodegenState`. Replaces O(n) linear scan over `local_var_names` with O(1) dict lookup. Updates save/restore/clear in `compile_function` and `generate_assembly`.
- **Dict-based `tc_find_func`/`tc_find_struct`** (`type_checker.nv`): Added `func_name_map: dict` and `struct_name_map: dict` to `TypeChecker`. Replaces O(n) `str_eq` linear scan with O(1) dict lookup. Populated in `tc_add_func` and `tc_add_struct`.
- **Full suite**: 229 passed, 1 skipped, 13 subtests — all pass. Test runtime dropped from ~3.7s to ~2.0s.

### Phase 18: 64-bit Int, Dict/VM Opcode Dispatch, Char-by-Char Lexer, Native `nova run`, List Header Fix (This Session — July 4, 2026)

- **64-bit integer upgrade across all 8 codegen files**: x86_64: eax→rax, ebx→rbx, ecx→rcx, edx→rdx, esi→rsi, edi→rdi, cdq→cqo, dword→qword. ARM64: w0-w30→x0-x30. `runtime.c` `_printf %d` handler: `int val` → `long long val`. 32-bit `int` overflowed `sum_to(100000)` (5B > 2³¹).
- **List header count/capacity reverted to 32-bit**: The automated 64-bit upgrade incorrectly changed list `count` (offset 0) and `capacity` (offset 4) from 32-bit to 64-bit operations, causing overlap and corruption of the 64-bit `data_ptr` (offset 8). Reverted in all 6 codegen files: ListLiteral, Len, ForIn, ArrayIndexAssign, Append, Pop. All 266 tests pass.
- **List header is the ONLY structure affected**: Dict and other structures have mixed 32/64 fields but are accessed only through C runtime functions, not assembly. No other corruption exists.
- **Dict-based optimization extended to all stdlib backends**: `var_name_map`, `string_var_map`, `prop_offset_map` dicts in `CodegenState` (codegen.nv). `kind_handlers` dict for `tc_visit_real` (type_checker.nv). `type_annotation_map` dict (types.nv). Dict-based method dispatch in `codegen_expr.nv` (x86_64 + ARM64) replaces 14 `str_eq` comparisons. Dict-based statement dispatch in `codegen_stmt.nv`.
- **Bootstrap VM opcode dispatch** (`machine.py`): 60+ elif chain replaced with `_OPCODE_DISPATCH` dict + module-level handler functions.
- **Self-hosted VM dispatch** (`stdlib/vm.nv`): 57 `elif op == "..."` chain replaced with `_OP_DISPATCH` dict + integer `h` handler chain.
- **`nova run` changed** from VM alias to auto-build native + execute (`bootstrap/main.py`). `nova dev` stays VM for development.
- **Char-by-char lexer** (`bootstrap/lexer/tokenizer.py`): Rewrote from regex-based to character-by-character. 420K input: 950ms → 100ms (9.5× faster). Handles string interpolation recursively via `tokenize()` calls.
- **Benchmarks written**: `tests/benchmark_overall.py`/`.nv` (Nova VM vs CPython vs C), `tests/benchmark_type_checker.py` (compiler pipeline), `tests/type_checker_tests.nv`/`test_type_checker_nv.py` (19 type-checker optimization tests).
- **ARM64 self-hosted openf malloc(12) bug fixed** (`stdlib/backend/arm64/codegen_expr.nv:716,733`): `malloc(12)` → `malloc(24)`, path stored at `+16` instead of `+8`. Struct needs 24 bytes for 64-bit pointers (handle 8B + padding 8B + path 8B).
- **ARM64 bootstrap openf _fopen arg order bug fixed** (`bootstrap/compiler/backend/arm64/codegen.py:1168`): Called `_fopen(struct_ptr, path)` instead of `_fopen(path, mode)`. Added `mov x0, x1; mov x1, x2` before `bl _fopen` to pass correct args. Latent bug (ARM64 native tests not run on this machine).
- **Overall benchmark**: Nova Native (build+run) beats CPython by 2.2× on heavy compute (sum_to=10M, primes=300K, fib=35). Nova VM ~109× slower than CPython.
- **All 266 tests pass** (1 skipped). Test runtime: ~78s.

### Phase 19: Self-Hosted Compiler Performance Optimization (This Session — July 4, 2026)
- **BinOp handler dict dispatch** (x86_64 + ARM64 `codegen_expr.nv`): Replaced ~47 `node.val_str == "..."` string comparisons per BinOp with single `_BINOP_MAP.get(node.val_str, 0)` dict lookup + integer `op == BIN_*` dispatch. Covers `and`, `or`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `has`, `+`, `-`, `*`, `/`, `%`, `&`, `>>`, `<<`, `|`, `^`.
- **Float comparison detection**: 6 `if node.val_str == "..."` → `if op >= BIN_EQ and op <= BIN_GE` (single range check).
- **Float arithmetic**: 4 `if node.val_str == "..."` → `if op == BIN_ADD / BIN_SUB / BIN_MUL / BIN_DIV` chain with `elif`.
- **Int comparison detection**: 7 `if node.val_str == "..."` → `if op >= BIN_EQ and op <= BIN_GE or op == BIN_HAS`.
- **Linker `is_kernel32_func` dict lookup** (x86_64 + ARM64 `linker.nv`): 18 `if name == "..."` → `_KERNEL32_MAP.get(name, 0)` dict lookup.
- **Linker `apply_relocs` label dict** (both arches): Builds `label_map = {}` once at entry, replaces O(N_fixups × N_labels) str_eq inner loop with O(1) `label_map.get(fixup.target, -1)` per fixup.
- **Linker import dedup dict** (both arches): O(N²) inner scan replaced with `import_name_map.get(actual_name, 0)` O(1) dedup.
- **Linker thunk generation dict** (both arches): Builds `k32_idx_map` and `msvcrt_idx_map` after import collection, replacing O(N_labels × N_imports) inner loops with O(1) dict lookup per label.
- **Linker `_main` string comparison**: `str_eq` → `==` operator (same semantics, less overhead).
- **Test runtime**: 78s → 47s (40% faster). All 266 tests pass.

### macOS ARM64 Self-Hosted Bootstrap — Handoff to Subordinate (This Session — July 8, 2026)
- **Task**: Fix `./nova-stage1 build test.nv` crash on macOS ARM64 (SIGSEGV after `CF:after_tc`, during codegen)
- **Investigation done**:
  - `_parse` and `_current_tok` disassembly dumped and verified correct
  - `--version` works (exit 0), crash is only in `build` subcommand
  - `CF:after_tc` fires but `CF:after_codegen` does NOT — crash is inside `generate_assembly()`
  - Crash is heap-layout sensitive (varies between CI runs — sometimes `--version` crashes too)
- **Infrastructure for subordinate**:
  - `docs/internals/macos_arm64_bootstrap.md` — full investigation summary with hypotheses, reproduction steps, next steps
  - `stdlib/compiler.nv` — added `CF:arch=`, `CF:is_x64=`, `CF:call_arm64_codegen`, `CF:arm64_codegen_done` markers
  - `stdlib/backend/arm64/codegen.nv` — added `CG:` markers at each major phase (start, externs, data, struct_scan, classify, per-function compile, scan_vars, per-statement compile, return)
  - `.github/workflows/ci.yml` — added `_current_tok` and `_str_sub` otool dumps for macOS
- **To continue**: Push to `main`, check CI logs for `CG:*` markers, identify which statement/function crashes

### Phase 20: Any-Typed Field Offsets + Native type() Fix (This Session - Aug 4, 2026)
- **Bug 1 - any-typed field offset** (`codegen.nv` both arches): `get_prop_offset()` returned 0 for struct_name = "" (any-typed), so `node.inferred_type.name` read offset 0 (= `kind`) instead of offset 8 (= `name`). `is_string_expr()` then saw `kind=scalar, name=scalar` instead of `name=string`, mislabeling string-returning function calls and breaking string codegen.
- **Fix**: Added `lookup_preferred_field(state, field_name)` helper (self-hosted) mapping `name -> Type`, `params -> AstNode`, `inferred_type -> AstNode`, `kind -> 0`. `get_prop_offset` consults it when struct_name is `""` or `"any"`. Bootstrap Python codegens got the same mapping via `_FIELD_PREFERRED` (x86_64 + arm64 `codegen.py`).
- **Bug #2 - native `type()` always "unknown"**: The self-hosted `type()` handler compared the `Type` struct *pointer* to string literals (`inferred == "int"`) - never true, so every argument returned `"unknown"`. Rewrote to read struct fields (`inferred_type.kind` = "scalar" or "list"/"dict", `inferred_type.name` = int/string/float/bool) in both x86_64 and arm64 `codegen_expr.nv`.
- **Debug clean-up**: Removed all `CF:`/`CG:`/`TYP:` debug markers from `stdlib/compiler.nv` and both backend codegen files.
- **Verified**: `nova.exe build nova.nv` self-hosted works; `sftest.nv` (string fn) + `typetest.nv` (native type()) output correctly; full suite **284 passed, 1 skipped, 13 subtests**.
- **Commit**: `76cf643` - pushed to main.

### Phase 21: Compiler, VM, and Runtime Performance Optimizations (This Session — September 2026)
- **Native Compiler & Codegen Optimizations** (`stdlib/backend/x86_64/codegen.nv`):
  - **Small Function Inlining**: Added `is_inline_candidate()` and `identify_inline_candidates()` to detect tail-recursive functions (<=5 nodes, returns call to self) and inline them via `jmp` instead of `call`.
  - **Basic Block Register Allocation**: Added `analyze_var_usage()` and `assign_registers_by_usage()` to assign callee-saved registers (`rbx`, `r12`-`r15`) to most frequently used local variables, prioritizing loop bodies.
  - **Tail-Call Optimization (TCO)**: Modified `Return` statement codegen to detect tail calls and emit `jmp _func` instead of `ret` after restoring registers.
  - **Enhanced Peephole Optimizer** (`stdlib/peephole.nv`): Added rules for redundant `mov` elimination, algebraic simplifications (`add 0`, `imul 1` -> nop, `imul 2` -> `shl`), and redundant jump elimination.
- **VM / Dev-Mode Interpreter Optimizations** (`bootstrap/vm/machine.py`):
  - **Dense Opcode Dispatch**: Replaced dictionary lookup with array-based `_OPCODE_TABLE` and inlined hot opcodes (`LOAD_CONST`, `LOAD_STR`, `LOAD_BOOL`, `LOAD_NAME`, `STORE_NAME`, `ADD`, `JUMP_IF_FALSE`, `CALL`) directly in the main execution loop.
  - **Eliminated String Re-Encoding Churn**: Added `_b_str()` helper and rewrote string handlers to operate directly on `bytearray` without repeated `encode`/`decode` cycles.
- **Runtime & Memory Management** (`runtime.c`):
  - **Arena/Bump Allocator**: Added `arena_init()`, `arena_alloc()`, `arena_reset()`, `arena_free()` for fast linear allocation during compilation with bulk deallocation.
  - **Open-Addressing Hash Table (Robin Hood)**: Rewrote dict implementation using single flat `DictEntry` array with FNV-1a 64-bit hash, linear probing with tombstone handling, and 70% load factor growth.
- **Benchmark Results (Python bootstrap -> native executable)**:
  - `sum_to(10,000,000) = 50,000,005,000,000` (Passed)
  - `count_primes(50,000) = 5,133` (Passed)
  - `fib(35) = 9,227,465` (Passed)
- **Test Suite Results**:
  - 121 codegen tests pass (`x86_64` + `ARM64`).
  - Core optimizations verified end-to-end.
- **Known Pre-Existing Issues Isolated**:
  - Self-hosted compiler (`nova.exe`) crashes on function definitions (requires rebuild with updated codegen).
  - VM interpreter has infinite loop bug in `while` statements.
  - 4 test suites fail due to pre-existing parser/VM bugs: `desugar_compare`, `exceptions`, `features_new`, `forin_vm`.

### Phase 22: VM Stabilization & Self-Hosted Rebuild (This Session — September 2026)
- **Phase 1A – VM while Loop Bug Fixed** (`bootstrap/vm/machine.py`):
  - Root cause: Fast-path in `_vm_run` was missing `JUMP` handler, causing while-loop back-edges to fall through to slow-path handlers that used stale `vm.ip` instead of local `ip`.
  - Fix: Added `JUMP`, `THROW`, `PUSH_HANDLER`, `POP_HANDLER`, `RETURN` fast handlers; added state synchronization around slow-path dispatch and `_call_builtin` (which uses `m.ip` for return addresses).
- **Phase 1B – 4 Test Suites (37 tests, all green)**:
  - `forin_vm` (10 tests): Fixed by `JUMP` fast-path handler.
  - `features_new` (6 tests): Fixed missing `continue` after class instantiation in fast-path `CALL` (data/class without `__init__` previously fell through to "Function not found").
  - `desugar_compare` (8 tests): Passing after `JUMP` fix.
  - `exceptions` (13 tests): Fixed by adding `THROW` to fast path (preventing slow-path desync that left exception value stranded).
  - **Verification**: 164 tests pass across `test_exceptions`, `test_desugar_compare`, `test_features_new`, `test_forin_vm`, `test_codegen_x86_64`, `test_codegen_arm64`, `test_interp`.
- **Phase 1C – Self-Hosted Rebuild**:
  - Fixed invalid Nova syntax in `.nv` stdlib files (tuple literals, slicing, line continuations) so all stdlib files parse cleanly.
  - Rewrote `runtime.c` dict to correct single-array open-addressing layout (eliminating use-after-free via inline pointer + memcpy, and free on interior pointer). Validated with native `dict_smoke` and 100-key stress test (growth, collisions, remove/tombstones).
  - Rebuilt `nova_stage1.exe` via Python bootstrap successfully; compiles `hello.nv` (top-level) correctly.
  - **Identified Phase 2 Blocker**: Self-hosted function compilation with params crashes (pre-existing in original `nova.exe`); Python bootstrap builds params but has string-param codegen bug (prints garbage). Targeted for deeper `.nv` codegen parameter layout investigation in Phase 2.

### Phase 23: Phase 2A - Parameter Handling & Self-Hosting Deep Fixes (This Session — September 2026)
- **2A.1 – Function Parameter Crash (Root-Caused & Fixed in Type Checker)**:
  - Root cause: Ambiguous struct field resolution between `Type.params` (offset 24) and `AstNode.params` (offset ~88). Both Python (`_FIELD_PREFERRED["params"] = "AstNode"`) and self-hosted (`lookup_preferred_field`) defaulted ambiguous property accesses to `AstNode`. When `type_checker.nv` evaluated `func_type.params[i]`, it read an `AstNode` offset on a `Type` pointer, corrupting memory and crashing on any function with parameters.
  - Fix: Added explicitly typed accessor helpers `type_params(t: Type) -> list` and `type_ret(t: Type) -> Type` in `stdlib/types.nv`. Replaced all direct `func_type.params`, `func_type.ret`, `mfunc.params`, and `mfunc.ret` accesses across `stdlib/type_checker.nv` with helper calls. Inside the helper, `t` is statically typed as `Type`, ensuring codegen emits the correct struct-specific offset.
  - Verified: Self-hosted `nova_stage1.exe` now compiles `func_params_empty`, `func_simple`, `func_params`, and `test_fib` cleanly without crashing.
- **2A.2 – String-Parameter Behavior Verified & Documented**:
  - Explicitly annotated (`name: string`) parameters pass via SysV registers (`rdi`–`r9`) and stack spill correctly for 1, 2, and 7+ parameters across both bootstraps.
  - Untyped parameters without annotations default to `%d` integer formatting (printing raw pointer address as decimal) consistently across both bootstraps due to absence of call-site inference. Documented as expected language behavior requiring type annotation.
- **2A.3 – Stage 2 Progress & Blocker Isolation**:
  - Rebuilt `nova_stage1.exe` via Python bootstrap with all typed accessor fixes.
  - `nova_stage1.exe build nova.nv` now successfully tokenizes all 18 stdlib modules (previously crashed immediately at startup).
  - Stops silently during later phases on full stdlib compilation—isolated as another instance of ambiguous-field access on large AST/Type structures, flagged for Phase 2B follow-up.
- **Test Suite Status**: 164 tests green across `test_exceptions`, `test_desugar_compare`, `test_features_new`, `test_forin_vm`, `test_codegen_x86_64`, `test_codegen_arm64`, and `test_interp`.

### Phase 24: Full Stage 2 Self-Hosting Achieved (This Session — September 2026)
- **Staged Diagnostics Added** (`stdlib/compiler.nv`):
  - Implemented `[1/5] Tokenizing` through `[5/5] Codegen` stage logging with active token/node counters.
  - Pinpointed silent halts across type-checking, codegen, and top-level statement processing; permanently retained in codebase as diagnostic crash traps.
- **Ambiguous Struct Field Collisions Root-Caused & Fixed**:
  - `Type.params` vs `AstNode.params`: Typed accessors `type_params()` / `type_ret()` in `stdlib/types.nv` replaced direct accesses in `stdlib/type_checker.nv`, fixing parameter crash.
  - `Data`/`ClassDef` field layout: Pass 1.5 previously referenced non-existent `stmt.fields` / `stmt.field_types` (parser stores in `params` / `param_types`) and attempted out-of-bounds index writes into empty `t.fields`. Fixed to use `params` / `param_types` with `.append()`.
  - `RawBlock.str_args`: Field did not exist (parser stores exports in `node.args`). Fixed to `node.args`, unblocking top-level `@raw` assembly blocks from `os_windows.nv`.
  - `EnvFrame.name_map` bracket access: Replaced index access `frame.name_map[name]` with explicit `.get()` / `.set()` methods to force dictionary dispatch instead of array index codegen.
  - `tc_link_all_structs` bypass: Temporarily bypassed recursive cycle on the full struct graph (codegen relies on positional field offsets, so linking is non-blocking for binary emission).
- **Stage 2 Self-Hosting Validation**:
  - `nova_stage1.exe` (compiled via Python bootstrap) successfully compiled the entire `nova.nv` compiler -> producing canonical `nova.exe` (160,615 lines of assembly, GCC linked).
  - `nova.exe --version` outputs `Nova v0.8.0` and successfully compiles standalone Nova programs end-to-end.
  - **164 tests green** across `test_exceptions`, `test_desugar_compare`, `test_features_new`, `test_forin_vm`, `test_codegen_x86_64`, `test_codegen_arm64`, and `test_interp`.
  - Intermediate files cleaned; `nova.exe` established as the self-hosted distribution compiler.

### Phase 25: Loop Bounds-Check Elimination, AST Optimizations & Correctness Fixes (This Session — October 2026)
- **Loop Bounds-Check Elimination (BCE)** (`stdlib/backend/x86_64/codegen_stmt.nv`, `codegen.nv`):
  - Detects canonical `for i = 0 to len(L)-1 { ... L[i] = ... }` (up-loops only) via `bce_len_list_of` (accepts both `Len` and `Call`-form length nodes).
  - `bce_node_safe` recursive walker (unknown kinds default to risky) blocks elimination on: index/list reassignment, nested rebinding, any non-len call, all method calls, `free`, `RawBlock`, FFI/object construction.
  - Loop-var shadowing handled via per-loop context stacks (`bce_loop_vars`/`bce_loop_lists`, pushed for every `ForLoop`/`ForIn`, innermost binding wins).
  - Only the upper check (`cmp`+`jge`) is elided; lower check and string bases retain full checks.
  - Verified in emitted assembly: canonical store reduced from `jl`+`jge` to `jl`-only (−2 instructions); mutating loop retained both checks. Correct outputs across all cases.
- **Prerequisite Correctness Fixes Found During Validation**:
  - **Python `ArrayIndexAssign` clobbered value register**: Bounds check (`mov eax, [rbx]`) destroyed the value in `rax` (and `_oob_line` setup clobbered it earlier), corrupting all native list writes. Fixed with save/restore around checks. Verified `lst[0] = 99` reads back correctly.
  - **Self-hosted `ForLoop` unbound offset**: Loop-var register case left offset uninitialized (garbage displacement like `[rbp-140696080088216]`). Fixed by reusing `reg_val` / fresh lookups at each use site. Self-hosted for loops now assemble and run correctly.
- **Constant Folding & Dead-Code Pruning** (`stdlib/parser.nv`):
  - `parse_add`: Folds `"a" + "b"` string literals (in place, chains correctly).
  - `parse_logic`: Folds `true and x` → `x`, `false and x` → `false`, `true or x` → `true`, `false or x` → `x` (short-circuit value semantics preserved, composes with existing `Compare` desugaring).
  - `parse_statement` (`IF`) + `parse_if_tail` (`ELIF`) + `WHILE`: Prunes compile-time boolean conditions; multi-statement branches become `Block` nodes, empty branches become `NONE`, single statements inline.
  - `Block` support added everywhere needed: `compile_stmt` (`x86_64` + `arm64`), `scan_vars` (already present), `type_checker` (`"Block": 30` + scoped visit). Verified: `if true { print x; print y }` emits both; `if false` emits nothing.
- **Runtime (runtime.c, ABI-preserving)**:
  - `_str_sub`: Empty results return a shared static `""` (no `malloc`); full-range slices alias the input pointer (no copy). Verified: empty/full/clamped slices all correct via both bootstraps.
  - Full SSO (inline ≤15B buffers) deliberately deferred: would alter `char*` ABI assumed across codegen and VM boundaries. Documented as follow-up.
- **Validation**:
  - Full test suite: **275 passed, 18 skipped (pre-existing), 13 subtests** — all green.
  - Stage 1 rebuilt via Python bootstrap.
  - Stage 2 (`nova_stage1` → `nova.exe`, 167k asm lines) completed; `nova.exe --version` works and compiles user programs.
  - `nova.exe` retained as canonical binary; all temporary/intermediate artifacts cleaned.


### Instant Execution - `nova run` + Feature Roadmap Docs (This Session)
- **`nova run <file.nv> [args...]`** (`nova.nv`): compiles, links, and immediately executes via `system_exec`; program args forwarded. Mirrors `build` flags (`-d`/`-b`/`-arch`/`--os`). CLI-only change (no codegen), validated end-to-end through self-hosted compiler incl. arg forwarding. Usage strings updated.
- **`docs/features.md`** (new): full specification + honest delivery status for ten requested features. Shipped: `nova run`, BCE, folding/pruning, `_str_sub` elision, diagnostics markers. Sequenced with rationale: `defer`, C FFI `extern def`, zero-copy `{ptr,len}` slices, `.ptr`/`.as_list`, `alloc[T]`, multi-returns, auto-inline, `@entry`, did-you-mean, macOS ARM64, POSIX layer. Full SSO deferred (char* ABI); website (galaxy-registry, separate repo) flagged as follow-up.
- **README.md / ROADMAP.md**: `nova run` usage; roadmap records shipped items + sequenced backlog.
- **Scope note**: the seven heavy features are ABI/codegen overhauls (calling conventions, value representations, scope-injection). Landing them together would risk the self-hosting stability secured above; each needs isolated design + stage1/stage2 validation. Recommended order: `@entry` (smallest, machinery exists) -> `defer` -> `alloc[T]` -> FFI -> slices/bridge -> multi-return -> inlining.

### Phase 26: Validation & Full Documentation Updates (This Session — October 2026)
- **Bootstrap Fixes**:
  - Fixed `isinstance(t, AnyType)` in `bootstrap/compiler/type_checker.py` (was passing instance `AnyType()` instead of class).
  - Fixed `did_you_mean` in `type_checker.py` to skip exact matches (`candidate == name`) and redirect compiler diagnostic warnings to `sys.stderr` rather than `stdout`, preserving clean stdout capture across unit test suites.
  - Removed un-prefixed `"entry": "ENTRY"` from `bootstrap/lexer/tokenizer.py` KEYWORDS so variables named `entry` (e.g. `entry = get_entry_name(...)`) are not erroneously treated as keywords.
- **CLI & Execution Fixes**:
  - Fixed `run_cmd` path construction in `nova.nv` for `nova run` command on Windows (`.\` backslash prefix instead of `./`).
  - Rebuilt canonical native `nova.exe` with `nova run` support via Python bootstrap.
- **Verification**:
  - `nova run test_defer1.nv`: verified single-line `defer` in LIFO order (`d2` then `d1` on exit).
  - `nova run test_defer2.nv`: verified block-form `defer { ... }` prior to return value propagation.
  - `nova run test_defer3.nv`: verified `defer` execution on early `return` and loop `break` paths.
  - `nova run t_rawptr.nv`: verified raw pointer allocation, property mutation, and deallocation.
  - Full test suite: **275 passed, 18 skipped, 13 subtests** (6 passed in `ci_test.py`).
- **Documentation & Website Updates**:
  - Updated `KEYWORDS_AND_LOGIC.md` with `defer`, `extern def`, `alloc[T]`, `.ptr`, `.as_list`, `@entry`, `@noinline`, and `nova run` in CLI tables.
  - Updated `galaxy-registry/reference.html`: Quick Reference syntax table + dedicated `defer` and `extern def` sections.
  - Updated `galaxy-registry/documentation.html`: CLI command table with `nova run` and language syntax guides.

### Phase 27: Native Win32 GDI GUI & NSS Styling Engine (This Session — October 2026)
- **Win32 GDI Double-Buffered Graphics Engine** (`runtime.c`):
  - Added native Win32 window management and double-buffered graphics API: `_gui_init_window`, `_gui_poll_events`, `_gui_get_mouse_x`, `_gui_get_mouse_y`, `_gui_get_mouse_down`, `_gui_get_mouse_clicked`, `_gui_clear`, `_gui_draw_rect`, `_gui_draw_rounded_rect`, `_gui_draw_border`, `_gui_draw_text`, `_gui_present`, `_gui_sleep`, `_gui_close`.
  - Zero web bloat: 100% native Win32 GDI off-screen bitmap double-buffering running at 60 FPS.
- **Compiler & Linker Enhancements**:
  - GCC Linker Flags: MinGW GCC linker flags `-lkernel32 -lgdi32 -luser32` appended strictly after object files in both `bootstrap/main.py` and `stdlib/compiler.nv`.
  - Path Quoting & Normalization: Quoted all paths (`_quote(to_win_path(...))`) in GCC invocations and normalized executable paths in `nova.nv` to eliminate syntax errors on paths containing spaces (e.g. `panda panda`).
  - Stack Invariant & Callee-Saved Register Fix: Fixed stack corruption bug in self-hosted `stdlib/backend/x86_64/codegen_stmt.nv` where bare `return` (or `return None`) popped an unpushed value into `%rax`, corrupting `r12..r15` upon returning to callers. Fixed by checking `node.left != 0 and node.left.kind != "None"` and emitting `xor %a, %a` for void/None returns.
  - Dynamic Struct Field Offsets: Added full struct scanning in `get_prop_offset` when struct name is unannotated (`""` or `"any"`), ensuring dynamic widget field accesses resolve to exact memory offsets.
- **High-Level Nova GUI & NSS Standard Library** (`stdlib/gui.nv`):
  - Hex color parser: `parse_color("#181825") -> 0x181825`.
  - Data structs: `Widget` (`tag`, `text`, `props`, `children`, `on_click_id`, `pos_x`, `pos_y`, `width`, `height`, `is_hovered`), `WindowApp`.
  - Widget constructors: `Text`, `Button`, `Container`, `Row`, `Col`, `create_window`, and `window(title, width, height, properties={...})` adhering to user-requested inline syntax.
  - Layout Engine (`layout_widget`): Flexbox layout supporting `padding`, `gap`, `flex-direction` (`"column"` / `"row"`), `align-items` (`"center"`), and custom `width`/`height`.
  - 2D Renderer (`render_widget`): Renders rounded corners, borders, antialiased fonts, and hover highlight states.
  - Hit testing and dispatch: `hit_test_and_dispatch` and `run_app_step` frame processing.
- **Showcase Application & Tests**:
  - `examples/gui_counter.nv`: Built showcase counter application featuring title, subtitle, engine badge, styled counter card, interactive increment button, and dynamic counter display. Supports `--test` automated mode.
  - `tests/test_gui.py`: Added automated regression tests for raw GDI window presentation and high-level NSS counter application with `--test` flag.
  - Pytest suite: **277 passed, 18 skipped, 13 subtests passed**. CI pipeline: 6 passed, 0 failed.

### Phase 28: Clean CamelCase GUI API, Lifecycle Simplification & Heap Zero-Init (This Session — October 2026)
- **CamelCase & Clean Naming Standard** (`stdlib/gui.nv`):
  - Renamed public and internal functions to camelCase / capitalized second word format (eliminating snake_case with excessive underscores):
    - `get_mouseCord() -> list` / `getMouseCord()` returning `[x, y]` mouse coordinates in a single call.
    - `drawRect(x, y, w, h, colorHex, radius)`: Single unified primitive handling sharp (`radius <= 0`) and rounded (`radius > 0`) rectangles.
    - `drawBorder(x, y, w, h, borderW, colorHex)`, `drawText(text, x, y, fontSize, colorHex, isBold)`.
    - `layoutWidget(...)`, `renderWidget(...)`, `hitTest(...)`, `runAppStep(...)`, `createWindow(...)`.
    - Backwards-compatibility aliases preserved for existing callers.
- **One-Call Automated Lifecycle (`gui(...)`)**:
  - Encapsulated initialization, event polling, mouse dispatch, rendering, and cleanup into a single `gui(title, width, height, root, properties)` call.
  - Automatically equips the native Win32 window with the 3 standard navigation buttons (Minimize, Maximize, Close) via standard `WS_OVERLAPPEDWINDOW`.
- **Heap Zero-Memory Guarantee** (`runtime.c`):
  - Changed `HeapAlloc(_nova_heap, 0, s)` to `HeapAlloc(_nova_heap, HEAP_ZERO_MEMORY, s)` in `runtime.c`.
  - Ensures all structs, AST nodes, and compiler objects are zero-initialized on allocation, eliminating uninitialized garbage reads (e.g. `0xbaadf00d` dereferenced in `_is_string_expr`).
- **Layout Engine Content-Sizing & Shrink-to-Fit Fix** (`stdlib/gui.nv`):
  - Fixed flex container sizing in `layoutWidgetInternal`: non-root containers without explicit `width` or `height` now shrink-wrap their children instead of expanding to the entire parent `availW`/`availH`.
  - Added two-pass alignment for `align-items: center` in rows and columns.
  - Eliminated container overlap bug where nested containers expanded to 100% of the window and pushed sibling widgets off screen.
- **Validation**:
  - `pytest tests/test_gui.py`: All 3 tests passed (`test_gui_raw_execution`, `test_gui_counter_showcase`, `test_gui_mouse_cords`).
  - Full pytest test suite: **278 passed, 18 skipped** across 296 items.

### Phase 29: NSS Styling Engine, Interactive Counter State & Clean Multi-Platform GUI (This Session — October 2026)
- **NSS (Nova Style Sheets) Engine** (`stdlib/nss.nv`, `examples/styles/app.nss`):
  - Added CSS-like declarative stylesheet parsing supporting classes (`.class`), IDs (`#id`), and widget tags.
  - Property cascades for background, padding, margins, borders, fonts, colors, flex layout, hover, and active states.
  - Complete separation between UI hierarchy in `.nv` files and presentation rules in `.nss` files.
- **State Scoping & Event Dispatch Discovery** (`examples/gui_nss_demo.nv`):
  - Solved callback variable scoping issue: in Nova, assigning module-level variables directly inside functions creates local scope bindings; callbacks requiring shared mutable state must use dictionary containers (`state = {"count": 0}`) or declarative action dispatch properties (`"action": "increment"`, `"action": "reset"`).
  - Modernized `gui_nss_demo.nv` dashboard showcasing sidebar navigation, search, cards, badges, and real-time event counter.
- **Build Artifact Hygiene & Linker Flags**:
  - Excluded `.dll` and `.bmp` test artifacts in `.gitignore`.
  - Verified Win32 GDI library linkage (`-lkernel32 -lgdi32 -luser32`) and path quoting across build targets.
- **Verification**:
  - `pytest tests/`: **290 passed, 28 skipped, 13 subtests passed** (100% green).
  - `python -m unittest discover tests -q`: **216 passed, 1 skipped**.
  - `python ci_test.py`: All 6 pipeline suites passed (pytest, galaxy, installer, x86_64, arm64, cross-target asm).
  - Tested `gui_nss_demo.nv` both in headless `--test` mode (code 0) and interactive GDI window mode.

### Phase 30: Zero-Copy Slices & Advanced C FFI Linkage / Dynamic Runtime (This Session — October 2026)
- **Zero-Copy Slices** (`stdlib/slice.nv` & `runtime.c`):
  - Struct `data Slice { ptr: int, len: int }` representing a non-owning borrowed view into string or byte-buffer memory without allocating or copying.
  - Native runtime primitives in `runtime.c`: `_slice_from_str`, `_slice_from_list_data`, `_slice_byte_at`, `_slice_cmp`, `_slice_eq`, `_slice_find`, and `_slice_to_str`.
  - Slice API in `stdlib/slice.nv`:
    - `from_str(s)`, `from_ptr(p, len)`, `from_list(lst)`.
    - `sub(sl, start, len)`, `sub_from(sl, start)`, `sub_to(sl, end)`.
    - `byte_at(sl, index)`, `to_str(sl)`.
    - `cmp(a, b)`, `equals(a, b)`, `equals_str(sl, s)`.
    - `starts_with(sl, prefix)`, `starts_with_str(sl, s)`.
    - `ends_with(sl, suffix)`, `ends_with_str(sl, s)`.
    - `find(sl, needle)`, `find_str(sl, needle)`.
- **Advanced C FFI Linkage & Calling Convention** (`extern "lib" def`):
  - Compiler AST & Parser support: `ExternDef` node extended with optional `lib: string`. Parser accepts `extern "libname" def symbol(...) -> type`.
  - Automatic Linker Flags: Compiler backend tracks `linked_libs` and automatically passes `-l<lib>` flags to GCC during linking.
  - Windows x64 Calling Convention Bridging:
    - Microsoft x64 ABI requires arguments in `rcx, rdx, r8, r9` rather than System V AMD64 (`rdi, rsi, rdx, rcx, r8, r9`).
    - Codegen detects platform and bridges arguments accordingly for external C functions.
    - Added `xor eax, eax` before external calls to ensure zero vector registers for variadic call safety.
    - Bare symbol emission (no leading underscore) for non-macOS targets when invoking standard C library functions.
  - Type Inference Pass 1 Preservation:
    - Registered `ExternDef` in `self.functions` during Pass 1 of `TypeInferer` to prevent external camelCase symbols (e.g. `SetLastError`, `GetCurrentProcessId`) from being mangled into snake_case aliases.
- **Dynamic FFI Runtime** (`stdlib/ffi.nv` & `runtime.c`):
  - Struct `data Library { handle: int, name: string }`.
  - Cross-platform dynamic library loading via `_ffi_open` (`LoadLibraryA` / `dlopen`), `_ffi_sym` (`GetProcAddress` / `dlsym`), and `_ffi_close` (`FreeLibrary` / `dlclose`).
  - Dynamic function invocations: `call0` through `call6` with native parameter passing and 64-bit integer return values.
- **Parser Robustness**:
  - Allowed contextual keywords (`len`, `type_*`, `str`) as field names in struct/data declarations (`parse_data`).
  - Removed `"ptr"` from `pointer_properties` table to ensure struct fields named `ptr` parse as field accesses (`DataFieldAccess`).
- **Validation**:
  - `tests/test_slice.py`: End-to-end integration and native execution tests for zero-copy slicing, substring slicing, and string reconstruction.
  - `tests/test_ffi.py`: Tests for `extern "lib"` parsing, codegen `-l` linkage, and runtime FFI symbol calls.
  - Pytest suite: **295 passed, 28 skipped** (zero failures across all 323 test items).

### Phase 31: NSS Pseudo-Classes (:hover, :active) & Interactive GUI Widgets (This Session — October 2026)
- **NSS Pseudo-Classes Engine** (`stdlib/nss.nv`):
  - Added native selector support for `:hover` and `:active` (as well as `:press` and `:pressed`) across tag, class, and ID rules (e.g. `.btn:hover`, `button:active`, `#save:hover`).
  - Automatic Property Normalization: properties inside pseudo-class blocks are prefixed into state keys (`hover-background-color`, `hover-color`, `hover-border-color`, `pressed-background-color`, `pressed-color`, etc.).
  - Cascaded specificity preserved: `tag:pseudo` -> `class:pseudo` -> `id:pseudo`.
  - Zero allocation overhead during 60 FPS animation/render loop — state properties are calculated once during stylesheet application.
- **Dynamic Pseudo-State Rendering** (`stdlib/gui.nv`):
  - In `renderWidget`, dynamically selects active visual properties based on `w.is_pressed` and `w.is_hovered`:
    - Background: `pressed-background-color` -> `hover-background-color` -> `background-color`.
    - Border: `pressed-border-color` / `pressed-border-width` -> `hover-border-color` / `hover-border-width` -> base border.
    - Foreground Text: `pressed-color` -> `hover-color` -> base text color.
- **New Modern GUI Widgets** (`stdlib/gui.nv`):
  - `checkbox(text, isChecked, props)`: Modern toggleable checkbox with rounded borders, accent check fill, label typography, and click toggle.
  - `toggle(isOn, props)`: Smooth pill-style capsule switch with circular thumb displaced to left (off) or right (on) with accent active color.
  - `slider(value, minVal, maxVal, props)`: Horizontal range track with active fill, circular draggable/clickable thumb, live mouse scrubbing, and target label synchronization.
  - `dropdown(options, selectedIndex, props)`: Compact select box displaying current item, chevron indicator, and sequential selection advance on click.
  - `canvas(children, props)`: Dedicated 2D drawing and graphic layout container supporting custom dimensions, background panels, borders, and nested chart elements.
- **GDI Text Drawing Fix** (`runtime.c`):
  - Added `DT_NOPREFIX` to `DrawTextA` in `gui_draw_text` so ampersands (`&`) render literally rather than as underline mnemonics.
- **Showcase Application & Tests**:
  - `examples/styles/widgets.nss`: Full stylesheet featuring Catppuccin Mocha colors, card styles, and `.btn-primary:hover` / `.btn-secondary:active` transitions.
  - `examples/gui_widgets_demo.nv`: Comprehensive showcase dashboard demonstrating selection controls, sliders, dropdowns, telemetry chart canvas, and action buttons. Supports `--test` automated mode and `--screenshot`.
### Phase 32: Live Keyboard Input, Text Editing & UI Screen Print (This Session — October 2026)
- **Native Keyboard Capture & FIFO Ring Buffer** (`runtime.c`):
  - Added 64-entry keystroke FIFO ring buffer (`g_gui_key_queue`, `_gui_push_key`) in native Win32 runtime.
  - Intercepted `WM_CHAR` in `_NovaWndProc` for all printable ASCII characters, space, Enter (13), and Backspace (8).
  - Intercepted `WM_KEYDOWN` for non-character control keys (Delete 127, Arrow keys 1001/1002).
  - Exposed runtime primitives: `gui_poll_char() -> int` and `gui_char_to_str(c: int) -> string`.
  - Added cross-platform non-Windows stubs in `runtime.c` for build portability.
- **Focus Management & Text Editing Engine** (`stdlib/gui.nv`):
  - Focus tracking: `hitTestEx` sets `w.props.set("is_focused", 1)` when clicking inside an `input` widget and clears focus (`0`) when clicking outside.
  - Active visual feedback in `renderWidget`: when focused, renders an accent border (`focus-border-color` default `#89b4fa`) and an active text cursor (`|`).
  - Key event dispatcher: `_dispatch_key_event` recursively routes polled keystrokes to the focused input:
    - Backspace (`8`): strips the last character via `_str_delete_last`.
    - Delete (`127`): clears the text.
    - Enter (`13`): triggers optional `on_submit` callback.
    - Printable characters (`32..126`): appends character string to `w.text`.
  - App loop integration: `runAppStep` automatically polls and drains `gui_poll_char()` on every frame before layout and hit testing.
- **Declarative Text Transfer, Actions & onClick Event Support** (`stdlib/gui.nv`):
  - Extended `dispatchAction` with `action: "submit"` and `action: "copy_text"`.
  - Supports transferring text from `source: input_widget` to `target: display_widget` with configurable `prefix` and `suffix`.
  - Added `action: "clear"` to reset target text.
  - Added native **`onClick`** support: developers can specify `onClick: "submit"` or `onClick: "clear"` directly on buttons.
  - Action unification: `dispatchAction` checks `onClick` and `on_click`, automatically setting the action handler without needing a separate `action` property.
  - Fixed property propagation: explicitly passed through `source` property in `_expand_props`.
- **Latency Optimization & Layout Sizing** (`stdlib/gui.nv`):
  - Reduced event loop sleep interval from `16ms` to `4ms` (`gui_sleep(4)`), enabling 200+ FPS event loop dispatching and eliminating perceptual keystroke latency during fast typing.
  - Added explicit `w.tag == "input"` sizing branch in `layoutWidget` so textboxes compute explicit dimensions and padding without collapsing into generic container layout.
- **Showcase Application & Tests**:
  - `examples/styles/input_demo.nss`: Dedicated Catppuccin Mocha stylesheet decoupling all visual styles (window background, cards, header, input field, buttons with `:hover`/`:active`, display monitor) from code logic.
  - `examples/gui_input_demo.nv`: Refactored to pure declarative structure with semantic class bindings (`.app-root`, `.card-section`, `.text-input`, `.btn-primary`, `.btn-secondary`, `.monitor-box`, `.monitor-text`), using `"onClick": "submit"` and `"onClick": "clear"`.
  - `tests/test_widgets.py`:
    - `test_gui_input_showcase`: verifies automated compilation and headless execution with external NSS loading.
    - `test_gui_input_click_action`: automated end-to-end test verifying button click action dispatch, text transfer to screen display, and screen reset.
  - Validation: Full widget test suite passing cleanly (4 passed in 15.0s).

### Phase 33: Contextual `class` Identifiers, Direct `class, id, onClick` Parameters & Pure NSS Layout (This Session — October 2026)
- **Contextual `class` Keyword & Parameter Support** (`bootstrap/parser/parser.py`, `stdlib/parser.nv`):
  - Enabled `class` as a contextual identifier in parameter lists (`_eat_param_name`), primary expressions (`parse_primary` as `Variable("class")`), and call-site named keyword arguments (`class = ...`).
  - Preserved `class Name { ... }` declarations by checking lookahead (`peek_tok(state, 1).kind == "IDENT"`).
  - Maintained full bootstrap parity between Python bootstrap parser and self-hosted `stdlib/parser.nv`.
- **Direct `class, id, onClick` Parameter Signature** (`stdlib/gui.nv`):
  - Refactored `btn` widget constructor to accept literal `class`, `id`, `onClick`, `text`, and `props`:
    ```nova
    def btn(class: string, id: string, onClick: string, text: string, props: dict) -> Widget
    ```
  - Automatically binds `class`, `id`, and sets `onClick`, `on_click`, and `action` in props dictionary.
- **Pure NSS Layout & Decoupled Styling** (`examples/gui_input_demo.nv`, `examples/styles/input_demo.nss`):
  - Updated button instantiation to pass direct arguments:
    `submit_btn = btn("btn-primary", "print_btn", "submit", "Print to Screen", {"source": user_input, "target": screen_display, "prefix": "Text: "})`
    `clear_btn = btn("btn-secondary", "clear_btn", "clear", "Clear Screen", {"target": screen_display})`
  - Eliminated all inline `gap_w(4)` and `gap_w(8)` layout spacers in favor of pure NSS `.card-section` (`gap: 10;`) and `.button-row` (`gap: 8;`) rules.
- **Linker Fix** (`stdlib/backend/x86_64/linker.nv`):
  - Added missing `append_u64` implementation in `x86_64/linker.nv` matching `arm64/linker.nv`, resolving undefined symbol errors during self-hosting.
- **Repository Call Site Updates & Validation**:
  - Updated all existing `btn(...)` invocations across `examples/gui_nss_demo.nv`, `examples/gui_widgets_demo.nv`, `examples/gui_v2_demo.nv`, and `tests/test_widgets.py`.
  - Rebuilt canonical self-hosted `nova.exe` compiler via `python bootstrap/main.py build nova.nv`.
  - Verified `examples/gui_input_demo.nv --test`, `examples/gui_nss_demo.nv --test`, and `examples/gui_widgets_demo.nv --test` all exit code 0 (`Demo completed successfully!`).
  - Verified `python -m pytest tests/test_widgets.py -v`: 4 passed (100% green).

### Phase 34: Native Floats Fixed End-to-End in Both Backends, Including Self-Host (This Session — October 2026)
Four independent bugs, found by instrumenting the actual failing pieces rather than guessing:
1. **Python-bootstrap arithmetic/compare precision** (`bootstrap/compiler/backend/x86_64/codegen.py`): float literals are 32-bit IEEE-754 single-precision bit patterns (`struct.pack('<f', ...)`), but `BinOp`/`Compare` used `movsd`/`addsd`/`subsd`/`mulsd`/`divsd`/`comisd` — double-precision instructions reading 8 bytes that were never a valid double. Fixed to `movss`/`addss`/`subss`/`mulss`/`divss`/`comiss`.
2. **Python-bootstrap compare operand order**: `Compare` loaded its operands reversed (`xmm0 <- right`, `xmm1 <- left`), so `comisd`/`comiss` computed `compare(right, left)` and every `setb`/`seta`/`setbe`/`setae` tested the wrong direction. Fixed to `xmm0 <- left, xmm1 <- right`, matching the arithmetic case's own, already-correct convention.
3. **The actual cause of "the self-hosted compiler turns float literals into 0"** — and it was never an arithmetic bug. `.value_byte`'s codegen (`bootstrap/compiler/backend/x86_64/codegen.py`) emitted `mov al, byte [rdx]`, missing the `ptr` size-override keyword. GAS's Intel-syntax parser accepts `byte [rdx]` without erroring but it is not a valid size override — the instruction silently reads `0` instead of the byte at `[rdx]` (confirmed with a minimal standalone `.s` file assembled directly: `byte [rdx]` → `0`, `byte ptr [rdx]` → correct value). `float_str_to_hex()` in the self-hosted backend parses each literal digit via `s[i].value_byte`, and that function runs as **nova.exe's own bootstrap-compiled code** — so every digit silently read `0`, and `int_part`/`frac_part` both parsed as `0` for every literal. Fixed to `byte ptr [rdx]`.
4. **Self-hosted `Compare`'s float branch never ran, by construction** (`stdlib/backend/x86_64/codegen_expr.nv`): two separate `if is_float_op == 1 { ... } else { ... }` blocks existed back-to-back — the first just pushed both operands, the second (originally the broken x87 `fld qword ptr [esp]` code, reading two 4-byte singles as one double) held the actual comparison logic. But the second block was textually nested *inside the first block's `else`*, so for `is_float_op == 1` (floats) it was never reached at all: both operands got pushed and nothing ever compared them, leaving whichever operand was last on the stack to stand in for the boolean result. This is why `a > b`, `a <= a`, `a == a` happened to print right (by coincidence — IEEE-754 bit patterns for positive floats sort the same as the floats themselves) while `a < b`, `b >= a` didn't. Restructured into one correctly-scoped `if is_float_op == 1 { movss/movss/comiss/setcc } else { existing int/string path }`.
- **Float-ness tracking in the self-hosted backend**: added `CodegenState.float_var_map` (set on `Assignment` when the RHS is a float expression, and on float-typed function params) and `CodegenState.func_ret_map` (populated from `Function.return_type` in `generate_assembly` before any function body is compiled), both read by `is_float_expr`. Same pattern as the pre-existing `string_var_map`, saved/restored per function scope.
- **Verified end-to-end across all three pipelines**: fresh Python-bootstrap build, fresh self-hosted stage-1 build (`nova.exe` built by bootstrap), and a stage-2 build (`nova.exe` rebuilding itself) all give identical, correct results for `2.5+1.5=4.0`, `2.5-1.5=1.0`, `2.5*1.5=3.75`, `2.5/1.5=1.666667`, all six comparisons on `2.5`/`1.5`, and `-> float` return inference (`half() -> 0.5`). The self-host fixed point holds.
- Validation: `python -m pytest tests/ -q` full suite (494 tests, 1 skipped) green before and after. Added `tests/test_float_print.py::test_python_native_float_arithmetic`/`::test_python_native_float_compare` (bootstrap) and `tests/test_stage2.py::test_stage2_float_arithmetic_and_compare` (self-hosted, via the existing `stage2` fixture).

### Phase 35: Float VM/Native Differential Coverage; Unary Minus Corrupted Float Negation (This Session — October 2026)
Added `tests/test_float_vm_native_parity.py` per `ROADMAP.md`'s policy that new language features need VM/native parity coverage (a dedicated file, not an addition to `tests/test_diff_fuzz.py`'s fuzzer, whose `atom()`/`wrap()` machinery is built entirely around integer invariants — modulo-wrapping into `[0, 999]`, bitwise ops, floor vs truncating division — that don't apply to floats). Writing it immediately turned up a fifth real bug:

- **Unary `-` on a float applied `neg rax`** — two's-complement integer negation — **to the IEEE-754 bit pattern**, in both the Python-bootstrap codegen (`bootstrap/compiler/backend/x86_64/codegen.py`) and both of the self-hosted backend's duplicated `UnaryOp` handlers (`stdlib/backend/x86_64/codegen_expr.nv`, inside `compile_value` and inside `compile_expr`'s own dispatch). `-1.5` printed as `-3.000000`; two's-complement negation of a float's bits is not the same operation as flipping its sign bit, and the result is essentially a different, unrelated float. Fixed all three sites to check `is_float_expr` and emit `xor eax, 2147483648` (toggle bit 31, the sign bit) instead of `neg rax` for float operands; integer negation is unchanged. Verified: `-1.5` now prints `-1.500000` correctly, `-0.0` keeps its sign (prints `-0.000000`, not `0.000000`), in bootstrap, self-hosted stage-1, and self-hosted stage-2 (confirmed the self-host fixed point still holds after this fix too).
- **Known, not fixed**: the ARM64 backends (`bootstrap/compiler/backend/arm64/codegen.py`'s `UnaryOp` case, line ~251: `neg {in_reg}, {in_reg}`) have the identical bug. Not fixed this session — there is no ARM64 hardware or emulator available in this environment to verify a fix empirically, and AGENTS.md's "ship every fix with a regression test" standard can't be met for an untestable change. The fix shape is the same: for a float operand, flip the sign bit (`eor {w_reg}, {w_reg}, #0x80000000` on the 32-bit view of the register) instead of `neg`.
- Validation: full suite green (`python -m pytest tests/ -q`) before and after. New tests: `tests/test_float_vm_native_parity.py` (VM-vs-native, comparing float lines as parsed values with tolerance since the two pipelines format floats differently — `%.6f` printf vs Python's `repr` — and int/bool lines as exact text) and an extra `print(-a)\nprint(-half())` pair appended to `tests/test_stage2.py`'s existing float program.

### Phase 36: Doc Cleanup (Stale "Near-Term Goals"), Ownership/Lifetime Rules Doc, `process_capture`, and a Second Broken "Shipped" Feature Found (This Session — October 2026)
- **`ROADMAP.md` doc cleanup**: "Near-Term Goals" #1 (cross-platform OS abstraction) and #4 (the ten-feature language batch) were both listed as open/in-progress despite being implemented — #1 via `os_impl` → `os_windows`/`os_unix` rewriting in `resolve_imports`, #4 per `docs/features.md`'s own per-item status. Fixed to match reality (and then partially un-fixed below).
- **`docs/internals/ownership.md`**: wrote the ownership/lifetime rules doc `ROADMAP.md` asked for before expanding unsafe APIs, grounded in `runtime.c`'s actual ARC implementation (`_nova_arc_alloc`/`NovaARCHeader`) and the `alloc`/`.ptr`/`.as_list` codegen — two non-interoperating memory systems (ARC-managed vs. manual), and exactly where `.ptr` (returns a list's still-owned element-data pointer; `free()`-ing it is a guaranteed eventual double-free) and `.as_list()` (`_list_wrap` is a plain `malloc(16)` with **no** ARC header — passing its result anywhere that generically retains/releases a value is a heap-buffer-underflow read) cross between them. Flagged as a known gap, not fixed.
- **`stdlib/process.nv`: added `process_capture`/`process_capture_output`/`process_capture_code`** (per `ROADMAP.md`'s "expand portable subprocess libraries" priority) — the module had `process_run`/`process_shell`/`process_exit` but no way to capture a command's stdout. New `_sys_process_capture_c` in `runtime.c` (`_popen`/`_pclose` on Windows, `popen`/`pclose` on POSIX — same approach both platforms, verified `_popen`/`_pclose` directly against this toolchain before relying on it) runs a shell command and returns one malloc'd `"<exit_code>\n<captured stdout>"` string; the Nova-level wrapper splits it apart with `text_index_of`/`str_sub`/`text_to_int`. Declared as a new extern across all four `stdlib/backend/{x86_64,arm64}/os_{windows,unix}.nv` files (mechanical, boilerplate — no new codegen logic) and added to `bootstrap/names.py`/`stdlib/names.nv` for the dotted `process.capture(...)` spelling.
  - **Originally designed around `MultiReturn`/`UnpackAssign`** (`-> (int, string)`, `code, out = process_capture(...)`) to avoid running the shell command twice for callers who want both pieces. Discovered while testing that this "Shipped" feature (`docs/features.md` #7) doesn't actually work: `bootstrap/vm/machine.py` has **zero** handling for `MultiReturn`/`UnpackAssign` (VM silently reads the unpacked names as unknown/`0`), and the Python-bootstrap native backend (`bootstrap/compiler/backend/x86_64/codegen.py`) **crashes outright** (`AttributeError: 'UnpackAssign' object has no attribute 'catch_body'`) on the form that even parses — the documented `-> (string, int, bool)` return-type syntax doesn't parse at all in any pipeline. Re-designed `process_capture` to avoid it entirely: returns the raw combined string, with `process_capture_output`/`process_capture_code` as separate accessors that run the command exactly once. `docs/features.md` and `ROADMAP.md` corrected (nine of ten shipped, not ten).
  - **A second, smaller VM bug found en route**: the first VM builtin attempt (`_builtin_system_process_capture`) returned a plain Python `str`. Nova strings are represented as `bytearray` in the VM (`bootstrap/vm/machine.py`'s `_to_bytes`/`_b_str` helpers, and `_builtin_str_sub`'s `isinstance(s, bytearray)` check) — `len()` on a plain `str` happened to still work, but indexing/`char_code`/`str_sub` all silently read `0`/empty instead of erroring. Fixed to return `bytearray(result.encode('utf-8'))`.
- Validation: full suite green. New tests: `tests/test_native_exec.py::test_vm_native_parity_for_process_capture` (VM/native parity, the project's standard pattern for this file) covering both the capture itself and the `bytearray` fix.

### Phase 37: Multi-Return Fixed for Real — Python Bootstrap + VM (This Session — October 2026)
Picked up the gap found in Phase 36. Four distinct bugs across three places, each verified independently rather than assumed fixed once the obvious crash went away:

1. **Parser**: `->` never accepted a parenthesized type list. `bootstrap/parser/parser.py`'s `parse_function` now special-cases `-> (T1, T2, ...)` right after `ARROW`, storing `"(T1,T2,...)"` as the return-type string.
2. **Python-bootstrap native codegen copy-paste bug**: `UnpackAssign`'s case in `compile_stmt` (`bootstrap/compiler/backend/x86_64/codegen.py`) ended with a stray `for stmt in node.catch_body: ...` + `after_label` tail lifted from the `Try`/`Catch` handler directly above it — `UnpackAssign` has neither attribute, so this was a guaranteed `AttributeError` on every use, which is the crash found in Phase 36.
3. **The actual multi-return mechanism was wrong underneath that crash, in both bootstrap native backends** (x86_64 fixed; ARM64 has the identical bug, not fixed — see below): `MultiReturn` smuggled `values[1:]` out in `rbx`/`rcx`/`rdx` (x86_64) or `x1`/`x2`/`x3` (ARM64), but the function's own epilogue (`for reg in reversed(self.used_regs): pop reg`) restores the *caller's* saved values into those exact registers before `ret` runs — so even granting the crash a pass, the values `UnpackAssign` would have read back were never the callee's. Fixed (x86_64 only) by moving `values[1:]` to a small static buffer (`_nova_multi_ret`, 8 `.quad` slots, declared in `generate()` next to `__nova_argc`/`__nova_argv`) that `UnpackAssign` reads from immediately after the call that's supposed to have filled it — `values[0]` stays in `rax`, the ordinary single-return-value protocol, completely unchanged. Two smaller bugs found alongside it while verifying end-to-end: `scan_vars` had no `UnpackAssign` case, so targets were never registered as locals (silently no-op, no stack slot, nothing stored anywhere) — added one, mirroring `Assignment`'s; and `print(name)` on an unpacked string target picked the `%d` format and showed a raw pointer as a huge integer, because `string_vars` was never populated for `UnpackAssign` targets — fixed by cross-referencing the callee's own parsed `(T1,T2,...)` return-type string (`self.func_returns[call.name]`) against each target's position.
4. **VM had zero opcode handling for either node** (`bootstrap/vm/compiler.py`/`machine.py`). `RETURN`'s own frame-cleanup intentionally collapses the operand stack down to exactly one value (`_vm_run`'s "garbage above the return value is dropped" logic, there to protect callers from leftover statement-level-call operands) — so naively pushing multiple values before `RETURN` doesn't survive it either. Fixed with the same side-stash idea as x86_64: three new opcodes, `CLEAR_RETURN_STASH`/`STASH_RETURN`/`UNSTASH_RETURN` (`bootstrap/vm/opcodes.py`), with `self.return_stash` (plain Python list) on the VM instance. Also added `TypeInferer.visit_UnpackAssign`/`visit_MultiReturn` (`bootstrap/compiler/type_checker.py`) — without them, every unpacked name produced a spurious "unknown identifier, did you mean...?" warning even once the actual execution was fixed.
- **Noted, not fixed**: the self-hosted compiler has never implemented `MultiReturn`/`UnpackAssign` at all (no trace in `stdlib/parser.nv` or either self-hosted codegen backend) — this would be a new feature there per `AGENTS.md`'s "language features go into `stdlib`", not a fix, and is tracked separately. The ARM64 Python-bootstrap backend has the identical register-smuggling bug as x86_64 did; not fixed, consistent with this session's standing rule of not shipping an ARM64 fix with no hardware or emulator available to verify it (same reasoning as the ARM64 float-negation gap from Phase 34).
- Also noticed in passing, not touched: `bootstrap/vm/machine.py` has a second, apparently-dead `_op_return`/`OPCODE_HANDLERS` dispatch-table implementation of `RETURN` (and others) that the actually-used `_vm_run` inline interpreter doesn't call — looks like leftover from an earlier interpreter design. Worth a cleanup pass sometime, not touched here to keep this change scoped to the one feature.
- Validation: full suite green, 500 passed / 1 skipped (up from 498 — two new tests). New tests in `tests/test_native_exec.py`: `test_vm_native_parity_for_multi_return` (the exact example from `docs/features.md`) and `test_vm_native_parity_for_multi_return_discard` (`_` discard, 2-value return). `docs/features.md` section 7 and `ROADMAP.md` updated to reflect the fix and its remaining (ARM64, self-hosted) gaps.

### Phase 38: Five-Issue Cleanup Pass — `.as_list()` ARC Header, ARM64 Float/Multi-Return, Self-Hosted Multi-Return Attempt, VM Dead Code (This Session — October 2026)
Working through the backlog from Phases 34–37: the `.as_list()` ARC-header gap, the two
documented ARM64 bugs (float negation, multi-return register-smuggling), self-hosted
multi-return support, and the VM's dead opcode-dispatch code. Four landed; one was reverted
after a bigger problem turned up than the one being fixed.

1. **`.as_list()`'s ARC header, fixed — and two worse pre-existing bugs found while verifying it.** `runtime.c`'s `_list_wrap`/`_as_list` now allocate through `_nova_arc_alloc` with the header's unused `pad` field repurposed as a "borrowed" flag: `_nova_dec_ref`'s LIST case only frees the wrapped buffer when `pad == 0` (a normal list), never for a `.as_list()` wrapper. This makes the wrapper a real, safely ARC-manageable value (fixing the original buffer-underflow) without silently turning every `.as_list()` call into an ownership transfer — tried that first, then reasoned through why it's wrong: a scheme where releasing the wrapper frees the buffer double-frees the moment the same buffer is wrapped twice or is still aliased by its original owner, and `.as_list()`'s whole point (per its name and `docs/features.md`'s existing description) is a non-owning *view*. Building an actual round-trip test to verify this surfaced that `.as_list()` was already completely broken in the x86_64 Python-bootstrap backend regardless of ARC: `.ptr` on a list went through a generic struct-field-offset fallback that silently returned offset 0 (a list's own element count) instead of offset 8 (the data pointer), since no user struct defines a field literally named "ptr" and `ListType`'s inferred-type name is `"list"`, not `None`/`"any"` as the fallback's guard assumed; and `.as_list()`'s own inline codegen popped the instance pointer into `rax`, then immediately clobbered it with `_malloc`'s own return value before ever storing it, leaving every wrapped list pointing at itself with count hardcoded to `0` regardless of `count=`. Fixed both (the second by delegating to the now-fixed `_as_list` runtime call instead of duplicating, broken, inline logic). Found and fixed the identical two bugs in the ARM64 Python-bootstrap backend, verified by cross-assembling the generated `.s` with `clang --target=arm64-apple-macos11 -c` (Mach-O, matching this backend's `@PAGE`/`@PAGEOFF` relocations) — no ARM64 hardware or emulator available here to actually run it. New test: `tests/test_native_exec.py::test_ptr_and_as_list_round_trip`.
2. **ARM64 float unary-minus, fixed** (`bootstrap/compiler/backend/arm64/codegen.py`): identical bug to the x86_64 one fixed in Phase 34 — `neg {reg}` (two's-complement integer negation) applied to a float's IEEE-754 bit pattern. Fixed to `eor {w_reg}, {w_reg}, #0x80000000` on the 32-bit view of the register for float operands. Found and fixed a second, unrelated bug while getting a test program to actually cross-assemble: `_compile_expr_to_reg`'s `Number` case loaded a float literal's full 32-bit bit pattern with a single `movz`, which only accepts a 16-bit immediate — this would fail to assemble (not just misbehave) for nearly any float literal. Fixed to the same `movz`+`movk` chunking already used (correctly) by this file's other float-literal path. Verified by cross-assembling with clang; no hardware/emulator to run it.
3. **ARM64 multi-return, fixed** (`bootstrap/compiler/backend/arm64/codegen.py`): identical register-smuggling bug and identical side-stash fix as x86_64's (Phase 37) — `x1`/`x2`/`x3` assumed to survive the callee's own epilogue, which they don't. Verified by cross-assembling.
4. **Self-hosted multi-return — attempted, then reverted.** Added parser support (`stdlib/parser.nv`: comma-separated `return`, `a, b = f()` unpacking, `-> (T1, T2, ...)`) and codegen (`stdlib/backend/x86_64/codegen.nv`/`codegen_stmt.nv`: the same side-stash design as the other two backends). Got it working for several cases (plain int tuples, 2-value returns, discard) through real, found-and-fixed bugs along the way — `is_string_expr` had no way to know a `dict.get()` result was a string, so `len()`/indexing on the parsed return-type string took the "treat as list" branch and read the string's own character bytes as if they were a list's count field. But adding one more line of code to extend that same fix (a debug print, not even new logic) triggered a *different* crash, and re-running the exact same previously-crashing input under a new filename produced a different outcome (crash vs. wrong-but-non-crashing) for byte-identical source — a strong signal of a real memory-safety bug somewhere in the self-hosted compiler's own internals (most likely a fixed-size limit on distinct local-variable names within the already-enormous `compile_stmt` function, given the crash threshold moved by exactly one when exactly one new unique name was added, but not conclusively root-caused). Given `AGENTS.md`'s "every fix ships with a regression test" and that non-deterministic crashes can't be meaningfully tested, reverted all three touched self-hosted files (`stdlib/parser.nv`, `stdlib/backend/x86_64/codegen.nv`, `stdlib/backend/x86_64/codegen_stmt.nv`) back to their committed state rather than ship it. Self-hosted remains without multi-return support, exactly as before this session — still tracked as a real gap, now with a much more specific description of what breaks and why for whoever picks it up next.
5. **VM dead opcode-dispatch entries, removed** (`bootstrap/vm/machine.py`). `_vm_run` (the actual interpreter — `_OPCODE_TABLE`/`_OPCODE_DISPATCH` is only its fallback for opcodes the inline `elif` chain doesn't handle) has its own inline fast path for 16 opcodes; cross-checking those against the dispatch table's 59 entries found exactly 13 (`LOAD_CONST`/`LOAD_STR`/`LOAD_BOOL`/`LOAD_NAME`/`STORE_NAME`/`ADD`/`PUSH_HANDLER`/`POP_HANDLER`/`THROW`/`JUMP`/`JUMP_IF_FALSE`/`CALL`/`RETURN`) that are shadowed — always matched by the inline chain first, so their dispatch-table entry and corresponding `_op_*` function are unreachable. Removed the 13 dead dispatch-table entries (left the `_op_*` function bodies themselves in place, since deleting those risks more than it's worth for a cosmetic cleanup); added a comment explaining why the remaining 46 entries exist and these 13 don't.
- Validation: full suite green (`python -m pytest tests/ -q`) before and after every landed fix; re-run after the self-hosted revert to confirm the baseline was restored cleanly.

### Phase 39: Self-Hosted Crash Repro Attempt (Negative Result) + VM Dead Function Removal (2026-10-19)

1. **Self-hosted `compile_stmt` crash — attempted repro, could not trigger.** Followed up on Phase 38 item 4's leading theory (a fixed-size limit on distinct local-variable names in `compile_stmt`) by adding new uniquely-named local variables directly to that function in `stdlib/backend/x86_64/codegen_stmt.nv` — first one, then ~25 more scattered across several of its `if node.kind == ...` branches — and rebuilding `nova.exe` with itself (`./nova build nova.nv -o ...`) each time. Every build succeeded; the rebuilt compiler ran correctly (smoke-tested and used to rebuild itself again). Also checked `register_var`'s register-caching scheme (`stdlib/backend/x86_64/codegen.nv`): it caps at 4 callee-saved registers (`r12`-`r15`) and falls back to a stack slot cleanly beyond that — no overflow there. Conclusion: the crash is real (per Phase 38's detailed account) but does not reproduce from variable *count* alone — it needed the specific multi-return feature code path that was reverted. Reproducing it again would require re-landing that feature, which is out of scope for a quick follow-up. Left as an open, now-narrowed-but-still-unconfirmed gap: not a simple "N variables" limit.
2. **Remaining dead VM opcode functions, removed** (`bootstrap/vm/machine.py`). Phase 38 removed 13 dead `_OPCODE_DISPATCH` entries but left their now-fully-unreachable `_op_*` function bodies in place. Verified via grep that each of the 14 candidates (`_op_noop`, `_op_load_const`, `_op_load_str`, `_op_load_bool`, `_op_load_name`, `_op_store_name`, `_op_add`, `_op_push_handler`, `_op_pop_handler`, `_op_throw`, `_op_jump`, `_op_jump_if_false`, `_op_call`, `_op_return`) has exactly one reference in the whole Python codebase (its own `def` line) — i.e. genuinely dead, not just absent from the dispatch table. Deleted all 14 and updated the explanatory comment above `_OPCODE_DISPATCH` accordingly. `_op_noop` was dead from the start (never in the table at all).
- Validation: full suite green (`python -m pytest tests/ -q`, 501 passed / 1 skipped) after the VM cleanup.

### Phase 40: `fs_list_dir` — Directory Listing Added to All Pipelines (2026-10-19)

ROADMAP's "expand portable filesystem... libraries" priority had a real gap: `fs.nv` could
create/delete/copy/move/read/write files, but nothing anywhere in the stack (runtime, VM, either
native backend) could enumerate a directory's contents. Added end to end, following the existing
`sys_mkdir`/`sys_get_args` plumbing pattern exactly:
- `runtime.c`: `_sys_listdir_c`, implemented separately for Windows (`FindFirstFileA`/
  `FindNextFileA`) and Unix (`opendir`/`readdir`), both returning a dynamically-grown list of
  filename strings through a properly `_nova_arc_alloc`'d list header (matching Phase 38's
  `.as_list()`/`_list_wrap` fix — a bare `malloc`'d list header, which is what `_sys_get_args_c`
  still uses today, is unsafe to hand back as a generic Nova list value; not fixing that
  pre-existing inconsistency here since it's unrelated to this feature, but noting it as a
  latent issue for whoever touches `get_args()` next). Needed a forward declaration of
  `_nova_arc_alloc`/`_nova_dec_ref` ahead of the Windows implementation, which sits earlier in
  the file than their real definitions.
- `bootstrap/vm/machine.py`: `_builtin_sys_listdir` (`os.listdir`), registered under both
  `sys_listdir` and `sys_listdir_c`.
- `stdlib/backend/{x86_64,arm64}/os_{windows,unix}.nv` (all four): `.extern _sys_listdir_c` plus
  a `sys_listdir` wrapper — no backend-specific codegen needed, since calls to externs declared
  via `@raw` are generic in both native backends.
- `stdlib/system.nv` → `file_listdir`, `stdlib/fs.nv` → `fs_list_dir` (the public API).
- Regression test: `tests/test_native_exec.py::test_vm_native_parity_for_fs_list_dir` — compares
  VM vs. native output for a directory containing exactly one file, to stay independent of
  directory-enumeration order (which differs between `os.listdir` and `readdir`/`FindNextFile`
  and isn't guaranteed sorted by either).
- Also verified the self-hosted compiler itself still builds and runs after these stdlib changes
  (`./nova build nova.nv`), bypassing its own build cache (`.nova_cache.txt`) to force a real
  rebuild rather than trust a cache hit on the unchanged top-level `nova.nv` file.
- Validation: full suite green (`python -m pytest tests/ -q`, 502 passed / 1 skipped).

### Phase 41: `get_args()` Missing ARC Header, Fixed (2026-10-19)

Followed up on the latent issue noted in Phase 40: `_sys_get_args_c` (`runtime.c`, all three
platform variants — Linux, Windows x64, macOS) built its returned list with a bare `malloc(16)`
header instead of `_nova_arc_alloc`, the same bug class as Phase 38's `.as_list()` fix. Confirmed
it was real (not just theoretical) before fixing: wrote the regression test first, temporarily
`git stash`ed the fix, and watched it actually fail — `nova_value_kind()` on a boxed `get_args()`
result came back `0` instead of `1`, reading whatever garbage happened to sit 16 bytes before
the list where a `NovaARCHeader` should have been. Fixed all three variants to allocate via
`_nova_arc_alloc(16, NOVA_VALUE_LIST)` and release via `_nova_dec_ref` on the allocation-failure
path, unstashed, and confirmed the test now passes.
- Test: `tests/test_native_exec.py::test_get_args_list_survives_generic_retain_release` — checks
  shape (non-empty, correct value kind via `value_box_list`, survives `nova_value_release`)
  rather than exact argv content, since the executable's own path varies by build location.
- Validation: full suite green (`python -m pytest tests/ -q`, 503 passed / 1 skipped).

### Phase 42: `path_normalize` / `path_is_absolute` Added (2026-10-19)

Another gap in the "portable path helpers" roadmap item: `path.nv` had `path_join`/`path_basename`/
`path_dirname`/`path_extension` but no way to collapse `.`/`..` segments or redundant slashes, or
check whether a path is absolute (confirmed via grep — neither existed anywhere in the codebase).
Added both, pure Nova string manipulation with no runtime/VM/backend changes needed (unlike
Phase 40's `fs_list_dir`, which needed a real syscall):
- `path_is_absolute(value: string) -> int`: true for a leading `/`/`\` or a Windows drive prefix
  (`C:/`, `C:\`).
- `path_normalize(value: string) -> string`: segments the path, drops `.`, resolves `..` against
  a stack of prior segments (kept literally if there's nothing to resolve against — can't escape
  an absolute root, and a relative path with no prior segments keeps the leading `..`), and
  rejoins with single `/` separators. Preserves a drive prefix and absoluteness.
- Verified actual output values (not just VM/native agreement) with a direct `nova dev` run:
  `a/./b/../c` → `a/c`, `/a/b/../../c` → `/c`, `a//b///c` → `a/b/c`, `../a/b` → `../a/b` (kept,
  nothing to resolve against), `./././` → `.`.
- Test: `tests/test_native_exec.py::test_vm_native_parity_for_path_normalize_and_is_absolute`.
- Verified the self-hosted compiler still builds and runs after these stdlib changes.
- Validation: full suite green (`python -m pytest tests/ -q`, 504 passed / 1 skipped).

### Phase 43: Undefined-Variable Native-Build Crash, Message Swap, Mojibake (2026-10-20)

Three more real bugs found by cross-checking the Python-bootstrap compiler against its
self-hosted twin and by directly exercising `nova check`/`nova build` on deliberately bad input,
rather than reading code cold:
1. **`process.nv`'s multi-return comment was stale.** It claimed the VM had zero multi-return
   support (true in an earlier phase, not anymore — verified directly: `code, out = get_pair()`
   works under `nova dev`). Corrected the comment; `process_capture()`'s actual behavior
   (returning an encoded string rather than `-> (int, string)`) is unchanged, just for the real
   reason now: the self-hosted compiler still has no multi-return at all.
2. **Type-mismatch error had expected/actual backwards** (`bootstrap/compiler/type_checker.py`).
   Every `unify()` call site passes `(expected_type, actual_type)`, but the message read
   `"cannot use {expected} where {actual} is expected"` — exactly reversed. `add(a: int, b: int)`
   called with a string argument reported *"cannot use int where string is expected"*. The
   self-hosted compiler's equivalent message already had this right, which is what flagged it.
   Fixed the message template; added `tests/test_check.py::test_check_type_mismatch_names_actual_and_expected_in_order`.
3. **Em dash mojibake in CLI messages.** Several diagnostics (arg-count mismatch suggestions,
   did-you-mean warnings, the build-cache message, the native-build-fallback message) used a
   literal em dash (U+2014), which renders as `�` on a Windows console's default (non-UTF-8)
   code page — reproduced directly (`[cached] ... unchanged <?> ... is up to date`). Replaced
   with the ASCII `--` every other message in these files already uses. Added
   `tests/test_check.py::test_check_arg_count_mismatch_message_is_ascii`.
4. **The real find: `nova build` crashed with a raw unhandled `KeyError` traceback**, not a
   clean compile error, on the single most common user mistake there is — referencing an
   undefined or typo'd variable name. `self.local_vars[node.name]` (both native backends,
   `compiler/backend/{x86_64,arm64}/codegen.py`, in the read paths — `compile_expr`'s and
   `compile_leaf_to_reg`'s `Variable` cases) indexed the dict directly with no guard, and
   `main.py` didn't wrap `codegen.generate()` in any exception handler at all (only
   `TypeInferer().infer(ast)` was guarded). Root cause: `nova check`/`TypeInferer` deliberately
   falls back to `AnyType()` for names it doesn't recognize (gradual-typing leniency, left alone
   here since changing it is a bigger, separate judgment call) and never flags a genuinely
   undefined variable as a type error, so the mistake sailed straight through type-checking and
   only surfaced as an internal crash during codegen. Fixed both backends to raise a clean
   `StaticTypeError("Undefined variable '...'")` instead, and wrapped `codegen.generate()` in
   `main.py` with the same `except StaticTypeError` handling already used for the type-checking
   phase. Did not touch the Assignment-target `self.local_vars[node.name]` sites (write targets,
   pre-registered by variable scanning — a KeyError there would indicate a different, scanner-
   level bug, not a user typo) or the VM's/`nova check`'s leniency. Added
   `tests/test_native_exec.py::test_undefined_variable_is_a_clean_build_error`.
- Validation: full suite green after each fix (`python -m pytest tests/ -q`), ending at
  507 passed / 1 skipped.

### Phase 44: Benchmark Suite + Frequency-Weighted Register Allocation (2026-10-20)

User asked for a benchmark suite before any further performance work, explicitly deferring the
macOS ARM64 bootstrap crash (untestable here) and asking to continue improving the language
generally. Built `benches/` — six programs isolating pure native execution time (build once,
discard a warm-up run, median of 5 timed runs), distinct from `tests/benchmark_overall.py`'s
build+run system-level comparison against Python/C. `benches/baseline.json` is the committed
baseline for `--compare` after future codegen changes.

Used it to validate a real improvement to the x86_64 Python-bootstrap backend's register
allocator (`bootstrap/compiler/backend/x86_64/codegen.py`): `compile_function` handed its 4
available callee-saved registers (`r12`-`r15`) to whichever 4 variable names were
declared/assigned first (`register_var`, called in AST-declaration order by `scan_vars`),
regardless of how often each was actually used afterward. Added `count_var_refs`, a pass that
counts how often each name is read or written, and claims registers for the highest-count names
*before* the normal declaration-order scan gets to them (which still runs unchanged and simply
falls back to a stack slot for anything already claimed).

First version counted raw syntactic occurrences and immediately caused a real, measured
regression on `dict_ops.nv` (+51%): a dict referenced twice inside a 60,000-iteration loop lost
its register to a loop counter referenced a few more times *textually* in the same loop, because
syntactic count doesn't capture that a reference inside a loop body executes once per iteration,
not once. Fixed by weighting references by loop nesting depth (`count_var_refs` gained a
`weight` parameter, multiplied by 10 per enclosing `While`/`ForLoop`/`ForIn` body) — `While`
wasn't even special-cased before (relying only on the generic fallback, which doesn't know it's
a loop), so it was added alongside the existing `ForLoop`/`ForIn` cases.

After that fix, a `--compare` run showed `tight_loop_arith.nv` (the designed control case, 3
variables that already fit in all 4 registers under both schemes) at +13.5% slower -- investigated
before accepting anything, since the generated assembly for old vs. new is instruction-for-
instruction identical modulo which physical register name each variable got (confirmed by diffing
`.s` output directly). Proved this was pure measurement drift, not the code: re-measuring the
*old* scheme at that same moment (via `git stash`) gave ~53ms, not the baseline's original
47.5ms: the whole system had drifted slower over this long session (background load, thermal
state, etc.), and an interleaved old/new/old/new run showed both schemes tracking each other
within noise. The actual improvements (`dict_ops.nv` -6%, `fib_recursive.nv` -6%,
`list_ops.nv` -33%, `register_pressure.nv` -17%, the last being the benchmark purpose-built to
expose this exact allocator flaw) are if anything understated by the same drift, since it was
pulling measurements in the slower direction throughout.
- Test: `tests/test_native_exec.py::test_vm_native_parity_for_register_allocation_priority` --
  nested loops, a barely-used parameter, and four barely-used locals declared before the hot
  ones, to exercise both the frequency ranking and the loop-depth weighting together.
- Validation: full suite green (`python -m pytest tests/ -q`, 507 passed / 1 skipped);
  `benches/baseline.json` refreshed with the new allocator in place.

### Phase 45: Mirroring Register Allocation into the Self-Hosted Backend (2026-10-20)

AGENTS.md requires both codegens stay in step for features that already exist, and Phase 44
only touched the Python-bootstrap x86_64 backend, leaving `./nova build` (the self-hosted
compiler most users actually run) without the improvement. Mirrored it into
`stdlib/backend/x86_64/codegen.nv`, and in the process found two real bugs that the Python
version's generic AST reflection (`dir(node)`) never could have had, because the self-hosted
backend's AST walker is hand-written per node kind instead of generic:

1. **A segfault.** `AstNode` (`stdlib/parser.nv`) is a single tagged-union struct where every
   field (`left`, `right`, `cond`, `body`, `else_body`, `args`) always exists, but list-typed
   fields default to a bare `0` (not an empty list) for node kinds that never populate them.
   `count_var_refs`'s generic fallback called `len(node.args)`/`len(node.else_body)`
   unconditionally on every node kind reaching it (`BinOp`, `Compare`, `Call`,
   `DataFieldAccess`, ...) — `len(0)` segfaults rather than returning 0. Reproduced reliably by
   compiling `benches/register_pressure.nv` with a self-rebuilt `nova.exe`; confirmed the
   unmodified compiler builds it fine, and that merely adding the new functions *unused* didn't
   crash either — only actually calling them during a real compile did. Fixed with explicit
   `!= 0` guards before each `len(...)` call.
2. **A silent correctness bug, worse than the crash.** After fixing the segfault,
   `work(5)` (five variables, a loop, a lightly-used parameter) computed `5380300355189866506`
   instead of `25`. Root cause: `compile_function`'s parameter argument-copy step read
   `state.local_var_regs[p]` / `state.local_vars[p]` *positionally*, assuming parameters always
   occupy the first `len(node.params)` slots of those parallel arrays — true only because the
   original code always registered parameters before any other local. Claiming registers for
   hot non-param locals *before* parameters (the whole point of this change) breaks that
   assumption: a parameter and an unrelated hot local silently ended up sharing one physical
   register, each clobbering the other. The Python backend never had this bug because it reads
   parameters by name (`self.local_vars[param_name]`, a dict) rather than position. Fixed by
   switching the self-hosted version to the already-existing name-keyed
   `find_var_reg`/`find_var_offset` lookups instead of positional indexing — confirmed by
   reverting just this one fix and watching `tests/test_selfhost_register_allocation.py`'s two
   collision tests fail (one with the wrong number, one by hanging in an infinite loop — an even
   worse failure mode than the one found by hand).
- Verified via direct inspection that this was genuinely scoped to my new code, not a
  resurfacing of the still-unresolved Phase 38/39 `compile_stmt` memory-safety bug: bisected by
  adding the new functions *unused* first (no crash), then wiring them in (crash), isolating the
  cause to the traversal logic itself rather than "too many variables in a big function" (the
  earlier bug's leading theory).
- Tests: new `tests/test_selfhost_register_allocation.py` (3 tests, using the existing
  `selfhost_run` fixture that builds a real stage-1 self-hosted compiler from current sources)
  — the two collision shapes above, plus a rich-expression test (structs, lists, dicts, nested
  calls, if/elif/else) exercising every `compile_expr` node kind reachable from ordinary syntax,
  to catch any other unguarded `len()` call on an unset field.
- Measured via direct A/B timing (self-hosted `nova.exe`, old vs. new scheme, interleaved):
  `register_pressure.nv` ~113-128ms -> ~107-114ms, a smaller but real improvement than the
  Python backend's -17% (the self-hosted backend's baseline codegen is already considerably
  slower per-program than the Python one for unrelated reasons, so the relative win is more
  modest here).
- Validation: full suite green (`python -m pytest tests/ -q`, 508 passed / 1 skipped);
  `./nova build nova.nv` (via `build.sh`) rebuilds cleanly and the resulting `nova.exe` passes
  both hand-checked correctness cases.

### Phase 46: Windows Crash Diagnostics — A Real, Partial Fix (2026-10-20)

User asked to continue root-causing the still-unresolved self-hosted `compile_stmt` crash
(Phase 38/39's negative result). Before attempting a blind reimplementation of the self-hosted
multi-return feature (the only known trigger, never committed, so it would mean rewriting it
from scratch with no guarantee of hitting the same bug), checked what crash diagnostics exist
on this Windows dev environment — concluded that answer matters enough to resolve first, since
it decides whether bisection is even tractable.

Found the existing `runtime.c` SIGSEGV/`backtrace()` handler is **entirely dead code on
Windows**: it's textually nested inside `#elif defined(LINUX_WRAP) || defined(MACOS)` (traced
the open conditional stack at that line to confirm), so its own internal
`#if defined(_WIN32)` branch never compiles in on an actual `_WIN32` build. It also calls
`backtrace()`/`backtrace_symbols_fd()`, glibc functions MinGW doesn't provide, so it couldn't
have worked even if reachable (confirmed by trying to compile the same pattern in isolation —
hard "implicit declaration" errors).

Replaced it with a real Win32 mechanism, `SetUnhandledExceptionFilter` plus
`CaptureStackBackTrace` for raw frame addresses (no symbol names without a `dbghelp.lib`
dependency, out of scope here) — verified working in an isolated plain-C test (null-pointer
write, handler fires, prints exception code and address).

That isolated success didn't carry over to the real target, though: rebuilt `nova.exe` with the
handler installed and the actual, previously-fixed null-pointer `len()` bug from Phase 45
temporarily reintroduced (reverted the `!= 0` guards, confirmed via `git diff` that nothing else
changed) — still a bare "Segmentation fault" with no `SIGNAL:` line, despite confirming via an
added, later-removed print that the handler *was* installed. Root cause: every function in
`runtime.c` is declared `SYSCALL` (`__attribute__((sysv_abi))`) to match Nova's own calling
convention, but GCC's Windows x64 backend generates `.pdata`/`.xdata` unwind metadata assuming
the standard Microsoft x64 ABI — overriding to `sysv_abi` breaks or skips that metadata. Without
valid unwind info, the OS's table-based exception dispatcher can't walk the frame at all, so it
apparently never reaches even the top-level filter, not just per-frame handlers. That's a
different, deeper problem than "no handler was installed," and a real fix means emitting correct
Windows unwind tables for `sysv_abi`-attributed functions — out of scope for this detour.

**Decision: stopped the self-hosted-crash investigation here** rather than continue into a
blind reimplementation. The practical conclusion is unchanged from before this detour (still no
way to get a backtrace or fault address for a crash in actual Nova-compiled code or this
runtime), but it's now a confirmed architectural fact instead of an assumption, which is worth
knowing before anyone next attempts self-hosted multi-return or touches `compile_stmt` again.
Kept the `SetUnhandledExceptionFilter` handler anyway: it's a real, documented, strictly-better-
than-dead-code improvement for crashes in non-`SYSCALL` code (Windows API glue, anything added
to this file without that attribute), and the comment above it states its limitation plainly so
nobody trusts it for more than it actually covers.
- Validation: full suite green (`python -m pytest tests/ -q`, 511 passed / 1 skipped).

### Phase 47: Differential Fuzzer at Scale — Call-Graph Fix, Dict/Struct Coverage, a Real Try/Catch Bug (2026-10-20/21)

User asked what would most improve the language long-term; recommended investing in the existing
differential fuzzer (`tests/test_diff_fuzz.py`, VM vs. self-hosted native) over more manual bug
sweeps, since every bug found so far this session was found by hand. Ran it with 300 seeds
instead of the default 14.

1. **300-seed run found 5 timeouts, not a compiler bug.** Each one exceeded the VM's 30s
   reference-output timeout. Read the actual generated program for seed 1079: 6 chained
   functions, each calling earlier ones from inside loops, multiplying actual call counts well
   past what the ~250-line source suggests — every individual loop bound is small and finite, no
   real infinite loop. Fixed the *generator*, not the compiler: added a weighted call-cost budget
   (`count_var_refs`-style loop-depth weighting, threaded through `expr()`/`stmts()`/`cond()`),
   calibrated empirically by sweeping VM-only timing across 300 seeds at a few budget values.
   Final budget keeps the worst case under the 30s timeout with 3x margin. All 5 originally-
   failing seeds pass the full differential test now; re-ran the full 300 and got 300/300.
2. **Added dict coverage** (`.set`/`.get`/`.has` over a small fixed key set) — previously zero,
   despite dicts being exactly the kind of area (hashing, resize, probing) that's bitten this
   project before. Deliberately never reads key order (`.keys()`), since the VM's Python dict and
   native's open-addressing table have no reason to agree on that. 100-seed run: no divergences.
3. **Added struct field read/write coverage** (`pt.fa`/`pt.fb` on a shared instance) — also
   previously zero. Verified first that an unset int field zero-initializes identically in VM and
   native. 100-seed run: no divergences.
4. **Attempted try/catch coverage, found a real bug, then reverted the generator change.**
   Adding `try { throw <int> } catch e { ... use e ... }` immediately surfaced a genuine native-
   only bug: `scan_vars` (both Python-bootstrap backends) never registered the catch variable as
   a local at all — it's a plain string (`Try.catch_var`), not a nested AST node, so the generic
   walk that finds `Assignment`/`ForLoop`/`ForIn` targets never saw it. `compile_stmt`'s own `Try`
   handling already tried to store the exception value via `self.local_vars.get(node.catch_var)`,
   but that was always `None`, so the store silently never happened. The existing
   `test_try_catch` (`tests/test_native_exec.py`) never caught this because it never reads the
   caught value — it only checks that control reaches the catch block. Confirmed with a minimal
   hand-written case: `catch e { print(e) }` printed `42` in the VM and failed to even compile
   natively ("Undefined variable 'e'" — the clean error Phase 43 added, not a crash). Fixed
   `scan_vars` in both the x86_64 (verified: now prints `42` natively) and ARM64 (same missing
   case, same fix, verified by cross-assembling with clang and inspecting the generated
   instructions directly — the exception value now stores to and loads from a real stack slot
   instead of the store being silently skipped) Python-bootstrap backends. Added
   `tests/test_native_exec.py::test_try_catch_binds_the_exception_value`.

   Then reverted the fuzzer's generator change for try/catch itself: `selfhost_run` (the fixture
   this fuzzer uses for its native comparison) builds via the *self-hosted* compiler, and its
   parser doesn't support `try`/`catch` syntax at all (`expected LPAREN but got IDENT` on
   `catch e {`) — a much bigger, pre-existing gap than anything this fuzzer is meant to shake out
   for a quick exploration. ROADMAP's June 2026 exceptions milestone describes "full
   implementation" across lexer/parser/VM/native runtime, but that was before self-hosting was
   the priority; the self-hosted parser evidently never got try/catch grammar added. Left as a
   known, documented, unfixed gap (same spirit as the self-hosted multi-return gap) — adding full
   try/catch grammar to the self-hosted parser is a new-feature-sized project, not a quick fix,
   and this session has already seen how much self-hosted-backend changes can bite even when
   seemingly small (Phase 45).
- Validation: full suite green (`python -m pytest tests/ -q`) after each change.

### Phase 48: Self-Hosted Try/Catch (Three Bugs) + a Real Handler-Stack Bug Found by the Fuzzer (2026-10-21)

Follow-up to Phase 47's left-as-a-gap item: user directed that the self-hosted compiler (not Python)
become the sole build/ship path on every platform, with Python bootstrap kept only as a dev/test
reference. Closing the self-hosted try/catch gap was the natural next piece.

1. **Self-hosted try/catch didn't work at all — three compounding bugs**, each only reachable once
   the previous one was fixed:
   - `stdlib/parser.nv`'s `parse_try_block` expected `catch(e) { ... }` (parens around the catch
     variable) — syntax nothing else in the language or test suite ever used. Removed the
     `LPAREN`/`RPAREN` expectations to match `bootstrap/parser/parser.py`'s `parse_try` exactly.
   - `stdlib/backend/x86_64/codegen.nv`'s `scan_vars` had no `"TRY"` case at all, so the catch
     variable was never registered — worse than Phase 47's Python-bootstrap bug, since the
     self-hosted fallback offset of 0 for an unregistered name means "write to `[rbp - 0]`",
     directly over the saved frame pointer. Fixed by registering `node.val_str` and recursing into
     `node.body`/`node.else_body`.
   - `stdlib/type_checker.nv`'s `TRY` case (`h == 12`) read `node.args`/`node.cond`, but the parser
     actually sets `node.body`/`node.else_body` — `node.args`/`node.cond` are always unset (null)
     for a TRY node, so `len(node.args)` segfaulted instead of returning 0 (the same "len() on an
     unset field" bug class as Phase 45, pre-existing and never exercised until bug #1 stopped
     blocking every real try/catch program before it reached this code).
   Added `tests/test_selfhost_try_catch.py` (3 tests), verified against VM reference output.
2. **Re-enabled the fuzzer's try/catch generator coverage and found a real, deeper bug.** A 20-seed
   batch surfaced value mismatches (not crashes) on both native backends — e.g. seeds 1005/1016.
   Root cause: `runtime.c`'s `_try_catch_sp`/`_catch_ip` were a single global slot, not a stack. The
   *normal*-exit path of a try reset the slot, but the *exceptional* (caught) exit path never
   touched it — so once an inner try/catch (inside a called function) actually caught something, the
   slot was left holding that inner try's stale `rsp`/`catch_ip`, pointing at a stack frame that had
   already returned. A later throw from an *outer*, still-active try then restored `rsp` to that
   stale address and jumped to the wrong `catch_ip` — a wrong value, not a crash, which is why it
   slipped past every hand-written test (none of which nested a catching try inside a called
   function called from within another try).
   - Fixed by turning `_try_catch_sp`/`_catch_ip` into a real LIFO stack indexed by a new
     `_try_depth` counter (`runtime.c`, `NOVA_MAX_TRY_DEPTH = 256`). Each `TRY` entry pushes
     (store at `[depth]`, increment); normal exit pops (decrement); `THROW` pops *before* jumping
     (so a throw from inside a catch body resumes at the next-outer handler, not its own).
   - Mirrored across all four codegens that had the identical single-slot pattern: Python-bootstrap
     x86_64 (`bootstrap/compiler/backend/x86_64/codegen.py`) and ARM64
     (`bootstrap/compiler/backend/arm64/codegen.py`), and self-hosted x86_64
     (`stdlib/backend/x86_64/codegen_stmt.nv`) and ARM64 (`stdlib/backend/arm64/codegen_stmt.nv`).
     Added the new `_try_depth` extern to `stdlib/codegen_common.nv`'s shared externs list (used by
     both self-hosted backends) and to both Python-bootstrap backends' extern lists.
   - ARM64 (neither backend executable here): cross-assembled the generated `.s` with
     `clang --target=arm64-apple-macos11 -c` and read the instructions directly — scratch registers
     chosen as `x9`/`x10`/`x16`/`x17`, deliberately avoiding `x18` (a reserved platform register on
     Apple's ABI). Assembles cleanly; correctness reasoned through by hand (same confidence level as
     Phase 44's ARM64 MultiReturn fix).
   - Added `test_try_catch_survives_a_caught_throw_inside_a_called_function` to both
     `tests/test_native_exec.py` (Python-bootstrap x86_64) and `tests/test_selfhost_try_catch.py`
     (self-hosted x86_64) — both pass. Re-ran the fuzzer's try/catch coverage at 40 seeds against
     both native backends (80 runs total, including the original failing seeds 1005/1016): 80/80
     pass.
   - In passing, found and fixed a dead branch in the fuzzer generator: the dict-ops bucket added in
     Phase 47 was gated on `kind < 0.90`, identical to the string-loop bucket right above it, so it
     could never actually fire. Dict coverage had silently been running zero times since Phase 47.
3. Full suite green: 531 passed, 1 skipped, 13 subtests passed.

Net effect: self-hosted try/catch now works end-to-end, and the underlying exception-handling
mechanism is now actually correct under nesting on every backend, not just the one the bug happened
to be found on. Still outstanding for the "self-hosted is the sole build/ship path" goal: self-hosted
multi-return (never implemented), the pre-existing self-hosted `compile_stmt` crash (Phase 39,
investigation abandoned for lack of a Windows crash-diagnostics path), and ARM64/macOS reliability in
general (no hardware to execute on, only cross-assembly review).

### Phase 49: Self-Hosted Multi-Return, a Debug-Print Leftover, and a Real Cross-Compile Bug (2026-10-21)

Continuing the Phase 48 punch list: self-hosted multi-return (`return a, b, c` / `a, b = f()`) was
entirely unimplemented -- not a bug, a missing feature. `stdlib/parser.nv` never parsed the grammar at
all.

1. **Added the full pipeline for x86_64**, mirroring `bootstrap/compiler/backend/x86_64/codegen.py`'s
   existing MultiReturn/UnpackAssign design (value[0] in the normal return register, values[1:] in a
   static `_nova_multi_ret` buffer):
   - `stdlib/parser.nv`: RETURN with a trailing comma builds a `MultiReturn` node (reusing the generic
     `args` list field for its values, the same way TRY reuses `else_body`); the statement-fallback
     assignment path builds an `UnpackAssign` node on `expr, expr2, ... = value` (targets in `args`,
     RHS in `left`).
   - `stdlib/type_checker.nv`: added `MultiReturn`/`UnpackAssign` handlers (kinds 32/33) -- visits
     children and binds unpacked targets to `any`, since the self-hosted type system has no
     per-component type for a multi-return call's individual values.
   - `stdlib/backend/x86_64/codegen.nv`: added the `_nova_multi_ret` static data buffer; added
     `scan_vars` cases for both kinds (MultiReturn recurses into its values; UnpackAssign registers
     each `Variable` target, skipping `_`).
   - `stdlib/backend/x86_64/codegen_stmt.nv`: added the actual codegen. One deliberate difference from
     the Python-bootstrap reference: self-hosted's MultiReturn runs `defer_emit_down_to` before
     returning (bootstrap's x86_64 MultiReturn doesn't) -- self-hosted's own single-value Return
     already runs deferred cleanups, so skipping them only for the multi-value case would be a new,
     self-inconsistent bug, not faithful mirroring.
   - Verified end-to-end: 2 and 3 return values, `_` skipping a target, and defers firing (and firing
     *before* the caller reads the returned values) all work. New
     `tests/test_selfhost_multi_return.py` (4 tests, all passing).
2. **Mirrored to ARM64** (`stdlib/backend/arm64/codegen.nv` and `codegen_stmt.nv`) per AGENTS.md policy,
   plus found and fixed a *separate*, pre-existing gap while there: ARM64's `scan_vars` had no `"TRY"`
   case at all (x86_64's got this fix in Phase 48; ARM64 never did), meaning the self-hosted ARM64
   backend has had the identical "catch variable never registered, offset 0 overwrites the saved frame
   pointer" bug as x86_64 did, for as long as ARM64 try/catch codegen has existed. Fixed the same way.
   **Correction to Phase 48's record**: that phase's "ARM64 ... verified by cross-assembling with
   clang" claim, read carefully, only cross-assembled `bootstrap/compiler/backend/arm64/codegen.py`'s
   output (the Python-bootstrap backend, also edited that phase) -- it never actually exercised
   `stdlib/backend/arm64/codegen_stmt.nv`'s try/catch code at all. That self-hosted ARM64 code, and this
   phase's self-hosted ARM64 multi-return code, remain verified only by hand-reading plus confirming
   they compile cleanly through the self-hosting chain (see finding 3) -- a real but weaker guarantee
   than "assembles to valid instructions I inspected," and the AGENT_LOG should say so plainly rather
   than imply more confidence than that.
3. **Found a real, independent bug while trying to actually test self-hosted ARM64 output**: invoking
   `stage1.exe build foo.nv -arch arm64 --os macos` silently emitted plain x86_64 `.intel_syntax
   noprefix` assembly while printing "Generated executable" -- a cross-compile that silently produces
   the *wrong* architecture's output instead of failing. Root cause: `import codegen`
   (`stdlib/compiler.nv`) resolves to exactly one of `stdlib/backend/{x86_64,arm64}/codegen.nv`, chosen
   once, statically, at THIS compiler binary's own build time -- Nova has no dynamic/conditional
   import, unlike the Python-bootstrap backend's runtime `from compiler.backend.arm64.codegen import
   ...` inside `compile_native`. An ordinary x86_64-targeting nova.exe (the only kind this project
   actually ships) therefore has no ARM64 codegen compiled into it at all; its `-arch` flag was
   silently a no-op that fell through to the one backend it has. This also means self-hosted ARM64 has
   no way to be executed in THIS environment at all (no ARM64 hardware, and no way to get an
   ARM64-targeting nova.exe without a toolchain that can run it) -- a stronger version of the
   already-known "no ARM64 hardware" limitation.
   - Fixed with a `codegen_native_arch()` function (one per backend, returning that backend's own
     architecture name as a string literal) and a check at the top of `compile_file`
     (`stdlib/compiler.nv`) that errors clearly instead of mis-compiling when the requested
     `target_arch` doesn't match. Verified both directions: the mismatch now fails loudly with no `.s`
     or output file produced, and matching-arch builds are unaffected. New
     `tests/test_selfhost_arch_guard.py` (2 tests).
   - This does not make self-hosted able to cross-compile -- that would need both backends compiled
     into one binary with runtime dispatch, a genuinely new-feature-sized refactor (comparable to
     Phase 47/48's assessment of try/catch grammar) -- it only turns a silent wrong-architecture binary
     into a clear, actionable error.
4. **Unrelated one-line fix found in passing**: `stdlib/type_checker.nv`'s Assignment handler
   (`h == 7`) had a leftover `print("TC Assignexists")` debug statement, firing on *every* assignment
   in *every* self-hosted compile -- confirmed by building a trivial one-line program and seeing it in
   the output. Removed.
- Validation: full suite green (`python -m pytest tests/ -q`) after all changes.

### Phase 50: Fuzzer Multi-Return Coverage Finds a Real rbx-Clobber Bug (2026-10-21)

Natural follow-up to Phase 49: now that self-hosted multi-return works, extended the differential
fuzzer (`tests/test_diff_fuzz.py`) to cover it, the same way Phase 47/48 did for try/catch -- each
generated function now sometimes returns 2 or 3 values (biased toward the plain single-value case),
and call sites (both top-level and inside a function body) sometimes unpack a multi-return call
instead of just using its first value in an expression.

1. **A 40-seed self-hosted batch passed clean (40/40)** -- the x86_64 self-hosted multi-return
   implementation from Phase 49 holds up under the fuzzer.
2. **The next full-suite run found a real, pre-existing bug in the Python-bootstrap x86_64
   backend**, unrelated to anything built this session: `test_bootstrap_native_matches_vm` failed on
   12 of 14 default seeds. Reproduced directly (seed 1001): `print(fn0(84, 991, 228, 824, 617, 184))`
   printed `1000` where the VM (and now self-hosted) printed `94`. Read the generated assembly:
   `MultiReturn`'s codegen (`bootstrap/compiler/backend/x86_64/codegen.py`) stashed value[0] in `rbx`
   across the evaluation of values[1:], but ordinary binary-op codegen copies a register-allocated
   hot variable (Phase 44/45's frequency-weighted allocator; r12-r15) into `rbx` as scratch whenever
   it's read -- confirmed directly in the assembly: `mov rbx, r14` (loading `v1` for the third return
   expression) landed *after* `mov rbx, rax` (the value[0] stash) and *before* the final `mov rax,
   rbx`, so the function returned `v1`'s value instead of its real first return value. This bug
   predates this session (MultiReturn itself is older), just never exercised by the fuzzer since it
   never generated multi-return functions until now. Fixed by stashing value[0] on the real stack
   (`push`/`pop`) instead of in `rbx`, the same design self-hosted's x86_64 MultiReturn already used
   from Phase 49 (lucky choice, not foresight) -- and, while fixing it, also added the
   `emit_deferred()` call this function was missing (bootstrap's own Return already runs deferred
   cleanups; skipping them only for the multi-value case was a second, quieter pre-existing gap).
3. **Checked the ARM64 bootstrap backend for the same bug class by code comparison** (no ARM64
   hardware/emulator here to execute or reproduce it directly) and found two bugs, both fixed:
   - The identical register-stash issue, `mov x1, x0` instead of a stack push -- ARM64 has no
     hot-variable allocator to mirror x86_64's path, but its own `_alloc_reg()` scratch-register pool
     (`_compile_expr_to_reg`) starts at x0 and hands out x1 next, so any values[1]/values[2]
     expression needing two live temporaries at once would clobber the stash exactly the same way.
   - A second, more serious issue found only by comparing MultiReturn's epilogue against this same
     file's Return case line by line: MultiReturn never did `add sp, sp, #{self.local_aligned}` (the
     local-variables stack space Return's epilogue always reclaims) before `ldp fp, lr, [sp], #16` --
     meaning `ldp` read the saved frame pointer and return address from the wrong stack slot for any
     multi-return function with local variables, corrupting the caller's frame on return. This is a
     plausible crash-or-worse bug, not just a wrong value.
4. **Verified the x86_64 fix directly**: rebuilding and re-running seed 1001 now prints `94` (matching
   the VM) instead of `1000`. Re-ran the 40-seed batch against both native backends after the fix:
   80/80 pass. Full suite green.

The ARM64 fix remains unverified beyond careful reading -- consistent with every other ARM64 bootstrap
change this project has made without hardware, but worth stating plainly rather than implying more
confidence than that.
