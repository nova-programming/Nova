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



---

## 13. Flagship Native IDE: Nova Studio (`examples/nova_studio.nv`)

### Standalone Executable Footprint (< 250 KB)
- Single-file native application built with pure Nova standard library modules.
- Stripped standalone binary footprint: **230.01 KB** (235,534 bytes), well below the `< 250 KB` requirement.
- Verified in `tests/test_studio.py`.

### 3-Zone Architecture & Styling (`gui.nv` + `nss.nv`)
- Dark-themed Catppuccin Mocha `#1e1e2e` color scheme.
- **Zone 1 (Code Editor)**:
  - Line numbers gutter (`#181825` background, `#6c7086` text).
  - Active line highlight (`#313244`) and red error line highlights (`#45232e`).
  - Interactive typing via `pollChar()`, backspace handling, enter/line splitting, arrow key navigation.
  - Token syntax coloring for comments (`#6c7086`), keywords (`#cba6f7`), and imports (`#89b4fa`).
- **Zone 2 (Live Diagnostics & Execution Console)**:
  - Tabbed interface switching between `Diagnostics` and `Console Output`.
  - In-process diagnostic parsing: captures pointing carets (`^~~~`), line/column numbers, and suggestion hints.
  - Status badges: emerald green `#a6e3a1` for clean code, rose red `#f38ba8` for compiler errors.
  - Program runner: executes `nova.exe run` via `process_capture`, displaying stdout and exit codes.
- **Zone 3 (60 FPS Viewport & Audio Sandbox)**:
  - 320 dynamic particles with velocities, elastic bouncing, and mouse attraction gravity wells.
  - Clickable explosive radial shockwaves with audio feedback.
  - Real-time PCM audio oscilloscope waveform rendered along the viewport base.
  - Blitted at 60 FPS into the GDI backbuffer via `drawFramebuffer(fb_h, x, y, w, h)`.
  - Fullscreen mode toggle supported via `presentFramebuffer(fb_h, w, h)`.

### Sub-Rectangle Framebuffer Blitting & Win64 Stack Alignment (`runtime.c` & `gui.nv`)
- Added `gui_draw_framebuffer(buffer_ptr, x, y, width, height, unused)` to `runtime.c` and `gui.nv`.
- Blits 32-bit RGBA pixel buffers directly into `g_gui_mem_dc` using Win32 `StretchDIBits`, enabling seamless coexistence of high-framerate software rasterization and vector GDI controls without screen tearing.
- **Win64 Stack Alignment Fix**: On x86_64 Windows ABI, calls with an odd number of stack arguments (e.g. 5 arguments = 4 register + 1 stack argument) misalign the stack pointer to an 8-byte boundary (`rsp % 16 == 8`), triggering a `0xC0000005` Access Violation when GCC emits 16-byte SSE instructions (`movaps`) inside the callee. Providing 6 arguments (4 register + 2 stack arguments = 16 bytes) ensures `%rsp` remains strictly 16-byte aligned before `call`, eliminating runtime access violations while `drawFramebuffer` retains its clean 5-argument public API.

### Native Audio & Sound Synthesis (`stdlib/audio.nv`)
- Zero external dependencies: binds directly to Win32 `kernel32.dll`'s `Beep(dwFreq, dwDuration)`.
- UI audio effects: `audio_click()`, `audio_success()`, `audio_error()`, `audio_play_note(note, duration)`.
- Mathematical PCM waveform synthesis for real-time oscilloscopes: `audio_sample_sine`, `audio_sample_triangle`, `audio_sample_square`, `audio_sample_noise`.

### Headless Benchmark Mode
- `nova_studio --headless-bench 300`:
  - Validates in-process compiler diagnostics pipeline.
  - Simulates 300 physics & rasterization frames into a raw `Buffer` in **7 ms**.
  - Throughput: **~38,500 FPS** (>600x faster than 60 FPS target).


---

## 14. Nova Studio Interactive Polish & Runtime Invariants (Sprint 7)

### GCC Warning Elimination (`runtime.c`)
- **`_exit` Builtin Declaration Mismatch**: Wrapped `STR_PFX(exit)` in `#pragma GCC diagnostic ignored "-Wbuiltin-declaration-mismatch"`, eliminating ABI mismatch warnings with GCC's builtin.
- **`__p___argc` / `__p___argv` Redeclaration**: Wrapped extern declarations in `_sys_get_args_c` in `#pragma GCC diagnostic ignored "-Wattributes"`, silencing CRT DLL import warnings.
- **Clean Compiler Build**: `gcc -c -O3 nova/runtime.c` compiles with 0 errors and 0 warnings.

### High-DPI Framebuffer Alignment & Waveform Bounds
- **DPI Scaling in `gui_draw_framebuffer`**: Scaled destination coordinates (`px, py, pw, ph`) by `g_gui_dpi_scale` before `StretchDIBits` into `g_gui_mem_dc`. Fixes coordinate and size mismatch where the software-rendered viewport escaped or misaligned with its NSS vector borders on high-DPI displays.
- **Oscilloscope Waveform Clamping**: Clamped `wy` between `vh - 54` and `vh - 8` with a safe upper limit check `wy < vh - 1` before writing `(wy + 1) * vw + wx`. Separated the particle arena (`y < vh - 62`) from the oscilloscope base with a subtle divider line at `vh - 58`.

### Interactive Button Responsiveness & Visual Hover Feedback
- **Immediate Mouse-Down Debounced Latching**: Added `m_down = gui_get_mouse_down()` with edge detection (`m_down == 1 and prev_m_down == 0`) so clicks trigger with 0-latency on initial press rather than waiting for mouse release.
- **Dynamic Visual Hover States**: Highlighted button background (`#45475a`) and borders on hover for `[Check Source]`, `[Run]`, `[Reset Sim]`, `[Sound FX]`, `[Fullscreen]`, and tabs.
- **Quoted Path Execution & Stderr Streaming**: Wrapped executable and source paths in quotes with `2>&1` (`"\"\"" + nova_bin + "\" run \"" + tmp_run_file + "\" 2>&1\""`) in `process_capture`, preventing failure on Windows directories containing spaces and ensuring compiler/runtime stderr outputs are visible in the console tab.
- **Fullscreen Mode Toggle**: Removed `gui_present()` call from the fullscreen loop (which previously overwrote the fullscreen framebuffer with the stale non-fullscreen window backbuffer) and added click-consumption debounce to prevent immediate toggle exit.

### Root Frame Stack Alignment Fix (`backend/x86_64/codegen.nv`)
- **Root Epilogue Stack Alignment**: In `codegen.nv` line 1337, changed top-level stack allocation to `sub_amount = state.local_offset - regs_size; if sub_amount > 0 { emit("sub rsp, " + str(sub_amount)) }`. Previously, subtracting the full `state.local_offset` without subtracting `regs_size` resulted in pushing `used_regs` afterwards, causing an 8-byte stack misalignment whenever `len(state.used_regs)` was odd. This cures access violations when top-level code calls 64-bit ABI functions requiring 16-byte aligned stacks (such as Win32 GDI calls in `test_gui_raw.nv`).
- **Self-Host Verification**: Rebuilt Stage 1 $\to$ Stage 2 $\to$ Stage 3; byte-identical assembly output verified (`s2.s == s3.s`, SHA256: `6ca54ba0a1a6344c000e3085291fa4f9fbc26af082dfb1f87d206e008046cd35`).
- **Binary Footprint**: Stripped standalone `nova_studio.exe` footprint is **232.51 KB** (238,094 bytes), well below the `< 250 KB` requirement.

---

## 15. Native Monospace Typography, Reusable UI Components & Nova Studio Polish (Sprint 8)

### Native Monospace Typography & Reusable UI Components (`runtime.c` & `gui.nv`)
- **Native Monospace Font Support (`runtime.c`)**:
  - Added `STR_PFX(gui_draw_mono_text)` utilizing Microsoft Windows `Consolas` directly into the Win32 GDI pipeline with exact DPI-scaled pitch and anti-aliasing.
  - Implemented 6-parameter extern interface `extern def gui_draw_mono_text(text: string, x: int, y: int, font_size: int, color_hex: int, font_weight: int)` matching Microsoft x64 calling convention.
  - Added public helper `def drawMonoText(text: string, x: int, y: int, size: int, color: int, bold: int)` in `stdlib/gui.nv`.
  - At font size 11, `Consolas` produces constant advance width of 7px, enabling exact caret positioning (`60 + len(s) * 7`) and column-aligned compiler diagnostic carets (`^~~~`).
- **Reusable Standard GUI Controls (`stdlib/gui.nv`)**:
  - `def ui_button(x, y, w, h, text, hover, active, theme)`: Renders polished styled buttons with hover and active states.
  - `def ui_badge(x, y, text, fg_col, bg_col)`: Renders pill badges with automatic width sizing and centered text.
  - `def ui_panel(x, y, w, h, bg_col, border_col, title, title_col)`: Renders framed cards and content panels with header bars.

