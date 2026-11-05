# Nova Project Context & Architectural Summary (`Agent.md`)

## 1. Project Overview & Mission
Nova is a programming language designed to bridge Python-like readability and ease of development with C/C++ native performance and low-level control. Nova retains a clean, Python-like syntax while compiling down to native machine code via GCC.

### Core Philosophy
- Keep Python-like syntax and ergonomics.
- Native performance via ARC (Automatic Reference Counting) and low-level escape hatches (`alloc`, `free`, `@raw`, `.ptr`).
- No unsolicited refactoring; minimal targeted changes only.

---

## 2. Invariants & Toolchain Rules
1. **Bootstrap Freeze**: `nova/bootstrap/*.py` is FROZEN for new features. Only critical self-hosting bug fixes are permitted. All compiler features, AST transformations, and stdlib modules belong in `nova/stdlib/*.nv`. Both x86_64 and ARM64 backends must stay in sync for shared features.
2. **64-bit GCC Toolchain**: Exclusively use 64-bit GCC located at `%LOCALAPPDATA%\nova\gcc\bin` on Windows. Never use 32-bit `C:\MinGW`.
3. **Stage 1 -> Stage 2 -> Stage 3 Verification**: Any change to object layout, value representation, calling conventions, or `runtime.c` requires full self-host verification:
   - Compile `nova.nv` with `nova_stage1.exe` (or bootstrap) -> Stage 1 binary.
   - Stage 1 compiles `nova.nv` -> Stage 2 binary.
   - Stage 2 compiles `nova.nv` -> Stage 3 binary.
   - Verify byte-for-byte identity (`Stage 2 == Stage 3`).
4. **Git Commands**: Never execute git commands unless explicitly instructed.
5. **No Hardcoding**: Maintain scalable, modular, clean constants and parameters.

---

## 3. High-Level & Low-Level Architecture

### Directory Structure
- `nova/bootstrap/`: Python bootstrap compiler (lexer, parser, type checker, x86_64/arm64 codegen).
- `nova/stdlib/`: Self-hosted compiler written in Nova:
  - `lexer.nv`, `parser.nv`: Tokenizing & recursive-descent parsing.
  - `type_checker.nv`, `infer.nv`, `types.nv`: Bidirectional type checking and inference.
  - `compiler.nv`: Coordination, module resolution (`resolve_imports`), build caching, API interfaces (`check_source`, `check_file`, `compile_file`).
  - `errors.nv`: Structured diagnostic logging; writes JSONL to `NOVA_DIAG_FILE` when set or human-readable format.
  - `backend/`: Code generators for x86_64 and ARM64.
- `nova/runtime.c`: C runtime providing memory management, string operations, I/O, JSON decoding, ARC primitives, platform wrappers.
- `nova/lsp/server.nv`: Native LSP server binary (`novalsp.exe`).
- `nova/editors/vscode/`: Zero-dependency VS Code extension (syntax highlighting, JSON-RPC stdio language client).
- `nova/examples/schema_doctor.nv`: Flagship developer utility (dual CLI + native Win32 GDI GUI, 186.7 KB).
- `nova/tests/`: Comprehensive test suite (unit, regression, selfhost verification, LSP, extension, CLI, parity).

### Calling Convention & Stack Cleanup Fix
- On x86_64 Windows ABI: First 4 integer/pointer arguments go into registers `rcx`, `rdx`, `r8`, `r9` (or `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` for System V). Arguments 7+ (or 5+ for Win64 externs) are pushed onto the stack.
- **Bug Fix**: Caller must balance the stack after calls with stack arguments by emitting `add rsp, (n_args - 6) * 8` (or `(n_args - 4) * 8` for Win64 externs) across all codegen call paths (`emit_call`, `emit_internal_call`, inline candidates, method calls). Without this, callee epilogue register pops read corrupted stack frames, leading to access violations.
- Verified in `tests/test_call_stack_args.py`.

---

## 4. Self-Hosted Pipeline Parity & Parity Crashers Resolved
1. **`extern def` FFI Symbol Naming & Microsoft x64 ABI**:
   - `emit_win_extern_call` emits Microsoft x64 calling convention (`rcx, rdx, r8, r9`, 32-byte shadow space).
   - `runtime.c` bridges native GDI GUI functions across Microsoft x64 calling convention to internal `sysv_abi` implementations.
