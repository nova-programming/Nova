# KEYWORDS & LOGIC ARCHITECTURE

Nova aims to simplify programming by blending high-level ease with low-level power.

---

## High-Level Keywords

### `def`
Defines functions/methods. In native codegen, emits x86 `call`/`ret` with cdecl stack convention.

### `class`
Defines an OOP blueprint with dunder methods. Native codegen supports vtables and dynamic dispatch.

**Supported dunder methods (native codegen):**
| Method | Trigger |
|--------|---------|
| `__init__(...)` | `ClassName(args)` — auto-constructor |
| `__str__()` | `print(obj)`, `str(obj)` |
| `__len__()` | `len(obj)` |
| `__eq__(other)` | `obj == other` |
| `__add__(other)` | `obj + other` |
| `__sub__(other)` | `obj - other` |
| `__mul__(other)` | `obj * other` |

### `self`
Refers to the current class instance. In native codegen, `ebp`-relative access resolves struct fields.

### `import`
Loads Nova modules: searches relative path, then `stdlib/`. Circular-import-safe via visited set.

### `if`, `elif`, `else`, `while`, `for`
Control flow. Native codegen emits conditional jumps with unique labels from a label counter.

### `for` (extended)
Range-based: `for i = start to end step s { }` with `downto` for descending iteration.

### `break`, `continue`
Loop control. Codegen tracks loop label stacks for correct jump targets.

### `and`, `or`, `not`
Short-circuit logical operators.

### `&`, `<<`, `>>`
Bitwise AND, left shift, right shift on integers.

### `has`
Runtime field-existence check for `data` structs. Evaluated at compile time in native codegen.

### `print`
Outputs to console. Native: pushes format string and calls `_printf` via FFI.

### `return`
Returns value from function. Native: `mov [result], eax; jmp epilogue`.

### Variable Mutability
Mutable by default; `const` for immutability (enforced at compile time).

---

## Low-Level Keywords

### `@raw`
Enters unsafe low-level mode enabling `alloc`/`free` and pointer `.value_byte` access. Enforced at compile time.

### `alloc(size)` / `free(ptr)`
Raw memory allocation/deallocation. Only inside `@raw`. Native: calls `_malloc`/`_free` via FFI.

### Type annotations (`: int`, `: string`, `: list[int]`, etc.)
Variables, function parameters, and return types support annotation syntax. The type checker resolves `int`, `float`, `bool`, `string`, `byte`, `void`, `list[T]`, and user-defined struct types.

### `data`
Defines raw C-style structs with typed fields. Native codegen resolves field offsets via `get_prop_offset()`. Fields can use `: type` annotations. Struct types are registered for type inference.

### `.value_byte`
Byte-level pointer dereference for raw memory access inside `@raw` blocks.

---

## Built-In Functions

### `len(var)`
Returns logical element count. For strings: `_strlen`. For lists: struct `length` field. For objects: `__len__` dunder. Type checker returns `int`.

### Array bounds checking
All list element reads (`arr[i]`) and writes (`arr[i] = x`) include runtime bounds checks: `cmp ecx, 0; jl _out_of_bounds; cmp ecx, [length]; jge _out_of_bounds`. Bounds violation calls `ExitProcess(1)` with "Index Out Of Bounds" message.

### Constant folding (`parser.nv`/`parser.py`)
During parsing, `+`, `-`, `*`, `/`, `%`, `&`, `<<`, `>>` on two literal `Number` nodes are evaluated immediately. `1 + 2 * 3` collapses to `7` at compile time — zero runtime instructions emitted.

### List type unification
`[1, 2, 3]` infers as `list[int]`. `[1, "hello"]` raises `StaticTypeError` at compile time. Array index assignments are checked against the element type.

### `str(var)`
Converts value to string. Native: emits format-string selection and `sprintf` call.

### `sizeof(var)`
Returns memory size in bytes.

### `sys_get_args()`, `sys_system(cmd)`, `sys_flush()`, `sys_exit(code)`
Native OS interface functions provided by `os_win.nv`/`os_linux.nv`.

---

## Self-Hosted Compiler Components

### `stdlib/lexer.nv`
Character-by-character tokenizer. Produces `Token` structs with `kind` and `val` fields. Handles escape sequences, multi-char operators, comments, and all Nova keywords.

### `stdlib/parser.nv`
Recursive-descent parser consuming Token list → `AstNode` AST. Expression hierarchy: `primary → unary → mul → add → compare → logic → expr`. Statement parsing for assignments, if/elif/else, while, for, break, continue, return, functions.

### `stdlib/codegen.nv` (+ `codegen_expr.nv`, `codegen_stmt.nv`)
x86-32 assembly code generator. Walks AST and emits Intel-syntax assembly using `CodegenState` struct tracking:
- Assembly lines and data section entries
- Label counter for unique jump labels
- Local variable offsets (`ebp`-relative)
- Struct field offset tables (`struct_names`, `struct_field_names`, `struct_field_offsets`)
- Variable-to-struct-type mappings for `DataFieldAccess`/`DataFieldAssign`
- Runtime helpers: `_concat_strings`, `_slice_string`
- Format string selection for `print`

The generated `.s` assembly is written to disk and linked via a `sys_system("gcc ...")` call.

### `stdlib/compiler.nv`
Pipeline orchestrator: `compile_file(path)` → read file → tokenize → parse → resolve imports → generate assembly. `compile_to_file(input, output)` writes assembly to `.s`.

### `stdlib/assembler.nv` (+ `assembler_parse.nv`, `assembler_encode.nv`, `assembler_pass.nv`)
x86-32 instruction encoder written in Nova. Parses assembly lines → encodes with ModRM/SIB → two-pass assembly with fixup resolution. **Not yet integrated into default compilation path.**

### `stdlib/linker.nv`
Native PE (Portable Executable) generator written in Nova. Constructs DOS/PE headers, section tables, import address tables. **Not yet integrated into default compilation path.**

### `stdlib/os_win.nv`
Windows HAL providing `sys_get_args()` (via `GetCommandLineA` FFI), file I/O (`sys_open`, `sys_read`, `sys_write`), `sys_system`, `sys_exit`, `sys_flush`, `sys_platform()`.

### `stdlib/memory.nv`
Raw byte-level memory access utilities using inline assembly in `@raw` blocks.

### `stdlib/os_linux.nv`
Linux runtime facade (parallel to `os_win.nv`, targeting POSIX FFI).

## CLI Modes

| Command | Mode | Description |
|---------|------|-------------|
| `python main.py build <file.nv>` | Production | Compiles to native x86 executable via GCC |
| `python main.py dev <file.nv>` | Development | Runs in Python bytecode VM |
| `nova_main.exe build <file.nv>` | Self-hosted | Nova-compiled compiler produces .s → GCC → .exe |