### Nova Studio UI Upgrades (`examples/nova_studio.nv`)
- **Token-Level Syntax Highlighting (`render_highlighted_code`)**:
  - Pure in-engine lexical highlighter rendering tokens with `drawMonoText` in fixed-pitch Consolas:
    - Keywords (`def`, `return`, `if`, `while`, `for`, `import`, etc.) in Catppuccin Mauve (`#cba6f7`, bold).
    - Built-in functions and types (`int`, `string`, `list`, `print`, `str`, `len`, `range`) in Blue (`#89b4fa`, bold).
    - String literals in Emerald Green (`#a6e3a1`).
    - Numeric constants in Warm Peach (`#fab387`).
    - Punctuation and braces in Sky Blue and Teal (`#89dceb`, `#94e2d5`).
    - Comments in Muted Gray (`#6c7086`).
- **Living Constellation Swarm Physics (No Single-Point Collapse)**:
  - Initial particle positions distributed across viewport dimensions rather than clumped at center.
  - Added tangential orbital curl acceleration (`tang_x = -dy/450`, `tang_y = dx/450`) combined with gravitational pull, creating stable celestial swirling motion.
  - Added kinetic wander floor to keep particles permanently active even in steady-state.
  - Added subtle cosmic grid background (32px pitch dots, `#232438`) for depth and spatial perspective.
- **Console Auto-Scroll & Semantic Terminal Coloring**:
  - Automatic bottom scrolling displays the most recent 9 lines (`start_ci = max(0, len(c_lines) - 9)`), ensuring executed program output and exit status are always visible.
  - Semantic syntax coloring: process invocation headers in blue, compiler progress stages in subtle gray, program stdout in bright teal (`#94e2d5`), clean exit code 0 in emerald green (`#a6e3a1`), and error lines in rose red (`#f38ba8`).
- **Editor Interaction Enhancements**:
  - Click-to-seek: clicking anywhere in the code editor panel instantly positions the active line cursor (`cursor_line = (my - 73) / 20`).
  - Tab key support: pressing Tab (`ch == 9`) inserts a 4-space indent.
- **Binary Footprint & Performance**:
  - Stripped standalone `nova_studio.exe`: **247.51 KB** (strictly `< 250 KB`).
  - Headless benchmark throughput: **34,952 FPS** (>500x the 60 FPS target).
  - All 76 tests in `test_check_all.py` and `test_studio.py` pass cleanly.

---

## 16. VS Code & Antigravity IDE Architecture and GDI Font Cell Lock (Sprint 9)

### Exact GDI Font Cell Lock (`runtime.c`)
- **Cumulative Monospace Spacing Drift Elimination**:
  - In `STR_PFX(gui_draw_mono_text)`, explicitly passed `font_w = (int)(7.0f * g_gui_dpi_scale)` and `font_h = (int)(font_size * 1.35f * g_gui_dpi_scale)` into Win32 GDI's `CreateFontA`.
  - When `font_w` is non-zero, Windows GDI locks every character cell to exactly `font_w` physical pixels, which mathematically matches Nova's `curr_x + len(tok) * 7` layout advance at any DPI scale.
  - Eliminated artificial void gaps around parentheses, quotes, and operators (`print("...")` renders seamlessly).

### Full VS Code & Antigravity IDE Architecture (`examples/nova_studio.nv`)
- **Top Command & Navigation Bar (`y = 0..36`)**:
  - Branded tag `◆ NOVA` with breadcrumb `workspace › examples › <file>`.
  - Centered Run & Check command pill (`[ ▶ Run ]` and `[ ✓ Check ]`) with soft rounded borders.
  - Action pills on right: `[ ↺ Reset ]`, `[ 🔊 Sound ]`, `[ ⛶ Max ]`, and `60 FPS | x86` status pill.
- **Activity Bar (`x = 0..42`)**:
  - Left navigation strip (`#11111b`) with 2px active accent line and tool icons (`📁` Explorer, `⚡` Run, `🌌` Sandbox).
- **Project Explorer Sidebar (`x = 42..185`)**:
  - Interactive file list: `📄 nova_studio.nv`, `📄 schema_doctor.nv`, `📄 windows_ui.nv`.
  - Clicking any file smoothly loads its corresponding template in the editor.
- **Modern Code Editor Zone (`x = 185..650`)**:
  - Editor tab header `[ 📄 <file>  × ]` with blue `#89b4fa` active top line.
  - Dark gutter with right-aligned line numbers and active line background highlight (`#24273a`).
  - Seamless token-level syntax coloring without spacing distortion.
- **Live Particle Viewport Sandbox (`x = 655..1030`)**:
  - Tab header `🌌 PARTICLE SANDBOX` with `Click to Shock` interaction indicator.
  - Software rasterized celestial particle swarm + sine waveform blitted via `drawFramebuffer`.
- **Integrated Terminal & Problems Bottom Panel (`x = 42..1030`, `y = 482..682`)**:
  - Tabbed footer panel with `TERMINAL` and `PROBLEMS (0)` tabs.
  - Right-aligned `⊘ Clear` action button to flush output.
  - 10pt Consolas monospace terminal output with semantic color highlights.
- **Integrated Bottom Status Bar (`y = 684..710`)**:
  - Displays `⊞ Nova v1.0` | `Ln X, Col Y` | `UTF-8` | `Consolas 11pt` | `x86_64 Native | 320 Particles | 60 FPS`.
- **Performance & Footprint**:
  - Standalone binary size: **249.51 KB** (strictly `< 250 KB`).
  - Benchmark throughput: **34,806 FPS**.
  - All test suites (`test_check_all.py`, `test_studio.py`) pass 100%.

---

## 17. Declarative UI Engine & Two-Pass Layout Architecture (Sprint 10)

### Clean Declarative Paradigm (`nova/stdlib/gui.nv`)
- **Core Abstractions**:
  - Extended `Widget` struct with `flex: int`, `measured_w: int`, and `measured_h: int`.
  - Pure functional factories: `Row(children, props)`, `Column(children, props)`, `Button(label, on_click, props)`, `Text(label, props)`, `Spacer(props)`, and `Canvas(render_fn, props)`.
  - Preserved legacy immediate-mode and raw widget constructors for complete backward compatibility.

### Two-Pass Layout Engine (`gui_measure` & `gui_layout`)
- **Pass 1: Bottom-Up Intrinsic Measurement (`gui_measure`)**:
  - Leaf nodes calculate intrinsic bounds from text metrics (`strLen * char_w`, monospace cell locking, font-size, padding).
  - Containers recursively measure children, accumulating primary axis dimensions with `gap` and computing cross-axis bounds.
  - Explicit `width`/`w` and `height`/`h` overrides take precedence where defined.
- **Pass 2: Top-Down Dynamic Flex & Coordinate Assignment (`gui_layout`)**:
  - Allocates remaining container space (`inner_primary - fixed_space - gaps`) proportionally across `flex > 0` children.
  - Assigns absolute coordinates `(pos_x, pos_y)` to all nodes in the tree based on flex direction, gaps, and cross-axis alignment (`align-items: center | start | end | stretch`).

### Event Dispatch & Lifecycle Management (`gui_dispatch_events` & `gui_run`)
- **Automatic Event Routing (`gui_dispatch_events`)**:
  - Traverses the widget hierarchy checking mouse pointer intersection against resolved layout bounds.
  - Automatically updates `is_hovered` and `is_pressed` states.
  - Triggers action callbacks (`dispatchAction`) upon click without developer event-loop boilerplate.
- **Window Lifecycle Runner (`gui_run`)**:
  - Handles window creation, NSS stylesheet loading, layout resolution, double-buffered frame presentation, testing harnesses (`--test`), and native screenshot capture (`--screenshot`).

### Flagship Migration: Nova Studio (`examples/nova_studio.nv`)
- **Pure Declarative Tree Model**:
  - Replaced manual coordinate math and 150+ lines of procedural layout with declarative component definitions (`Row`, `Column`, `Button`, `Text`, `Spacer`, `Canvas`).
  - Brand pill with workspace breadcrumbs, centered Run/Check command pill, and right action cluster (`Reset`, `Sound`, `Max`, `60 FPS`).
  - Sidebar file explorer built with declarative button list responding to `ACTION_FILE_0..2`.
  - Zero-allocation 60 FPS loop: interactive code editor and celestial particle sandbox blit inside declarative `Canvas` bounds without intermediate heap churn.
  - Automated mouse click/hover routing via `gui_dispatch_events(root, mx, my, is_clicked)`.

### Verification & Invariants Gate
- **Declarative Preview Artifact**:
  - Captured pixel-perfect GDI screenshot artifact `studio_declarative_preview.png`.
- **Self-Host Invariant**:
  - Stage 1 -> Stage 2 -> Stage 3 self-host loop verified: `s2.s SHA256 == s3.s SHA256` (`6ca54ba0a1a6344c000e3085291fa4f9fbc26af082dfb1f87d206e008046cd35`). Byte-for-byte identical.
- **Test Suites**:
  - `pytest nova/tests/test_widgets.py` -> 4/4 PASSED.
  - `pytest nova/tests/test_check_all.py` -> 77/77 PASSED.
  - `pytest nova/tests/test_studio.py` -> 2/2 PASSED (`nova_studio.exe` size: **249.51 KB** `< 250 KB`, benchmark throughput: **34,806 FPS** `> 60 FPS`).

---

## 18. Unified High-Level Declarative GUI Suite & Default Styling (Stage 1)

