# Nova Native Codegen Internals (`stdlib/backend/`)

Codegen is organized by architecture under `stdlib/backend/<arch>/`. Each backend directory contains:

- `codegen.nv` — main codegen state machine, instruction dispatch, runtime helpers
- `codegen_expr.nv` — expression tree → assembly (compile_expr, node_to_asm)
- `codegen_stmt.nv` — statement → assembly (compile_stmt)

The same source tree is shared between architectures via the `state` object's register names — `state.rax`, `state.rbx`, etc. resolve to `rax`/`rbx` on x86_64 or `x0`/`x1` on ARM64.

Supported backends:
- **x86_64** (primary) — SysV calling convention, MinGW GCC compatible, fully verified self-hosted
- **ARM64** (secondary) — tested via CI on macOS runners

## State Management

`CodegenState` struct tracks:
- `asm_lines` / `data_lines` — assembly and data section output buffers
- `local_vars` / `local_var_names` — maps variable names to `state.bp`-relative stack offsets (x86_64: `rsp`, ARM64: `sp`) with a `local_var_base` shift to prevent overlap with saved parameter area
- `local_var_regs` — tracks which variables are promoted to CPU registers (per-architecture, e.g. `r12`/`r13` on x86_64)
- `used_regs` — track of CPU registers used in the current function frame
- `local_offset` — total local stack frame size
- `label_counter` — unique label generator for control flow
- `loop_labels` / `loop_end_labels` — stack of labels for `break`/`continue`
- `param_names` / `param_offsets` — function parameter layout (saved at negative offsets from `rbp`)
- `struct_names`, `struct_field_names`, `struct_field_offsets` — per-struct field layout tables

## Pass 1: Variable Scanning (`scan_vars`)

Recursively walks the AST of a block to find `Assignment` nodes and register local variables. Uses `local_var_base = 16 + n_params * 8` shift so local variable offsets start above the saved parameter area, preventing overlap bugs. Updates `local_offset` for stack frame allocation.

## Pass 2: Instruction Generation

Uses the target architecture's calling convention (SysV on x86_64: args in `rdi`/`rsi`/`rdx`/`rcx`/`r8`/`r9`). All expressions push results onto the stack.

### Expression Evaluation
- **Integer literal**: `push imm64` (x86_64) or `mov x0, #imm`
- **Variable**: `mov rax, [state.bp + offset]` / `push rax` (rsp-relative on x86_64, sp-relative on ARM64)
- **BinOp**: push left → push right → pop into registers → compute → push result
- **String literal**: references `.data` section label, pushes address
- **Slice `s[i:j]`**: pushes end, start, base → calls `_slice_string` → `add rsp, 24` → pushes result
- **Concat**: calls `_concat_strings` runtime helper written in C (`runtime.c`)
- **HashMap/Dict**: `{"key": val}` — all 4 backends (x86_64 .nv, ARM64 .nv, x86_64 Python, ARM64 Python) emit `_dict_new`/`_dict_set`/`_dict_get`/`_dict_has`/`_dict_remove`/`_dict_keys`/`_dict_values`/`_dict_items` native calls. No VM fallback or placeholder.

### Statements
- **Function `def` (x86_64)**: Prologue (`sub rsp, local_offset` — no `push rbp; mov rbp, rsp`), body, epilogue (`add rsp, local_offset` / `ret`). Frame pointer optimization uses `state.bp="rsp"`, saving 2 instructions per call and freeing `rbp` as GP register.
- **Function `def` (ARM64)**: Prologue (`stp fp, lr, [sp, #-16]!` / `sub sp, sp, local_offset` — no `mov fp, sp`), body, epilogue (`add sp, sp, local_offset` / `ldp fp, lr, [sp], #16` / `ret`). Saves 1 instruction per call.
- **Parameter save/restore**: Parameters are saved to `[state.bp - N]` slots before body compilation; restored after to prevent callee-side clobbering
- **Assignment**: Compile RHS → pop → `mov [state.bp + offset], reg`
- **If/While**: Compile condition → `cmp reg, 0` → conditional jump
- **`print`**: Selects format string based on inferred type; calls `_printf` via `runtime.c` wrapper
- **ForIn loop**: Pushes list pointer, iterates via index comparison

## Runtime Helpers (C wrappers in `runtime.c`)

Platform-independent C helpers compiled alongside user assembly:
- `_concat_strings(base, append)` — allocates new buffer, copies both strings, null-terminates
- `_slice_string(base, start, end)` — allocates `end-start+1` bytes, byte-copies substring, null-terminates
- `_printf` / `_sprintf` — wrappers around libc `printf`/`sprintf` (all `%d` and `%s` unified to read from `rsi`)
- `_sys_get_args` — parses command line with proper `in_quote` tracking for paths with spaces
- `_system` — synchronous execution via `system()` (not async `WinExec`)
- Dict runtime functions: `_dict_new`, `_dict_set`, `_dict_get`, `_dict_has`, `_dict_remove`, `_dict_keys`, `_dict_values`, `_dict_items`

