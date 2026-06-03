# KEYWORDS & LOGIC ARCHITECTURE

Nova bridges high-level Pythonic simplicity with low-level C-like control. This document lists every keyword, type, operator, built-in function, pointer property, and low-level directive supported by the Nova compiler and bytecode VM.

---

## Language Keywords

### High-Level Flow & Structure
* **`def`**: Declares functions. Generates standard x86 `call`/`ret` routines using the `cdecl` calling convention (arguments pushed right-to-left, caller cleans stack).
* **`class`**: Defines object-oriented blueprints. Supports vtables and dynamic dispatch in native codegen.
* **`self`**: Reference to the current class instance. Used for `ebp`-relative field lookups.
* **`import`**: Loads other `.nv` files. Circular-import-safe (uses a global visited set).
* **`from` / `as`**: Used in imports for namespace management (e.g., `import module as alias` or FFI libraries `import "c" as libc`).
* **`if` / `elif` / `else`**: Conditional branch logic. Emits conditional jump instructions based on comparative evaluations.
* **`while`**: Basic loop iteration. Evaluates condition, jumps to loop body, or jumps to end.
* **`for`**: Supports two iteration syntax forms:
  1. Range-based loops: `for i = start to end step s { ... }` (or `downto` for descending iteration).
  2. Collection iteration: `for item in list { ... }` (syntactic sugar over length-based iteration).
* **`break` / `continue`**: Standard loop control. The codegen tracks a stack of loop labels to resolve jumps.
* **`return`**: Returns a value from a function. Emits code to pop the return value into `eax`, clean the local stack frames, and return.
* **`const`**: Enforces compile-time variable immutability. Assigments to a `const` variable raise compilation errors.
* **`null`**: Represents a null reference or uninitialized pointer value.

### Low-Level Control
* **`data`**: Defines C-style data structures. Fields can have optional type annotations. Offsets are resolved during codegen via field layout calculations.
* **`alloc(size)`**: Dynamically allocates `size` bytes of raw memory on the heap. Only allowed inside `@raw` blocks. Calls `_malloc` (`HeapAlloc`) under the hood.
* **`free(ptr)`**: Frees memory allocated at `ptr`. Only allowed inside `@raw` blocks. Calls `_free` (`HeapFree`) under the hood.

### File I/O Built-ins
* **`open(path, mode)`**: Opens the file at `path` in `mode` (`"r"` or `"w"`). Returns an integer file descriptor.
* **`read(fd)`**: Reads the entire contents of the file referenced by the file descriptor `fd` and returns it as a string.
* **`write(fd, content)`**: Writes a string `content` to the file referenced by `fd`.
* **`close(fd)`**: Closes the file descriptor `fd`.

---

## Data Types

The type checker (`type_checker.nv`) resolves and validates the following types:
* **`int`**: 32-bit signed integer.
* **`float`**: IEEE-754 32-bit single-precision floating point.
* **`bool`**: Boolean values (`true` and `false`).
* **`string`**: Null-terminated character sequences.
* **`byte`**: 8-bit unsigned byte.
* **`void`**: Denotes no return value or empty expression.
* **`list[T]`**: Dynamically-sized array of elements of type `T` (e.g., `list[int]`).
* **User-defined structures**: Created using the `data` keyword.

---

## Pointer Properties & Accessors

Within `@raw` blocks, pointers (variables containing memory addresses) can access special suffix properties:
* **`.value`**: Resolves/assigns the 32-bit integer value pointed to by the memory address.
* **`.value_byte`**: Resolves/assigns a single 8-bit byte at the memory address.
* **`.value_word`**: Resolves/assigns a 16-bit word at the memory address.
* **`.value_dword`**: Resolves/assigns a 32-bit double word at the memory address.
* **`.value_qword`**: Resolves/assigns a 64-bit quad word at the memory address.
* **`.addr`**: Obtains the raw memory address of the variable or field itself.
* **`.bytes`**: Accesses raw byte array representation of the memory.
* **`.isValid`**: Checks if the pointer address is non-zero.
* **`.isNull`**: Checks if the pointer address is zero (`null`).

---

## Operators