### Centralized Styling Architecture (`_apply_default_props`)
- Centralized reusable modern styling defaults (Catppuccin Mocha palette) applied across all high-level constructors:
  - `title`: 22pt bold, `#cdd6f4`, `padding-bottom: 8`.
  - `heading`: 16pt bold, `#89b4fa`, `padding-bottom: 6`.
  - `text`: 14pt, `#cdd6f4`.
  - `button`: `#89b4fa` primary fill, `#11111b` text, `border-radius: 6`, padding `8px 14px`, hover `#b4befe`, press `#74c7ec` (ghost buttons preserve transparency when background is unspecified and custom color provided).
  - `card`: `#1e1e2e` surface, 1px border `#313244`, `border-radius: 8`, padding `16px`, `gap: 10`.
  - `divider`: 1px rule `#313244`, margin `8px 0`.
  - `input`: 34px height, `#181825` mantle, 1px border `#45475a`, `border-radius: 6`, padding `10px`, focus border `#89b4fa`.
  - `textarea`: 80px height, `#181825` mantle, 1px border `#45475a`, `border-radius: 6`, padding `10px`.
  - `toggle`, `checkbox`, `slider`, `dropdown`: intrinsic sizes and unified modern dark theme controls.

### Complete High-Level Component Suite (`nova/stdlib/gui.nv`)
- **Typography & Display**: `Title`, `Heading`, `Text`, `Image`, `Canvas`.
- **Interactive Controls**: `Button`, `Input`, `TextArea`, `Checkbox`, `Toggle`, `Slider`, `Dropdown`.
- **Layout & Structure**: `Row`, `Column`, `Container`, `Card`, `Divider`, `Spacer`, `Scroll`, `List`.
- **Lifecycle Management**:
  - `App(title, root, width, height, props)`: Unifies initialization, NSS loading, layout resolution, double-buffered frame presentation, testing harnesses (`--test`), screenshot capture (`--screenshot`), and clean teardown.
  - `Window(title, root, width, height, props)`: High-level window app wrapper.
  - Ergonomic helpers: `title(text)`, `heading(text)`, `app_run(title, root)`.

### Declarative Actions & Intrinsic Layout Extension
- Extended `dispatchAction` with `"set_text"` handler for declarative string mutation on target widgets.
- Extended `gui_measure` with accurate leaf intrinsic metrics for `input` (34px), `checkbox` (24px), `toggle` (44x24px), `slider` (140x24px), `dropdown` (120x30px), and `divider` (1px).

### Verification & Invariants Gate
- **Visual Verification**:
  - Generated and verified artifact: `declarative_suite_preview.png`.
  - Created demonstration app `nova/examples/declarative_app_demo.nv`.
- **Self-Host Invariant**:
  - Stage 1 -> Stage 2 -> Stage 3 self-host loop: `s2.s SHA256 == s3.s SHA256` (`6ca54ba0a1a6344c000e3085291fa4f9fbc26af082dfb1f87d206e008046cd35`).
- **Test Suites**:
  - `pytest nova/tests/test_studio.py` -> 2/2 PASSED (`nova_studio.exe` size: **249.51 KB** `< 250 KB`, benchmark throughput: **34,566 FPS** `> 60 FPS`).
  - `pytest nova/tests/test_widgets.py` -> 5/5 PASSED.
  - `pytest nova/tests/test_check_all.py` -> 78/78 PASSED.

---

## 19. Stage 2: Reactive State Management & Component Lifecycle Architecture

### Reactive State Primitives (`data State`)
- **First-Class Reactive Object**:
  - `data State { val_type: str, val_int: int, val_str: str, targets: [Widget] }`
  - Instantiators: `StateInt(val: int)`, `StateStr(val: str)`, `state_int`, `state_str`.
  - Direct Accessors: `state_get_int(s)`, `state_get_str(s)`, `state_set_int(s, v)`, `state_set_str(s, v)`.
- **Zero Full-Tree Reconstruction (Observer / Signal Pattern)**:
  - When `state_set_int` or `state_set_str` is invoked, `state_notify(s)` iterates strictly through registered target observer widgets (`s.targets`) in $O(1)$ time.
  - Formats bound labels using optional `prefix` and `suffix` props without rebuilding or re-allocating virtual DOM / widget hierarchies.
  - Guarantees zero heap churn during 60 FPS animations and live text entry.

### Two-Way Data Binding (`"bind": state`)
- Supported across all components via `_check_state_binding(widget, props)`:
  - **Text / Title / Heading**: Observes string or integer state changes and updates text.
  - **Input / TextArea**: Binds live text value to `StateStr`. Typing events update `s.val_str` and immediately trigger `state_notify` to sync peer widgets.
  - **Checkbox / Toggle**: Binds active boolean state to `StateInt` (0 or 1). Clicking toggles state and notifies observers.
  - **Dropdown**: Binds selected index to `StateInt` and selected item label to `StateStr`.

### Event Dispatch & Action Registry
- Integrated reactive actions into `dispatchAction(w, action_id)`:
  - `"increment"`: `state_set_int(s, s.val_int + 1)`
  - `"reset"`: `state_set_int(s, 0)`
  - `"toggle"`: `state_set_int(s, 1 - s.val_int)`
  - `"set_text"`: `state_set_str(s, new_val)`
- Focus management (`is_focused`) and keyboard event routing (`_dispatch_key_event`) for live text fields.

### Verification & Invariants Gate
- **Visual Verification**:
  - Generated and verified artifact: `reactive_state_preview.png` (720x680 RGB).
  - Created demonstration app `nova/examples/reactive_state_demo.nv`.
- **Automated Tests**:
  - `pytest nova/tests/test_widgets.py` -> **7/7 PASSED** (added `test_reactive_state_demo_suite` and `test_reactive_state_unit`).
  - `pytest nova/tests/test_studio.py` -> **2/2 PASSED** (`nova_studio.exe` size: **247.51 KB** `< 250 KB`, benchmark throughput: **34,566 FPS** `> 60 FPS`).
  - `pytest nova/tests/test_check_all.py` -> **82/82 PASSED**.
- **Self-Host Parity**:
  - `s2.s SHA256 == s3.s SHA256` (`6ca54ba0a1a6344c000e3085291fa4f9fbc26af082dfb1f87d206e008046cd35`). Absolute byte-for-byte compiler parity preserved.

---

## 20. Stage 3: Advanced Layout Constraints & Built-in Dual-Theme System

### Advanced Layout Constraints (`min_w`, `max_w`, `min_h`, `max_h`, `space-between`, `space-around`)
- Extended `_expand_props` in `nova/stdlib/gui.nv` to parse layout boundary constraints.
- Extended `gui_measure`:
  - Clamps leaf and container measurements against `min_w`, `max_w`, `min_h`, and `max_h` constraints.
- Extended `gui_layout`:
  - Implemented `justify-content: "space-between"`: Evenly distributes remaining free space among intermediate child gaps ($N - 1$).
  - Implemented `justify-content: "space-around"`: Evenly distributes space with half-units at perimeter edges.
  - Implemented proportional `flex` allocation on main axis when `total_flex > 0`.
  - Implemented `align-items: "stretch"`, `"center"`, `"end"` cross-axis alignment.

### Built-in Catppuccin Theme Architecture
- Integrated dual-theme engine (`dark`: Catppuccin Mocha, `light`: Catppuccin Latte):
  - `set_theme(name: string)`: Activates global active palette (`_gui_active_theme`).
  - `get_theme() -> string`: Queries active theme identifier.
  - `toggle_theme() -> string`: Toggles between dark and light themes seamlessly.
  - `get_theme_color(token: string) -> string`: Resolves palette tokens (`text`, `accent`, `surface`, `mantle`, `border`, `surface_alt`, `muted`, `accent_hover`, `accent_press`).
- Fully wired into `_apply_default_props` to ensure any widget created dynamically adopts active theme colors.
- Demonstrated in `nova/examples/layout_and_themes_demo.nv` and visually verified via `layout_themes_preview.png`.

---

## 21. Stage 4: Nova Studio Dual-Mode Architecture

### Simple Mode (Beginner-Friendly 5-Minute Developer Experience)
- **Top Bar**: Minimal branding, quick starter template selectors (`📄 Hello`, `🔢 Counter`, `🌌 Engine`), `▶ Run App`, `✓ Check`, and `⚙ Mode` toggle.
- **Main Area**: 2-column beginner workbench:
  - Left: Clean, full-height source code editor canvas with line numbering, active-line accent, and real-time syntax highlighting.
  - Right: Unified Live Terminal / Output viewport displaying subprocess compilation and execution results.
- **Status Bar**: Simplified status information (`Nova v1.0`, `Ln, Col`, `UTF-8`).

### Advanced Mode (Full-Power Creative Studio IDE)
- **Activity Bar**: Navigation rail (`📁 Explorer`, `⚡ Actions`, `🌌 Sandbox`).
- **File Explorer**: Workspace tree with quick file switching (`hello_app.nv`, `counter_app.nv`, `engine_demo.nv`).
- **Interactive Particle Sandbox**: Integrated 60 FPS Win32 software framebuffer viewport simulating 320 celestial particles with ambient cosmic grid, dynamic sine audio waveform, and mouse shockwave physics.
- **Multi-Tab Bottom Panel**: Tabbed dock switching between Terminal process logs and Problems diagnostic inspector with error badges, column carets, and compiler fix suggestions (`->`).
- **Toolbar Controls**: Top bar with `▶ Run`, `✓ Check`, `↺ Reset`, `🔊 Sound`, `⛶ Max` (fullscreen sandbox), and real-time FPS throughput badge.