## Exceptions (try/catch/throw)

Exception handling uses C `setjmp`/`longjmp` via `runtime.c` wrappers:
- `_try_block()` — calls `setjmp(buf)`, returns 0 for try body or non-zero for catch path
- `_throw_error(val)` — calls `longjmp(buf, (intptr_t)val)` to unwind to the matching catch
- `_catch_error(buf)` — returns the thrown value from the catch variable

Codegen emits `_try_block` call at try entry, conditionally branches on return value to try body vs catch body. `throw` emits `_throw_error` call with the thrown value. ARM64 backend emits equivalent wrappers.

## Bounds Checking

Array reads and writes emit bounds-checking assembly:
```asm
cmp rcx, 0
jl _out_of_bounds
cmp rcx, [rdx]          ; compare with list length
jge _out_of_bounds
```

## Type System Integration

Expression codegen reads `node.inferred_type` to select format strings, detect string vs list indexing, and choose integer vs string comparison. The helper functions `is_string_expr()` and `is_float_expr()` check `inferred_type` for Variable nodes — critical for recognizing strings assigned without type annotations (e.g., `s = "hello"`).

The `type()` built-in resolves to a compile-time string constant in native codegen. Both x86_64 and ARM64 backends special-case `BuiltinCall("type", ...)` to emit `.asciz` strings (`"int"`, `"string"`, `"float"`, `"bool"`, `"list"`, `"dict"`, `"unknown"`) based on `node.args[0].inferred_type`. No runtime call needed.

## Variable-to-Register Promotion

Local variables are greedily mapped to CPU registers (`r12`/`r13` on x86_64) instead of stack offsets. Promoted registers are saved/restored in function prologue/epilogue.

## Native Standard Library Injection

Standard library helper functions (file I/O `sys_*` from `os_*.nv`, ChaCha20 from `math_utils.nv`) are compiled and injected directly into the assembly output of every compiled program. All platform data uses the Nova stdlib's authoritative implementations (e.g., `sys_platform()` from `os_windows.nv` returns `"windows"`), not hardcoded assembly.

## Cross-Compilation

The `CodegenState` struct carries a `target_os` field that influences:
- **GCC command**: `_find_gcc()` looks for a cross-toolchain; Windows uses `x86_64-w64-mingw32-gcc` if available
- **Output extension**: `.exe` on Windows, no extension on macOS/Linux
- **Linker flags**: `-mconsole -lkernel32` on Windows, none on Unix
- **Architecture**: `target_arch` selects x86_64 or ARM64 backend directory and assembler

`compile_to_exe` dispatches on `target_os`:
- **Windows**: Bundled MinGW GCC (`gcc/bin/gcc.exe`) or system PATH
- **macOS/Linux**: System `gcc` with no Windows-specific flags
- **ARM64 Windows**: Internal PE assembler+linker (no GCC needed)

## Key Fixes (Self-Hosting History)

- **Variable-to-register promotion overlap**: Local var offset shifted by `local_var_base = 16 + n_params * 8` to prevent overlap with saved parameters
- **`_printf` `%d` register fix**: `runtime.c` unified `%d` and `%s` handlers to both read from `rsi` (SysV second arg)
- **`_fopen` mode string fix**: Changed from exact match to first-char check, supporting all mode variants (`w`, `wb`, `w+`, `w+b`, etc.)
- **`_fputs` HANDLE dereference fix**: Removed extra dereference that caused `STATUS_ACCESS_VIOLATION`
- **`is_string_expr` `inferred_type` check**: Variable nodes without type annotations are now recognized via `inferred_type`
- **`_sys_platform` assembly removed**: Both backends now use Nova stdlib `sys_platform()` instead of hardcoded assembly
- **x86 (32-bit) support removed**: Only x86_64 and ARM64 are maintained. All x86-32 codegen and emitter code deleted.
- **Frame pointer optimization (x86_64)**: `state.bp` changed from `"rbp"` to `"rsp"`. No `push rbp; mov rbp, rsp` in prologue. Variables accessed via `[rsp + offset]` with `local_var_base` shift. Epilogue uses `add rsp, local_offset` instead of `mov rsp, rbp; pop rbp`.
- **Frame pointer optimization (ARM64)**: `state.bp` changed from `"fp"` to `"sp"`. No `mov fp, sp` in prologue. Variables accessed via `[sp, #+K]` with positive offsets from sp.
- **Dict key/value swap fix**: `_dict_set` parameter order in `ArrayIndexAssign` codegen fixed across all 4 backends — x86_64 Python, ARM64 Python, self-hosted x86_64, self-hosted ARM64.
