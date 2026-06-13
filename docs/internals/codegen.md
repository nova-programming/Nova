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
- `local_vars` / `local_var_names` — maps variable names to `rbp`-relative stack offsets with a `local_var_base` shift to prevent overlap with saved parameter area
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
- **Variable**: `mov rax, [rbp - offset]` / `push rax`
- **BinOp**: push left → push right → pop into registers → compute → push result
- **String literal**: references `.data` section label, pushes address
- **Slice `s[i:j]`**: pushes end, start, base → calls `_slice_string` → `add rsp, 24` → pushes result
- **Concat**: calls `_concat_strings` runtime helper written in C (`runtime.c`)
- **HashMap/Dict**: `{"key": val}` literals parsed and compiled; VM supports full dict operations

### Statements
- **Function `def`**: Prologue (`push rbp` / `mov rbp, rsp` / `sub rsp, local_offset`), body, epilogue (`mov rsp, rbp` / `pop rbp` / `ret`)
- **Parameter save/restore**: Parameters are saved to `[rbp - 8]`, `[rbp - 16]`, etc. before body compilation; restored after to prevent callee-side clobbering
- **Assignment**: Compile RHS → pop → `mov [rbp - offset], reg`
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

## Variable-to-Register Promotion

Local variables are greedily mapped to CPU registers (`r12`/`r13` on x86_64) instead of stack offsets. Promoted registers are saved/restored in function prologue/epilogue.

## Native Standard Library Injection

Standard library helper functions (file I/O `sys_*` from `os_*.nv`, ChaCha20 from `math_utils.nv`) are compiled and injected directly into the assembly output of every compiled program. All platform data uses the Nova stdlib's authoritative implementations (e.g., `sys_platform()` from `os_windows.nv` returns `"windows"`), not hardcoded assembly.

## Key Fixes (Self-Hosting History)

- **Variable-to-register promotion overlap**: Local var offset shifted by `local_var_base = 16 + n_params * 8` to prevent overlap with saved parameters
- **`_printf` `%d` register fix**: `runtime.c` unified `%d` and `%s` handlers to both read from `rsi` (SysV second arg)
- **`_fopen` mode string fix**: Changed from exact match to first-char check, supporting all mode variants (`w`, `wb`, `w+`, `w+b`, etc.)
- **`_fputs` HANDLE dereference fix**: Removed extra dereference that caused `STATUS_ACCESS_VIOLATION`
- **`is_string_expr` `inferred_type` check**: Variable nodes without type annotations are now recognized via `inferred_type`
- **`_sys_platform` assembly removed**: Both backends now use Nova stdlib `sys_platform()` instead of hardcoded assembly