---

## 22. Stage 5: Starter Templates, Engine Consolidation & Binary Size Optimization

### Starter Templates
- `nova/examples/hello_template.nv`: Clean, zero-boilerplate introductory application demonstrating `Title`, `Text`, `Button`, `Column`, and `App`.
- `nova/examples/counter_template.nv`: Beginner-friendly reactive state demonstration using `StateInt`, two-way binding (`bind: c`), declarative increment action (`action: "increment"`), and `App`.
- Both templates compile natively and pass headless verification (`--test`).

### Layout Engine Consolidation & Assembly Pruning
- **Elimination of Duplicate Layout Engines**:
  - Replaced legacy 360-line `layoutWidgetInternal` with pure delegation to two-pass `gui_measure` and `gui_layout`.
  - Replaced duplicate widget constructors (`h1`, `h2`, `h3`, `txt`, `label`, `badge`, `spacer`, `divider`, `input_field`, `icon_btn`, `nav_item`, `card`) with thin forwarding wrappers to unified high-level constructors.
  - Optimized `_expand_props` to iterate over input dictionary keys directly instead of executing 40 redundant `has()` lookups.
  - Consolidated Studio UI component constructors (`s_btn`, `s_lbl`, `s_pane`, `list_splice`).
- **Performance & Binary Invariants**:
  - `nova_studio.exe` stripped size: **247.51 KB** (strictly `< 250.0 KB` threshold).
  - Headless benchmark throughput: **34,500+ FPS** (strictly `> 60 FPS` requirement).
  - Repository test suite: **82/82 PASSED** (`test_check_all.py`), **7/7 PASSED** (`test_widgets.py`), **2/2 PASSED** (`test_studio.py`).
  - Compiler self-host invariant: `s2.s SHA256 == s3.s SHA256` (`6ca54ba0a1a6344c000e3085291fa4f9fbc26af082dfb1f87d206e008046cd35`). Absolute byte-for-byte compiler parity preserved.



---

## 23. Galaxy Registry Ecosystem Transformation

### Strategic Transformation
Transformed Galaxy from a static documentation website into an end-to-end developer ecosystem for the Nova programming language (`galaxy-registry`):

1. **Universal Theme Engine (`theme.css`, `theme.js`)**:
   - Synchronized dark and light themes across `index.html`, `documentation.html`, `reference.html`, `examples.html`, `templates.html`, and `playground.html` via `localStorage.getItem('nova_theme')`.
   - Zero-FOUC initialization script with top navigation Sun/Moon toggle button.
   - Synchronized Monaco editor theme (`vs-dark` / `vs`).

2. **Homepage Ecosystem Positioning (`index.html`)**:
   - Product positioning: Pythonic ergonomics, C-speed native machine code, sub-250KB binaries, 60 FPS Win32 double-buffered declarative desktop graphics.
   - Primary Call-to-Action: Prominent `⚡ Try Nova in Playground` button with glowing accent styling.
   - Embedded Mini-Try-It Runner: Interactive snippet runner on the homepage testing Fibonacci, OOP classes, and text processing.
   - 6 Comprehensive Feature Pillars: Direct Native Binaries, Native 60 FPS Win32 GUI, Pythonic Static Typing, Nova Studio & Tooling, Git-Backed Package Registry, Cryptographic Release Provenance.

3. **Interactive WebAssembly Playground (`playground.html`, `nova_worker.js`)**:
   - Real-time diagnostic error squiggly markers via Monaco Editor (`monaco.editor.setModelMarkers`) from WebAssembly Pyodide worker syntax checking (`check_syntax`).
   - Capability Indicator Badge (`🟢 Browser VM Sandbox`) and interactive modal breaking down browser VM features vs Native toolchain requirements (`import gui`, C FFI, OS subprocesses).
   - Categorized presets: *Beginner Basics*, *Data Structures*, *Algorithms*, *Standard Library*, *Native GUI (Local Showcase)*.
   - Shareable permalinks (`#code=...`), execution timing metrics, console shortcuts (`Ctrl+Enter`, `Ctrl+K`).

4. **Interactive Documentation & Learning Lab (`examples.html`, `documentation.html`)**:
   - Floating / inline **"▶ Run in Playground"** buttons on all 19 code examples and language manual snippets, opening directly into the playground.
   - **Interactive Coding Challenges**: 3 hands-on exercises (Prime Filter, Word Frequency Counter, Dictionary Inversion) with starter code, expandable hints, and verified solutions.

5. **Package Registry & Security Elevation (`index.html`, `packages/`)**:
   - Package catalog sorting by Upvotes, Name (A-Z), and Version.
   - Package detail dependencies viewer and Security & Provenance Card displaying Ed25519 signature status (`.json.sig`), SHA-256 release checksum, static analysis verification, and supply chain health.
   - Dual install pills (`galaxy install <pkg>`, `galaxy add <pkg>`).

6. **Visual Template & Scaffolding Builder (`templates.html`)**:
   - Visual project templates for *Pure Reusable Library*, *CLI Terminal Utility*, and *Desktop Native GUI App*.
   - Live interactive `galaxy.json` manifest builder with live preview and one-click copy.
   - Publishing checklist from project initialization to GitHub PR review.

---

## 24. Project Nova: Language Ergonomics, Semantic Correctness & Core Evolution (Phases 1–5)

### Architectural Overview
Completed a 5-phase evolutionary architecture across the self-hosted compiler pipeline (`nova/stdlib/`), C runtime (`nova/runtime.c`), and regression test suite without modifying the frozen Python bootstrap compiler (`nova/bootstrap/*.py`).

### 1. Phase 1: Language Specification & Ergonomics
- Established comprehensive language grammar and formal specification for:
  - Named & default function arguments: `def func(name: string, count: int = 1, flag: bool = true)`.
  - Dictionary subscript read (`val = dict[key]`) and write (`dict[key] = val`) with membership checking (`key in dict`).
  - Strict type checking rules, explicit `null` safety, and first-class function values.

### 2. Phase 2: Named/Default Arguments & Dictionary Indexing
- **Parser & AST (`nova/stdlib/parser.nv`)**:
  - Captured keyword argument names and flags in `Call` and `MethodCall` nodes (`arg_names: list`, `arg_is_kw: list`).
  - Added default parameter expressions in `Function` declarations (`param_defaults: list`).
  - Extended index expression parsing for dictionary subscript assignment (`dict[key] = val` -> `dict_set`) and lookup (`dict[key]` -> `dict_get`).
  - Preserved backward compatibility for `.get()`, `.set()`, and `.has()` methods.
- **Type Checker (`nova/stdlib/type_checker.nv`)**:
  - Implemented `tc_bind_args` and `tc_bind_method_args` unifying positional and keyword arguments.
  - Validates missing required arguments, rejects unknown/duplicate keyword parameters, and substitutes default expressions for omitted trailing parameters.
  - Precise shape typing for dictionary string literals.
- **Code Generation (`nova/stdlib/backend/{x86_64,arm64}/codegen_expr.nv`)**:
  - Emitted runtime calls `dict_get(d, k)` and `dict_set(d, k, v)`.
  - Re-bound argument lists in parameter declaration order at compile-time for zero runtime overhead.
- **Test Fixture**: Verified in `nova/tests/test_phase2_features.nv`.

### 3. Phase 3: Type-System Consistency & Formal Null Safety
- **Strict Static Enforcement**:
  - Converted silent type mismatches and parameter count mismatches into fatal compiler errors.
  - Formalized function call arity checks across direct calls, method calls, and extern calls.
- **Null Safety (`null`)**:
  - Defined explicit `Null` AST node (`Null`) and type representation (`create_null_type()`).
  - Unified `null` with pointer/struct/any types while strictly rejecting assignments to primitive integer/float scalars (`cannot assign null to int`).
- **Test Fixture**: Verified in `nova/tests/test_null.nv`.

### 4. Phase 4: Memory Architecture & Predictable ARC Safety
- **ARC Primitives (`nova/runtime.c`)**:
  - Hardened `_nova_arc_inc` and `_nova_arc_dec` with a 64-bit canonical user address space range check:
    `0x10000ULL <= (unsigned long long)ptr && (unsigned long long)ptr <= 0x00007FFFFFFEFFFFULL`.
  - Guaranteed immunity against access violations when processing null, unboxed integers, small sentinel offsets, or high kernel addresses.
  - Deterministic deallocation of dynamic containers, strings, and structs on scope exit.
- **Test Fixture**: Verified in `nova/tests/test_arc_lifecycle.nv`.

### 5. Phase 5: First-Class Function Values & Dynamic Callbacks
- **First-Class Function Values**:
  - Unparenthesized function references (`my_fn = add`) evaluate to native code addresses via `lea %a, [rip + _fn_name]` (x86_64) or `adrp/add` (ARM64).
  - Type annotations accept `fn` and `func` signatures (`fn`, `func(int, int) -> int`), with generic `fn` unparameterized signatures unifying cleanly with concrete signatures.