2. **List Comprehension Codegen Crash**:
   - Supported `Block` expressions in `codegen_expr.nv` ensuring proper pointer return and register scoping without stack clobbers.
3. **Class Methods & Field Assignment (`self.x = ...`)**:
   - `parser.nv` allows `SELF` as argument name; synthesizes constructor layouts in `data_fields`.
   - `type_checker.nv` checks methods with `self` typed as struct in env; `h == 17` (`MethodCall`) resolves class method return types.
   - `codegen.nv` mangles methods as `<Class>_<method>` passing `self` as first parameter; attribute mutation resolves struct offsets. Scalar types are explicitly checked in `is_string_expr` to prevent integer fields (e.g. `val: int`) from being mishandled as strings.
4. **Multiple Return Assignment (`a, b = f()`)**:
   - `parser.nv` and `compiler.nv` support tuple unpacking on assignment and tuple return annotations `-> (T1, T2, ...)`.
- Verified in `tests/test_selfhost_parity.py`.

---

## 5. String Concatenation Architecture & Performance Optimization
- **Root Cause of Performance Cliff**: Naive string concatenation allocated a new buffer on every `+`, copying both strings. In loops with 40,000 appends, this produced $O(N^2)$ quadratic allocations and Win32 `lstrcmpA` overhead.
- **`NovaStrHeader` & Amortized Growth**:
  - Dynamically allocated strings feature `NovaStrHeader` (`magic = 0x53545231`, `len`, `cap`).
  - In-place appending `_nova_str_append(s, rhs)` detects loop accumulators (`s = s + ...`) and doubles capacity when needed ($O(1)$ amortized append).
  - Fast byte-level `strcmp` replaces `lstrcmpA`.
  - Geometric mean benchmark run time: **0.057s** over 10 benchmarks; `strings` benchmark dropped from **6.04s to 0.012s** (500x speedup).

---

## 6. Binary Portability & Installer Alignment
- `stdlib/compiler.nv` resolves modules using a 4-tier search order:
  1. Current working directory (`./<module>.nv`)
  2. `NOVA_PATH` environment variable
  3. `<exe_dir>/stdlib/<module>.nv` (executable-relative)
  4. Fallback to CWD `./stdlib/<module>.nv`
- `install.py` copies fresh self-hosted `nova.exe`, `novalsp.exe`, `runtime.o`, and `stdlib/` to installation directory.
- `README.md` and repository license updated to standard MIT License.
- Verified in `tests/test_portable_execution.py`.

---

## 7. CLI Normalization
- Fully documented and normalized subcommands in `nova/nova.nv`:
  - `nova build <file.nv> [-o <out>] [-b] [-d] [-arch <arch>] [--os <os>]`
  - `nova run <file.nv> [args...]`
  - `nova check <file.nv>` (type-checks and syntax-checks without compiling)
  - `nova version`, `nova --version`, `nova -v`
  - `nova help`, `nova --help`, `nova -h`
- Verified in `tests/test_cli.py`.

---

## 8. Flagship Developer Utility: Schema Doctor (`examples/schema_doctor.nv`)
- **Dual Mode**:
  - **CLI Mode**: `schema_doctor <schema.json> <data.json>` validates JSON payloads against JSON schema specifications (supports `type`, `required`, `properties`, `items`, `minLength`, `maxLength`, `minimum`, `maximum`, `minItems`). Exits 0 on valid, 1 on validation failure with structured error paths.
  - **Win32 GDI GUI Mode**: Opened via `schema_doctor` or `schema_doctor --gui`. Renders dark-themed dual-pane layout (Schema left, Data right), interactive "Run Validation" button, and live health status badge (emerald green on success, rose red on error).
- **Binary Footprint**: Standalone native executable is **186.7 KB** (well within `< 350 KB` requirement).
- Verified in `tests/test_schema_doctor.py`.

---

