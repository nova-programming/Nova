# Nova Native Codegen Internals (`stdlib/codegen.nv`)

The `codegen.nv` module (plus `codegen_expr.nv` and `codegen_stmt.nv`) traverses the AST and emits Intel-syntax x86-32 assembly for the MinGW/GCC linker.

## State Management

`CodegenState` struct tracks:
- `asm_lines` — list of assembly instruction strings
- `data_lines` — list of `.data` section entries (string literals, format strings)
- `local_vars` / `local_var_names` — maps variable names to `ebp`-relative stack offsets
- `local_offset` — total local stack frame size
- `label_counter` — unique label generator for control flow
- `loop_labels` / `loop_end_labels` — stack of labels for `break`/`continue`
- `struct_names`, `struct_field_names`, `struct_field_offsets` — per-struct field layout tables
- `var_struct_types` — maps variable names to their struct type for field access resolution

## Pass 1: Variable Scanning (`scan_vars`)

Recursively walks the AST of a block to find `Assignment` nodes and register local variables in `local_vars`. Updates `local_offset` for stack frame allocation. Does **not** scan inside `@raw` blocks — variables used exclusively inside `@raw` must be declared outside first.

## Pass 2: Instruction Generation

Uses x86 cdecl stack calling convention. All expressions push results onto the stack.

### Expression Evaluation
- **Integer literal**: `push imm32`
- **Variable**: `mov eax, [ebp - offset]` / `push eax`
- **BinOp**: push left → push right → pop right to `ebx` → pop left to `eax` → compute → push result
- **String literal**: references `.data` section label, pushes address
- **Slice `s[i:j]`**: pushes end, start, base → calls `_slice_string` → `add esp, 12` → pushes result
- **Concat**: calls `_concat_strings` runtime helper
- **Variable indexing**: resolves struct field via `get_prop_offset()` or list index via list struct layout

### Statements
- **Function `def`**: Standard prologue (`push ebp` / `mov ebp, esp` / `sub esp, local_offset`), body compilation, epilogue (`mov esp, ebp` / `pop ebp` / `ret [n]`)
- **Assignment**: Compile RHS → pop to `eax` → `mov [ebp - offset], eax`
- **If/While**: Compile condition → pop → `cmp eax, 0` → conditional jump using `next_label()`
- **Loop label stacks**: `while` pushes/ pops labels for `break` and `continue` resolution
- **`print`**: Selects `fmt_int` or `fmt_str` based on type, pushes args → `call _printf`

## Runtime Helpers

Generated at the end of the `.text` section:
- `_concat_strings(base, append)` — allocates new buffer, copies both strings, null-terminates
- `_slice_string(base, start, end)` — allocates `end-start+1` bytes, byte-copies substring, null-terminates