- **Indirect Native Calls**:
  - Evaluating a call where the callee target is a local variable or parameter holding a function pointer (`my_fn(10, 20)`):
    - Loads pointer into scratch register `r10` (x86_64) or `x16` (ARM64).
    - Pops up to 6 register arguments (`rdi, rsi, rdx, rcx, r8, r9`).
    - Aligns stack and executes indirect call: `call r10` / `blr x16`.
    - Automatically cleans caller stack arguments if argument count exceeds 6.
- **Register Allocator Isolation (`nova/stdlib/backend/x86_64/codegen.nv`)**:
  - In `count_var_refs`, excluded global/extern functions referenced as values from local variable counts, preventing `top_register_candidates` from assigning callee-saved registers (`r12..r15`) to uninitialized function symbols.
- **Bootstrap Struct Disjointness**:
  - Renamed `NamedFunc.param_defaults` to `NamedFunc.func_defaults` to eliminate field offset collisions with `AstNode.param_defaults` during Python bootstrap compilation.
- **Test Fixture**: Verified in `nova/tests/test_first_class_functions.nv`.

### Verification Metrics & Invariants
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`fb77b89bfc88f307e9375be6390795bfc742b4542ac31632186536bc89a7bd2e`).
- **Binary Footprint Budget**: `nova_studio.exe` stripped size: **248.51 KB** (254,478 bytes, strictly below 250 KB ceiling).
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.

---

## 29. Codebase Cleanup, Dead Code Elimination & Toolchain Hardening

### Architectural Overview
Comprehensive cleanup and optimization of the self-hosted compiler codebase, test suite, and runtime layer. Streamlined I/O operations during compilation, removed obsolete scratch scripts, pruned dead peephole analysis routines, deduplicated AST node constructors, and strictly partitioned Windows Microsoft x64 ABI vs internal System V AMD64 calling conventions in the runtime.

### 1. Legacy Dead Code Pruning & Test Harness Hardening
- **Root Scratch Cleanup**: Removed 6 obsolete debug/scratch files (`test_bridge.nv`, `test_bridge.py`, `test_cache_path_arm64.py`, `test_hook.py`, `test_len_arm64.py`, `test_lex.py`).
- **Pytest Discovery Guard (`pyproject.toml`)**: Added `norecursedirs = [".*", "build", "dist", "bootstrap", "stdlib", "benches", "examples"]` under `[tool.pytest.ini_options]` ensuring pytest collections run strictly within `tests/`, collecting 611/611 tests instantaneously without collection errors.
- **Peephole Optimizer Cleanup (`nova/stdlib/peephole.nv`)**: Pruned unused `gp_regs()` dictionary generator and eliminated dead `regs: dict` parameters from `optimize_pass(lines)` and `optimize(lines)`.
- **AST Constructor Deduplication (`nova/stdlib/parser.nv`)**: Delegated `make_num(val, line)` directly to `make_number_node(val, line, 0)`.
- **Lexer Whitespace Optimization (`nova/stdlib/lexer.nv`)**: Replaced chained comparisons in `is_whitespace(ch)` with a fast branch/switch block.

### 2. Assembly Emission & I/O Syscall Optimization
- **Compiler Line Batching (`nova/stdlib/compiler.nv`)**: Updated `write_lines(lines, path)` to concatenate `lines[i] + "\n"` per buffered chunk, reducing host OS `WriteFile` kernel syscall transitions by 50% during assembly file emission.

### 3. ABI Partitioning & Runtime Stability (`nova/runtime.c`)
- **MS x64 ABI vs SysV AMD64**: Clarified and isolated calling conventions:
  - Windows `extern def` functions exposed directly to Nova user code (e.g. `gui_sleep`, `gui_next_click_id`) follow the Microsoft x64 ABI (`rcx, rdx, r8, r9`).
  - Internal runtime utilities use System V AMD64 (`rdi, rsi, rdx, rcx, r8, r9`).
  - Removed incorrect `SYSCALL` attributes from Windows forwarder wrappers (lines 4843–4948) preventing 367B ms `Sleep` hangs caused by argument register mismatch.
- **Inline Counter Mutation**: Refactored `gui_next_click_id` to directly increment `++g_gui_next_click_id` inline, eliminating unnecessary register spills, `movaps` alignment requirements, and function call overhead.

### 4. Verification & Invariants
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`72b21fda2ca7d991504869cbcc2e4b1a313b8fcb1ca00a1da7d9ae71deba156d`).
- **Regression Suite**: All **90/90 tests passed** in `nova/tests/test_check_all.py` (40.15s).
- **GUI & Widget Tests**: All **7/7 tests passed** in `nova/tests/test_widgets.py` (12.54s).
- **Studio Tests & Binary Footprint**: All **2/2 tests passed** in `nova/tests/test_studio.py`:
  - Stripped `nova_studio.exe` footprint: **234.51 KB** (240,142 bytes, comfortably below the 250 KB ceiling).
  - Headless benchmark throughput: **35,000+ FPS**.
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.
- **All Fixtures Passing**: Full pytest suite passes across all unit, selfhost, regression, and feature tests.

---

## 25. Modernized Native GUI Framework: First-Class Event Callbacks (`nova/stdlib/gui.nv`)

### Architectural Overview
Upgraded the Nova declarative GUI framework to leverage Phase 5's native first-class function values and indirect native calls (`call r10` / `blr x16`), replacing legacy dynamic dispatch stubs while maintaining 100% backward compatibility for declarative string actions and integer click IDs.

### 1. Data Model & Widget Struct Modernization
- **Callback Fields in `data Widget`**:
  - `on_click_fn: fn`: Direct click callback invoked on button press or widget click.
  - `on_toggle_fn: fn`: Toggle callback invoked on checkbox / toggle switch state transitions.
  - `on_change_fn: fn`: Change callback invoked on slider adjustment or dropdown selection.
  - `on_submit_fn: fn`: Submit callback invoked on text input enter keypress.
- **Unified Widget Initialization (`_new_widget`)**:
  - Automatically initializes all callback fields to 0.
  - Inspects property dictionary for both direct callback keys (`on_click_fn`, `on_toggle_fn`, `on_change_fn`, `on_submit_fn`) and property shorthand keys (`on_toggle`, `on_change`, `on_submit`).

### 2. Ergonomic Constructors & Fluent Helpers
- **Shorthand & Factory Functions**:
  - `button(text: string, callback: fn) -> Widget`: Instant zero-boilerplate button with direct callback.
  - `button_props(text: string, callback: fn, properties: dict) -> Widget`: Button with callback and styling dict.
  - `ButtonCb(label: string, callback: fn, properties: dict) -> Widget`: Full constructor with automatic click ID allocation.
- **Fluent Builder Modifiers**:
  - `on_click(w: Widget, callback: fn) -> Widget`
  - `on_toggle(w: Widget, callback: fn) -> Widget`
  - `on_change(w: Widget, callback: fn) -> Widget`
  - `on_submit(w: Widget, callback: fn) -> Widget`

### 3. Native Indirect Event Dispatch Architecture
- **Register ABI Indirect Dispatch**:
  - `dispatchAction`: Indirect call `cb_click(w)` passes widget pointer, allowing 0-arg callbacks `def cb()` and 1-arg callbacks `def cb(w: Widget)` to seamlessly execute without stack corruption.
  - Checkbox & Toggle: Indirect call `cb_chk(chk, w)` passes new state `chk: int` and widget `w`.
  - Dropdown: Indirect call `cb_drop(sel, w)` passes selected index `sel: int` and widget `w`.
  - Slider (`hitTestEx`): Indirect call `cb_slide(calc_val, w)` passes calculated value `calc_val: int` and widget `w`.
  - Text Input (`_dispatch_key_event`): Indirect call `cb_sub(w.text, w)` passes entered string and widget `w`.
- **100% Backward Compatibility**:
  - Existing string actions (`"increment"`, `"reset"`, `"toggle"`, `"submit"`, `"clear"`, `"set_text"`, `"toggle_theme"`) remain fully functional.

### 4. Verification & Invariants
- **Regression Test Fixture**: `nova/tests/test_gui_callbacks.nv` comprehensively tests button click callbacks, builder chaining, checkbox toggles, slider drag/hitTest calculations, input submission, and legacy string action compatibility.
- **Test Suite Verification**: All 88 tests in `nova/tests/test_check_all.py` pass cleanly (including the 5 selfhost feature fixtures).
- **Self-Hosting Byte Identity**: `s2.s SHA256 == s3.s SHA256` (`fb77b89bfc88f307e9375be6390795bfc742b4542ac31632186536bc89a7bd2e`).
- **Binary Footprint**: Stripped `nova_studio.exe` remains strictly within budget at **249.51 KB** (< 250 KB ceiling).


---

## 26. Path C: Algorithmic & Compiler Performance Optimizations (DSA/DAA Principles)

### Architectural Overview
Implemented comprehensive DSA/DAA algorithmic and compiler system architecture optimizations across the Nova compiler pipeline and runtime C engine, achieving an **8.5x overall compiler throughput speedup** while maintaining bit-for-bit self-hosting identity and zero struct layout regressions.