Nova supports a complete range of unary and binary operators:
* **Arithmetic**: `+` (addition), `-` (subtraction), `*` (multiplication), `/` (division), `%` (modulo)
* **Bitwise**: `&` (AND), `|` (OR), `^` (XOR), `~` (NOT), `<<` (left shift), `>>` (right shift)
* **Logical**: `and` (short-circuiting logical AND), `or` (short-circuiting logical OR), `not` (logical inversion)
* **Comparison**: `==` (equality), `!=` (inequality), `<` (less than), `>` (greater than), `<=` (less than or equal), `>=` (greater than or equal)
* **Metadata/Field Checks**: `has` (evaluates whether a property field exists on a `data` structure at compile time)
* **Assignment**: `=` (stores values in variables, pointer locations, array indices, or struct fields)
* **Annotation**: `:` (declares types for variables, parameters, and fields), `->` (return type annotation on functions)

---

## Built-In Functions

These functions are available natively in all programs without requiring manual imports:

### General & String Utilities
* **`len(var)`**: Returns the count of elements. For `string` values, it computes the length via a built-in `_strlen` loop. For lists, it reads the internal capacity/size fields.
* **`str(var)`**: Converts integers or floats into their string representation using an internal FFI `sprintf` routine.
* **`sizeof(var)`**: Evaluates the compile-time byte size of variables, structures, or data types.

### Native OS Interface (`os_win.nv` / `os_linux.nv`)
* **`sys_get_args()`**: Extracts CLI arguments via FFI (using `GetCommandLineA` on Windows), returning them as a parsed string array. Surrounding quotes are automatically stripped.
* **`sys_system(cmd)`**: Executes shell commands via system sub-processes (uses `WinExec` FFI on Windows).
* **`sys_flush()`**: Flushes standard output buffers.
* **`sys_exit(code)`**: Terminates the current process immediately with status `code` (uses `ExitProcess` FFI on Windows).
* **`sys_platform()`**: Returns the host platform identifier (e.g. `"windows"`).
* **`sys_get_tick_count()`**: Returns the system uptime tick count in milliseconds (uses `GetTickCount` FFI on Windows).

### Cryptographically Secure PRNG
* **`random()`**: Returns a cryptographically secure 32-bit random integer. Uses an optimized, fully-unrolled ChaCha20 block generation algorithm. The CSPRNG is automatically initialized and seeded at startup using `sys_get_tick_count()`.
* **`chacha20_init(seed1, seed2)`**: Manually initializes or seeds the ChaCha20 CSPRNG with specific seeds (useful for reproducible deterministic pseudorandom sequences).

---

## Low-Level Compiler Directives

* **`@raw { ... }`**: Unsafe block mode. Permits inline assembly instructions, pointer dereferencing, heap allocations, and direct FFI calls.
* **`@export { name1, name2 }`**: Exports defined symbols globally, allowing them to be resolved externally or by other compiled modules.

---

## Compiler Infrastructure

### Self-Hosted Compiler pipeline
The self-hosted compiler files located in `stdlib/` run as a sequential pipeline:
1. **`lexer.nv`**: Tokenizes source characters into a stream of structured `Token` structs.
2. **`parser.nv`**: Constructs a syntax tree (AST) via recursive-descent parsing. Performs constant folding for integer operations.
3. **`types.nv` & `type_checker.nv`**: Infers and validates static types across all AST nodes.
4. **`codegen.nv` (+ `codegen_expr.nv`, `codegen_stmt.nv`)**: Generates Intel-syntax x86-32 assembly lines. Injects list/array bounds checking code and maps local variables to CPU registers (`esi` and `edi`) where possible.
5. **`assembler.nv` (+ submodules)**: Encodes x86-32 assembly lines to native machine code bytes.
6. **`linker.nv`**: Manually packages machine code, imports, and resources into a valid Windows PE binary (GCC-free compilation).

---

## CLI Modes

| Command | Mode | Description |
|---------|------|-------------|
| `python main.py build <file.nv>` | Production | Compiles to native x86 executable using python codegen + GCC |
| `python main.py dev <file.nv>` | Development | Runs in Python bytecode VM |
| `nova_main.exe build <file.nv>` | Self-hosted | Nova-compiled compiler compiles directly to native PE executable using internal assembler + linker (no external toolchain required) |
| `nova_main.exe assemble-link <file.s> <out.exe>` | Assembler/Linker | Assembles and links a raw x86 assembly file directly to a PE executable |
| `nova_main.exe build-bare <file.nv> <org> <entry>` | Flat Binary | Compiles to a flat, headerless binary (ideal for bare-metal/bootloader use) |
