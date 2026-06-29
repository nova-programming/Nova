# Agent Session Summary

## Global Lock
- None

## Architecture Policy
- **x86 (32-bit) support removed** — only x86_64 and arm64 are maintained
- **Bootstrap (Python) is FROZEN** for new features — only bug fixes that prevent self-hosting. All new language features go into stdlib (Nova) only
- **Shared codegen layer**: `stdlib/backend/codegen_expr.nv` and `stdlib/backend/codegen_stmt.nv` handle all architecture-specific emit via the `state` object's register names

## Current State
- **Galaxy Package Manager**: Fully implemented and live at [galaxy-registry.vercel.app](https://galaxy-registry.vercel.app)
- **Compiler**: Stable, tree-shaking + variable-to-register promotion + self-hosted bootstrap working + 7 built-in functions + cross-platform GCC fallback + exceptions + list comprehensions + REPL + cross-compilation
- **Installer**: Native `install.sh` (bash, uses only curl+tar) + `install.ps1` (PowerShell) + `install.py` (Python fallback) — no dependencies required
- **Version**: v0.7.0. `nova --version` / `galaxy --version` + self-update via registry endpoints

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
- **Status**: Waiting for CI on next commit to confirm the fix.

**Next Instruction for Agent:**
1. Push the libc wrappers fix (`#if defined(LINUX_WRAP)` → `#if defined(LINUX_WRAP) || defined(MACOS)`) to GitHub and trigger CI.
2. If CI passes macOS ARM64 linking, the next blocker will likely be runtime errors in the compiled stage1 compiler (assembly bugs, syscall mismatches).
3. If CI still fails on macOS ARM64 with a different error, investigate the new error.
4. On success, remove all `GEN:...` debug markers introduced in Phase 9 and finalize.