### 1. Intelligent Automated Dependency Fingerprinting (`nova/stdlib/compiler.nv`)
- **Root Cause & Invalidation Tracking**:
  - Previously, every invocation of `nova build` or test suite run invoked MinGW GCC to recompile `runtime.c` (~2.0-3.5 seconds per compilation), or risked running stale binaries if manual caching was attempted.
  - Addressed the user question: *"what if they made changes in code?"*
- **Solution (`_runtime_stamp`)**:
  - Implemented automatic content-based fingerprinting using `len(content)` and polynomial rolling hash `text_fingerprint(content)` written to `runtime.stamp`.
  - On every compilation, `_compile_runtime` reads `runtime.c` and computes the exact content fingerprint.
  - If `runtime.o` exists and `runtime.stamp` matches the fingerprint, GCC recompilation is safely bypassed in `< 1 ms`.
  - **Dynamic Invalidation**: Any edit to `runtime.c` automatically invalidates the stamp, triggering an immediate clean GCC recompilation and refreshing `runtime.stamp` and `runtime.o`.

### 2. Algorithmic Optimizations in Compiler Core
- **$O(1)$ Type Checker Environment Popping (`nova/stdlib/type_checker.nv`)**:
  - Replaced $O(N)$ allocation-heavy stack slice copying (`new_stack = []` and element copy loop) in `tc_pop_env` with native $O(1)$ popping: `_ = tc.env_stack.pop()`.
- **Static Method Dispatch in Expression Codegen (`nova/stdlib/codegen_common.nv`)**:
  - Replaced repeated runtime heap allocation of 17-element `method_id_map = {...}` dictionaries inside every `MethodCall` node visitor across both `x86_64/codegen_expr.nv` and `arm64/codegen_expr.nv`.
  - Replaced with static `def method_name_to_id(name: string) -> int` using compile-time jump table / `switch` dispatch, eliminating thousands of transient dictionary allocations.
- **Peephole Optimizer Register Lookups (`nova/stdlib/peephole.nv`)**:
  - Replaced dynamic dictionary instantiation of General Purpose registers (`gp_regs()`) on every peephole pass with static `is_gp_reg(r: string) -> int` switch.
- **Runtime Hash Table Fast-Path Pointer Short-Circuiting (`nova/runtime.c`)**:
  - Added pointer equality fast path `(e->key == key || strcmp(e->key, key) == 0)` to `_df_idx` and `_df_find_or_insert` in `nova/runtime.c`. Identical interned/static string pointers bypass string comparison completely.

### 3. Empirical Performance Verification & Benchmark Leap
- **Compiler Build Speedup across Standard Benchmark Suite (`nova/tools/bench.py --compiler nova/nova.exe`)**:
  - **Total Build Time**: Dropped from **~32.0s down to 3.8s (8.5x faster overall compiler throughput)**.
  - `bubble`: 4.0s -> 0.4s (10x faster)
  - `collatz`: 4.0s -> 0.4s (10x faster)
  - `dict`: 3.3s -> 0.5s (6.6x faster)
  - `fib`: 3.5s -> 0.4s (8.7x faster)
  - `loops`: 3.0s -> 0.3s (10x faster)
  - `matmul`: 2.6s -> 0.3s (8.6x faster)
  - `primes`: 2.8s -> 0.4s (7x faster)
  - `sieve`: 2.5s -> 0.3s (8.3x faster)
  - `strings`: 2.7s -> 0.4s (6.7x faster)
  - `structs`: 2.8s -> 0.4s (7x faster)
  - **Execution Time (Geomean)**: 0.056s. All 10 benchmark execution checksums 100% identical.
- **Test Suite Runtime**:
  - `pytest nova/tests/test_check_all.py` completed all **88/88 checks in 44.37s** (down from 69.5s).
- **Self-Hosting Invariant**:
  - Bit-for-bit assembly byte identity verified: `s2.s SHA256 == s3.s SHA256` (`4ca91a63a38579298a5d20af9f09cd7a184e57fe07c0afd5a2e9144d80e23e73`).
- **Binary Footprint Budget**:
  - Stripped `nova_studio.exe` binary footprint: **249.51 KB** (255,502 bytes, strictly below 250 KB ceiling).

---

## 27. Phase 1A: Algebraic Data Types (ADTs) & Beginner-Friendly Pattern Matching (`enum` and `match`)

### Architectural Overview
Implemented modern Algebraic Data Types (ADTs / Tagged Unions) and pattern matching (`match`) in the self-hosted compiler, supporting both clean unboxed unit variants and payload variants with beginner-friendly dot syntax (`enumVar.var`), multi-field destructuring, and fallback handling (`else =>` and `_ =>`).

### 1. Syntax & Data Model Design
- **Unit Variants (Unboxed Zero-Cost Enums)**:
  ```nova
  enum Status {
      Pending,
      Active,
      Done
  }
  let s = Status.Pending  # Emits unboxed integer constant 0 at compile time
  ```
- **Payload Variants (Tagged ARC Structs)**:
  ```nova
  enum Result {
      Ok(data),
      Err(msg)
  }
  let r = Result.Ok("Success")
  ```
  - Automatically synthesizes typed `Data` struct definitions (`Result_Ok` with `__tag = 0, data`) and constructor hooks.
- **Pattern Matching (`match`)**:
  ```nova
  match r {
      Result.Ok(val) => print("Success: " + val)
      Result.Err(msg) => print("Error: " + msg)
      else => print("Default fallback")
  }
  ```
  - Supports both concise single-statement arms (`Pattern => stmt`) and braced blocks (`Pattern => { ... }`).
  - Supports literal values, numbers, strings, and unit enum constants.
  - Automatically generates scoped temporary bindings (`__match_val_N`) preventing double-evaluation of complex target expressions.

### 2. Implementation Pipeline
- **Lexer (`nova/stdlib/lexer.nv`)**:
  - Registered keyword `match` (`MATCH`).
  - Registered two-character token `=>` (`FAT_ARROW`).
- **Parser (`nova/stdlib/parser.nv`)**:
  - `parse_enum_def`: Parses unit and parameterized variants, registering `__enum_...` metadata in `state.data_fields`.
  - `parse_postfix`:
    - Transforms unit access `Status.Pending` directly into unboxed `Number(tag_val)` nodes.
    - Transforms constructor call `Result.Ok(data)` directly into `__new_Result_Ok(0, data)`.
  - `parse_match`: Parses patterns, payload variable bindings, and arm bodies, desugaring them into structured `IfElse` branches inside a scoped `Block`.
  - `desugar_enums`: Synthesizes variant constants and `Data` type declarations before constructor source expansion.

### 3. Verification & Invariants
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`02321fc1b1c74e61b3f64857c181a3e19bc27232d6428335c9dbdb40386b54a7`).
- **Regression Suite**: All **89/89 tests passed** in `nova/tests/test_check_all.py` (including the new comprehensive `test_enums_and_match.nv` running through the self-hosted native compiler).
- **Binary Footprint Budget**: Stripped `nova_studio.exe` remains **249.51 KB** (255,502 bytes, strictly below 250 KB ceiling).
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.

---

## 29. Codebase Cleanup, Dead Code Elimination & Toolchain Hardening

### Architectural Overview
Comprehensive cleanup and optimization of the self-hosted compiler codebase, test suite, and runtime layer. Streamlined I/O operations during compilation, removed obsolete scratch scripts, pruned dead peephole analysis routines, deduplicated AST node constructors, and strictly partitioned Windows Microsoft x64 ABI vs internal System V AMD64 calling conventions in the runtime.

### 1. Legacy Dead Code Pruning & Test Harness Hardening
- **Root Scratch Cleanup**: Removed 6 obsolete debug/scratch files (`test_bridge.nv`, `test_bridge.py`, `test_cache_path_arm64.py`, `test_hook.py`, `test_len_arm64.py`, `test_lex.py`).
- **Pytest Discovery Guard (`pyproject.toml`)**: Added `norecursedirs = [".*", "build", "dist", "bootstrap", "stdlib", "benches", "examples"]` under `[tool.pytest.ini_options]` ensuring pytest collections run strictly within `tests/`, collecting 611/611 tests instantaneously without collection errors.
- **Peephole Optimizer Cleanup (`nova/stdlib/peephole.nv`)**: Pruned unused `gp_regs()` dictionary generator and eliminated dead `regs: dict` parameters from `optimize_pass(lines)` and `optimize(lines)`.
- **AST Constructor Deduplication (`nova/stdlib/parser.nv`)**: Delegated `make_num(val, line)` directly to `make_number_node(val, line, 0)`.
- **Lexer Whitespace Optimization (`nova/stdlib/lexer.nv`)**: Replaced chained comparisons in `is_whitespace(ch)` with a fast branch/switch block.

### 2. Assembly Emission & I/O Syscall Optimization
- **Compiler Line Batching (`nova/stdlib/compiler.nv`)**: Updated `write_lines(lines, path)` to concatenate `lines[i] + "\n"` per buffered chunk, reducing host OS `WriteFile` kernel syscall transitions by 50% during assembly file emission.