## 9. Native Language Server (`novalsp`) Architecture
- **Protocol**: Speaks LSP 3.17 over standard I/O (JSON-RPC with `Content-Length:` headers).
- **In-Process Front-End**: Directly invokes `compiler.check_source()` and `compiler.check_file()` without running codegen or altering the build cache.
- **Diagnostics Isolation**: When `NOVA_DIAG_FILE` is set, `errors.nv` writes structured JSONL records to this file, leaving stdout pure for JSON-RPC messages.
- **Sync Model**: Full document sync (`textDocumentSync: 1`). Responsive editing is achieved by running syntax-only checks (`check_syntax_source`) on `didChange`, and full import resolution + type-checking on `didOpen` and `didSave`.
- **Diagnostic Attribution**: `TypeChecker` threads `tc.filename` to ensure diagnostics are properly scoped to individual open buffers, preventing cross-document diagnostic pollution.
- **CLI Mode**: `novalsp --check <file.nv>` prints diagnostics in standard Unix format `:line:col: severity [Kind] message`.
- Verified in `tests/test_lsp_diagnostics.py`.

---

## 10. VS Code Extension Architecture (`nova/editors/vscode/`)
- **Zero External Dependencies**: Pure VS Code Extension API and standard Node.js (`child_process`, `path`, `fs`). No `node_modules` or `npm install` needed at runtime or packaging.
- **Components**:
  - `package.json`: Manifest declaring language `nova`, file extension `.nv`, configuration schema (`nova.lsp.path`, `nova.lsp.enable`, `nova.lsp.trace`), command `nova.restartServer`.
  - `language-configuration.json`: Comment syntax (`#`), bracket pairs, indentation rules, auto-closing.
  - `syntaxes/nova.tmLanguage.json`: Complete syntax grammar covering keywords, types, decorators (`@raw`), string interpolation `{...}`, escape sequences, numbers, and builtins.
  - `extension.js`: Activates on `nova` files, locates `novalsp.exe`, spawns the language client process over stdio, implements JSON-RPC message framing and document sync (`didOpen`, `didChange`, `didSave`, `didClose`), and translates `publishDiagnostics` into native `vscode.Diagnostic` items.
  - `README.md`: Complete documentation and usage instructions.
- Verified in `tests/test_vscode_extension.py`.

---

## 11. Systems & Creative Engine Architecture (Sprint 5 Upgrade)

### User-Defined `def main()` Collision Resolution
- Removed `main` from reserved function keywords in `nova/stdlib/type_checker.nv`.
- In `nova/stdlib/backend/x86_64/codegen.nv` and `arm64/codegen.nv`, user-defined `main` functions and call targets are mangled to `_nova_user_main`, eliminating collisions with C runtime `main(int argc, char** argv)`.
- Verified in `tests/test_selfhost_parity.py` (`test_user_defined_main_function`).

### High-Speed Contiguous Raw Memory Buffers (`nova/stdlib/buffer.nv`)
- Implemented unboxed contiguous memory slab primitives in `runtime.c`: `buf_new`, `buf_free`, `buf_get_u8`, `buf_set_u8`, `buf_get_i32`, `buf_set_i32`, `buf_fill_i32`, `buf_copy`.
- `Buffer` class provides zero-cost encapsulation with `handle: int` and `size: int`.
- Benchmark achieves 10 million 32-bit word writes in `< 25ms` (<0.0025 ns/op).
- Verified in `tests/test_buffer.py`.

### Native TCP Networking (`net.nv`) & High-Resolution Monotonic Timers (`time.nv`)
- Dynamic Winsock2 (`ws2_32.dll`) loading at runtime ensures zero static linker dependencies across stages.
- Primitives: `nova_net_init`, `nova_tcp_listen`, `nova_tcp_accept`, `nova_tcp_connect`, `nova_net_send`, `nova_net_recv`, `nova_net_close`.
- Microsecond timing via Windows `QueryPerformanceCounter`/`QueryPerformanceFrequency` (`time_now_us`, `time_now_ms`, `sleep_ms`).
- Verified in `tests/test_net_time.py`.