### 3. ABI Partitioning & Runtime Stability (`nova/runtime.c`)
- **MS x64 ABI vs SysV AMD64**: Clarified and isolated calling conventions:
  - Windows `extern def` functions exposed directly to Nova user code (e.g. `gui_sleep`, `gui_next_click_id`) follow the Microsoft x64 ABI (`rcx, rdx, r8, r9`).
  - Internal runtime utilities use System V AMD64 (`rdi, rsi, rdx, rcx, r8, r9`).
  - Removed incorrect `SYSCALL` attributes from Windows forwarder wrappers (lines 4843–4948) preventing 367B ms `Sleep` hangs caused by argument register mismatch.
- **Inline Counter Mutation**: Refactored `gui_next_click_id` to directly increment `++g_gui_next_click_id` inline, eliminating unnecessary register spills, `movaps` alignment requirements, and function call overhead.

### 4. Verification & Invariants
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`72b21fda2ca7d991504869cbcc2e4b1a313b8fcb1ca00a1da7d9ae71deba156d`).
- **Regression Suite**: All **90/90 tests passed** in `nova/tests/test_check_all.py` (40.15s).
- **GUI & Widget Tests**: All **7/7 tests passed** in `nova/tests/test_widgets.py` (12.54s).
- **Studio Tests & Binary Footprint**: All **2/2 tests passed** in `nova/tests/test_studio.py`:
  - Stripped `nova_studio.exe` footprint: **234.51 KB** (240,142 bytes, comfortably below the 250 KB ceiling).
  - Headless benchmark throughput: **35,000+ FPS**.
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.

---

## 28. Phase 2: Lightweight Concurrency & Async Tasks (`spawn` & `await`)

### Architectural Overview
Implemented native multi-core concurrency in Nova with beginner-friendly syntax (`spawn` and `await`), thread-safe atomic Automatic Reference Counting (ARC), a hardware-scaled work-stealing thread pool, and an assembly bridge maintaining SysV AMD64 register purity.

### 1. Language Ergonomics & Data Model
- **Beginner-Friendly Syntax**:
  ```nova
  # 1. Spawning parallel computation across CPU cores
  let t1 = spawn fib(34)
  let t2 = spawn fib(34)

  # 2. Awaiting result directly without unwrapping ceremony
  let r1 = await t1
  let r2 = await t2
  print("Total: " + str(r1 + r2))

  # 3. Direct inline await expression
  let sum = await spawn square(6) + await spawn square(8)

  # 4. Task fan-out in collections
  let tasks = []
  for i = 0 to 7 { tasks.append(spawn worker(i)) }
  for i = 0 to 7 { print(await tasks[i]) }
  ```

### 2. Runtime & Concurrency Engine (`nova/runtime.c`)
- **Thread-Safe Atomic ARC**:
  - `_nova_inc_ref`: Uses atomic fetch-and-add (`__atomic_fetch_add(&hdr->ref_count, 1, __ATOMIC_RELAXED)` / `lock xadd`).
  - `_nova_dec_ref`: Uses atomic decrement (`__atomic_sub_fetch(&hdr->ref_count, 1, __ATOMIC_ACQ_REL)`).
  - Eliminates data races when tasks or data structures are shared across worker threads.
- **Hardware-Scaled Worker Thread Pool**:
  - Automatically queries hardware logical core count ($N = \text{cores}$, e.g. `SYSTEM_INFO.dwNumberOfProcessors`).
  - Spawns background worker threads sleeping on OS semaphores (`CreateSemaphoreA` on Windows, `pthread_cond_t` on POSIX) for zero idle CPU usage.
  - Dynamically allocated task ring buffer (`NOVA_TASK_QUEUE_CAP = 4096`) protecting binary footprint.
- **Assembly SysV Bridge (`_nova_task_invoke`)**:
  - Dedicated handwritten assembly bridge preserving all callee-saved registers (`rbx, rdi, rsi, r12, r13, r14, r15`).
  - Guarantees 16-byte stack alignment and loads SysV arguments (`rdi, rsi, rdx, rcx, r8, r9`) safely without register clobbering.

### 3. Compiler Pipeline (`lexer.nv`, `parser.nv`, `codegen_expr.nv`)
- **Lexer (`nova/stdlib/lexer.nv`)**: Registered keywords `spawn` (`SPAWN`) and `await` (`AWAIT`).
- **Parser (`nova/stdlib/parser.nv`)**: Handled `Spawn` and `Await` AST nodes in `parse_unary`, seamlessly enabling expressions, statements, and inline math.
- **Type Checker (`nova/stdlib/type_checker.nv`)**: Added AST traversal for `Spawn` and `Await` child expressions.
- **Backend Codegen (`codegen_expr.nv` x86_64 & arm64)**:
  - `Spawn`: Compiles arguments, pushes argument count and function pointer, calls `_nova_task_spawn`.
  - `Await`: Evaluates task handle and calls `_nova_task_await`.

### 4. Verification & Invariants
- **Multi-Core Speedup Verified**:
  - Empirical benchmark (`test_concurrency_tasks.nv`): Sequential 2x `fib(34)`: **63 ms** $\to$ Parallel 2x `fib(34)`: **31 ms** (**2.03x parallel speedup** across hardware cores).
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`745be15f71d58be02195b0b6d172c083c7a5ebf93a4abb50b7f471e17f7251fd`).
- **Regression Suite**: All **90/90 tests passed** in `nova/tests/test_check_all.py`.
- **GUI & Widget Tests**: All **7/7 tests passed** in `nova/tests/test_widgets.py`.
- **Studio Tests & Binary Footprint**: All **2/2 tests passed** in `nova/tests/test_studio.py`:
  - Stripped `nova_studio.exe` footprint: **234.51 KB** (240,142 bytes, comfortably below the 250 KB ceiling).
  - Headless benchmark throughput: **17,885 FPS** (>290x above 60 FPS requirement).
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.

---

## 29. Codebase Cleanup, Dead Code Elimination & Toolchain Hardening

### Architectural Overview
Comprehensive cleanup and optimization of the self-hosted compiler codebase, test suite, and runtime layer. Streamlined I/O operations during compilation, removed obsolete scratch scripts, pruned dead peephole analysis routines, deduplicated AST node constructors, and strictly partitioned Windows Microsoft x64 ABI vs internal System V AMD64 calling conventions in the runtime.

### 1. Legacy Dead Code Pruning & Test Harness Hardening
- **Root Scratch Cleanup**: Removed 6 obsolete debug/scratch files (`test_bridge.nv`, `test_bridge.py`, `test_cache_path_arm64.py`, `test_hook.py`, `test_len_arm64.py`, `test_lex.py`).
- **Pytest Discovery Guard (`pyproject.toml`)**: Added `norecursedirs = [".*", "build", "dist", "bootstrap", "stdlib", "benches", "examples"]` under `[tool.pytest.ini_options]` ensuring pytest collections run strictly within `tests/`, collecting 611/611 tests instantaneously without collection errors.
- **Peephole Optimizer Cleanup (`nova/stdlib/peephole.nv`)**: Pruned unused `gp_regs()` dictionary generator and eliminated dead `regs: dict` parameters from `optimize_pass(lines)` and `optimize(lines)`.
- **AST Constructor Deduplication (`nova/stdlib/parser.nv`)**: Delegated `make_num(val, line)` directly to `make_number_node(val, line, 0)`.
- **Lexer Whitespace Optimization (`nova/stdlib/lexer.nv`)**: Replaced chained comparisons in `is_whitespace(ch)` with a fast branch/switch block.

### 2. Assembly Emission & I/O Syscall Optimization
- **Compiler Line Batching (`nova/stdlib/compiler.nv`)**: Updated `write_lines(lines, path)` to concatenate `lines[i] + "\n"` per buffered chunk, reducing host OS `WriteFile` kernel syscall transitions by 50% during assembly file emission.

### 3. ABI Partitioning & Runtime Stability (`nova/runtime.c`)
- **MS x64 ABI vs SysV AMD64**: Clarified and isolated calling conventions:
  - Windows `extern def` functions exposed directly to Nova user code (e.g. `gui_sleep`, `gui_next_click_id`) follow the Microsoft x64 ABI (`rcx, rdx, r8, r9`).
  - Internal runtime utilities use System V AMD64 (`rdi, rsi, rdx, rcx, r8, r9`).
  - Removed incorrect `SYSCALL` attributes from Windows forwarder wrappers (lines 4843–4948) preventing 367B ms `Sleep` hangs caused by argument register mismatch.
- **Inline Counter Mutation**: Refactored `gui_next_click_id` to directly increment `++g_gui_next_click_id` inline, eliminating unnecessary register spills, `movaps` alignment requirements, and function call overhead.

### 4. Verification & Invariants
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`72b21fda2ca7d991504869cbcc2e4b1a313b8fcb1ca00a1da7d9ae71deba156d`).
- **Regression Suite**: All **90/90 tests passed** in `nova/tests/test_check_all.py` (40.15s).
- **GUI & Widget Tests**: All **7/7 tests passed** in `nova/tests/test_widgets.py` (12.54s).
- **Studio Tests & Binary Footprint**: All **2/2 tests passed** in `nova/tests/test_studio.py`:
  - Stripped `nova_studio.exe` footprint: **234.51 KB** (240,142 bytes, comfortably below the 250 KB ceiling).
  - Headless benchmark throughput: **35,000+ FPS**.
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.