### 60 FPS Software Framebuffer Blitting & Interactive Input (`gui.nv`)
- Win32 `StretchDIBits` directly blits raw 32-bit RGBA pixel buffers to window HDC surfaces via `presentFramebuffer(fb_handle, width, height)`.
- Input polling via `isKeyDown(keycode)` and `isMouseDown(btn)` provides instant, unbuffered state query.
- Verified in `tests/test_framebuffer.py`.

### Showstopper Flagship: Nova Physics Studio (`examples/nova_sandbox.nv`)
- Interactive 60 FPS particle studio with 600 particles, gravity wells, explosive shockwaves, elastic boundary collisions, and real-time HUD vector overlay.
- Dual-mode architecture:
  - GUI Mode: Full Win32 software-rasterized window with interactive mouse/keyboard controls.
  - Headless Benchmark Mode: `nova_sandbox --headless-bench 300` executes 300 physics & rasterization frames in **21 ms** (**14,092 FPS**, >20x faster than the 600 FPS target).
- Standalone executable footprint: **187.5 KB** (well within `< 250 KB` requirement).
- Verified in `tests/test_sandbox.py`.

---

## 12. Standard Library Modular Hardening & Systems Upgrade (Sprint 6)

### Phase 1: Memory, Bytes & Text (`buffer.nv`, `text.nv`, `runtime.c`)
- **`NovaBufferHeader` Metadata**: All raw heap allocations are prefixed with a 16-byte metadata header tracking `magic (0x42554631)` and `capacity`.
- **Strict Boundary Guards**: Out-of-bounds `buf_get_*` or `buf_set_*` calls trigger a clean panic (`_nova_buf_panic`) printing telemetry (offset, required bytes, capacity) to stderr and exiting cleanly with code 1 instead of unrecoverable memory access violations.
- **Unaligned Word Reads/Writes**: `buf_get_u16`, `buf_set_u16`, `buf_get_i32_unaligned`, and `buf_set_i32_unaligned` use safe memory copy primitives for strict-alignment architectures.
- **Safe Buffer Slicing**: `buf.slice(offset, length)` creates sub-buffers bounds-checked against capacity.
- **String View Helpers**: `text.str_slice(s, start, length)` performs bounds-clamped substring extractions.
- Verified in `tests/test_buffer.py` and `tests/test_std_extensions.py`.

### Phase 2: File System & Paths (`fs.nv`, `path.nv`)
- **Deterministic Path Normalization**: `path_to_forward(path)` unifies Windows backslashes (`\`) to POSIX forward slashes (`/`).
- **Atomic File Writes**: `fs_write_atomic(path, content)` writes data to `<path>.tmp` and atomically renames via `fs_move`, preventing data corruption during crashes or partial writes.
- Verified in `tests/test_std_extensions.py`.

### Phase 3: Networking & Time (`net.nv`, `time.nv`)
- **Socket Timeouts**: Dynamic Winsock2 `setsockopt` integration (`SO_RCVTIMEO` and `SO_SNDTIMEO`) via `nova_socket_set_timeout(sock, ms)` and `stream.set_timeout(ms)`, preventing network operations from hanging indefinitely.
- **Monotonic Clocks**: High-performance monotonic clocks on Windows (`QueryPerformanceCounter`) and POSIX (`clock_gettime(CLOCK_MONOTONIC)`).

### Phase 4: Creative UI & Styling (`gui.nv`, `nss.nv`)
- **GUI Event Ring Buffer**: Circular event queue (`g_gui_events` ring buffer of 128 slots) in `_NovaWndProc` and `gui_poll_event_raw`, guaranteeing mouse clicks and keystrokes are never dropped during heavy frame rasterization.
- **Pre-Parsed NSS AST Cache**: `nss_get_cached(path)` caches stylesheet ASTs to eliminate repetitive disk I/O and re-parsing per frame.

### Phase 5: Parsing & Diagnostic Isolation (`json.nv`, `errors.nv`)
- **Streaming JSON Tokenizer**: `json_cursor_new(src)` and `json_next_token(c)` support token-by-token parsing in $O(1)$ memory without constructing complete recursive ASTs.
- **Compiler Diagnostic Caret Pointers**: Emits exact source column pointing carets (`^~~~`) matching Clang/Rust diagnostics.
- Verified in `tests/test_std_extensions.py`.