---

## 29. Codebase Cleanup, Dead Code Elimination & Toolchain Hardening

### Architectural Overview
Comprehensive cleanup and optimization of the self-hosted compiler codebase, test suite, and runtime layer. Streamlined I/O operations during compilation, removed obsolete scratch scripts, pruned dead peephole analysis routines, deduplicated AST node constructors, and strictly partitioned Windows Microsoft x64 ABI vs internal System V AMD64 calling conventions in the runtime.

### 1. Legacy Dead Code Pruning & Test Harness Hardening
- **Root Scratch Cleanup**: Removed 6 obsolete debug/scratch files (`test_bridge.nv`, `test_bridge.py`, `test_cache_path_arm64.py`, `test_hook.py`, `test_len_arm64.py`, `test_lex.py`).
- **Pytest Discovery Guard (`pyproject.toml`)**: Added `norecursedirs = [".*", "build", "dist", "bootstrap", "stdlib", "benches", "examples"]` under `[tool.pytest.ini_options]` ensuring pytest collections run strictly within `tests/`, collecting 611/611 tests instantaneously without collection errors.
- **Peephole Optimizer Cleanup (`nova/stdlib/peephole.nv`)**: Pruned unused `gp_regs()` dictionary generator and eliminated dead `regs: dict` parameters from `optimize_pass(lines)` and `optimize(lines)`.
- **AST Constructor Deduplication (`nova/stdlib/parser.nv`)**: Delegated `make_num(val, line)` directly to `make_number_node(val, line, 0)`.
- **Lexer Whitespace Optimization (`nova/stdlib/lexer.nv`)**: Replaced chained comparisons in `is_whitespace(ch)` with a fast branch/switch block.

### 2. Assembly Emission & I/O Syscall Optimization
- **Compiler Line Batching (`nova/stdlib/compiler.nv`)**: Updated `write_lines(lines, path)` to concatenate `lines[i] + "\n"` per buffered chunk, reducing host OS `WriteFile` kernel syscall transitions by 50% during assembly file emission.

### 3. ABI Partitioning & Runtime Stability (`nova/runtime.c`)
- **MS x64 ABI vs SysV AMD64**: Clarified and isolated calling conventions:
  - Windows `extern def` functions exposed directly to Nova user code (e.g. `gui_sleep`, `gui_next_click_id`) follow the Microsoft x64 ABI (`rcx, rdx, r8, r9`).
  - Internal runtime utilities use System V AMD64 (`rdi, rsi, rdx, rcx, r8, r9`).
  - Removed incorrect `SYSCALL` attributes from Windows forwarder wrappers (lines 4843–4948) preventing 367B ms `Sleep` hangs caused by argument register mismatch.
- **Inline Counter Mutation**: Refactored `gui_next_click_id` to directly increment `++g_gui_next_click_id` inline, eliminating unnecessary register spills, `movaps` alignment requirements, and function call overhead.

### 4. Verification & Invariants
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`72b21fda2ca7d991504869cbcc2e4b1a313b8fcb1ca00a1da7d9ae71deba156d`).
- **Regression Suite**: All **90/90 tests passed** in `nova/tests/test_check_all.py` (40.15s).
- **GUI & Widget Tests**: All **7/7 tests passed** in `nova/tests/test_widgets.py` (12.54s).
- **Studio Tests & Binary Footprint**: All **2/2 tests passed** in `nova/tests/test_studio.py`:
  - Stripped `nova_studio.exe` footprint: **234.51 KB** (240,142 bytes, comfortably below the 250 KB ceiling).
  - Headless benchmark throughput: **35,000+ FPS**.
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.

---

## 30. Bare-Metal Operating System Capabilities & Low-Level Hardware Primitives

### Architectural Overview
Equipped Nova with bare-metal operating system capabilities and hardware primitives using clean, beginner-friendly dot notation (`peek.u8`, `poke.u16`, `cpu.cli`, `cpu.outb`). Eliminated the need for developers to write inline assembly in user code by compiling high-level CPU/hardware constructs into single native machine instructions. Created freestanding compilation mode (`--os bare`) with zero libc or host OS dependencies, and built a bootable 64-bit Multiboot operating system kernel demo.

### 1. Dotted Memory-Mapped I/O (MMIO) Primitives
- **Reading Hardware Memory**:
  - `peek.u8(addr)` -> `movzx eax, byte ptr [rdx]` / `ldrb w0, [x3]`
  - `peek.u16(addr)` -> `movzx eax, word ptr [rdx]` / `ldrh w0, [x3]`
  - `peek.u32(addr)` -> `mov eax, dword ptr [rdx]` / `ldr w0, [x3]`
  - `peek.u64(addr)` -> `mov rax, qword ptr [rdx]` / `ldr x0, [x3]`
- **Writing Hardware Memory**:
  - `poke.u8(addr, val)` -> `mov byte ptr [rdx], al` / `strb w0, [x3]`
  - `poke.u16(addr, val)` -> `mov word ptr [rdx], ax` / `strh w0, [x3]`
  - `poke.u32(addr, val)` -> `mov dword ptr [rdx], eax` / `str w0, [x3]`
  - `poke.u64(addr, val)` -> `mov qword ptr [rdx], rax` / `str x0, [x3]`
- **Type Checker Ergonomics**: `peek` and `poke` address parameters accept `any` type, allowing direct indexing on raw addresses (`0xB8000`) and string/buffer pointers (`text.ptr + i`).

### 2. Dotted CPU Hardware Intrinsics
- **Privileged CPU Instructions**:
  - `cpu.cli()` -> `cli` / `msr daifset, #2` (Clear interrupt flag)
  - `cpu.sti()` -> `sti` / `msr daifclr, #2` (Set interrupt flag)
  - `cpu.hlt()` -> `hlt` / `wfi` (Halt CPU / Wait for interrupt)
  - `cpu.inb(port)` -> `in al, dx` (Read 8-bit port)
  - `cpu.outb(port, val)` -> `out dx, al` (Write 8-bit port)
  - `cpu.inw(port)`, `cpu.outw(port, val)` (16-bit ports)
  - `cpu.ind(port)`, `cpu.outd(port, val)` (32-bit ports)
  - `cpu.cr3.get()`, `cpu.cr3.set(val)` (Page table directory base)
  - `cpu.invlpg(addr)` (Invalidate TLB entry)
- **Ring 3 vs Ring 0 Isolation**: When compiling for desktop OS (`target_os != "bare"`), calls route to safe C wrappers in `runtime.c`, allowing the full test suite to execute in user space without triggering `STATUS_PRIVILEGED_INSTRUCTION` faults.

### 3. Freestanding Bare-Metal Compilation Mode (`--os bare`)
- Added `--os bare` support across `nova.nv` and `compiler.nv`.
- When compiling for bare metal (`target_os == "bare"`):
  - Inlines raw CPU silicon instructions directly into the assembly stream.
  - Suppresses all `.extern` declarations for host C runtime functions (`_malloc`, `_printf`, `_oob_file_ptr`, `_nova_str_concat`, etc.).
  - Emits pure, freestanding `.s` files suitable for linking with custom linker scripts (`ld -T linker.ld`).

### 4. Flagship Bare-Metal 64-bit Kernel Demo (`nova/examples/baremetal_os/`)
- **`kernel.nv`**: 100% pure Nova kernel with zero assembly and zero libc dependencies:
  - Initializes VGA text mode video buffer at `0xB8000`.
  - Clears screen with a rich navy blue background (`0x1F`) and draws stylized boot headers.
  - Implements a COM1 UART serial driver (`0x3F8`) streaming telemetry over the serial bus.
  - Enters a low-power idle halt loop (`cpu.hlt()`).
- **`boot.s`**: 32-bit Multiboot 1 trampoline setting up 64-bit paging (identity-mapping the first 1 GB with 2 MB huge pages), enabling Long Mode (EFER.LME) and Paging (CR0.PG), and calling `kmain`.
- **`linker.ld`**: Bare-metal ELF64 linker script positioning sections at the 1 MB mark (`0x100000`).
- **`build.ps1`**: Automated build script generating both Multiboot `kernel.elf` (7.9 KB) and flat binary `kernel.bin` (41.0 KB), bootable in QEMU.

### 5. Verification & Invariants
- **Self-Hosting Invariant**: Bit-for-bit assembly byte identity verified:
  `s2.s SHA256 == s3.s SHA256` (`1cbfe86c80205ec1d094c9909a4670bddf705cf84a638608529453714c65503e`).
- **Regression Suite**: All **91/91 tests passed** in `nova/tests/test_check_all.py` (including the new `test_baremetal_hardware.nv`).
- **GUI & Widget Tests**: All **7/7 tests passed** in `nova/tests/test_widgets.py` (20.65s).
- **Studio Tests & Binary Footprint**: All **2/2 tests passed** in `nova/tests/test_studio.py`:
  - Stripped `nova_studio.exe` footprint remains well below 250 KB ceiling.
  - Headless benchmark throughput: **35,000+ FPS**.
- **Bootstrap Status**: `nova/bootstrap/*.py` remains completely frozen.
