# KEYWORDS & LOGIC ARCHITECTURE

Nova bridges high-level Pythonic simplicity with low-level C-like control. This document provides a complete, detailed architectural guide to all keywords, types, pointer properties, operators, built-in functions, and compiler internals of the Nova language.

---

## 1. High-Level Language Keywords

### Flow & Structure Control
* **`def`**: Declares a function. Native codegen generates standard x86 `call`/`ret` routines using the `cdecl` calling convention (arguments pushed right-to-left, caller cleans the stack).
  * *Syntax*: `def add(a: int, b: int) -> int { return a + b }`
* **`class`**: Defines an object-oriented class template. Methods are compiled with virtual method table (vtable) entry offsets for dynamic dispatch.
  * *Syntax*:
    ```python
    class Point {
        x: int
        y: int
        def __init__(x_val: int, y_val: int) {
            self.x = x_val
            self.y = y_val
        }
        def move(dx: int, dy: int) {
            self.x = self.x + dx
            self.y = self.y + dy
        }
    }
    ```
* **`self`**: Reference to the current class instance (implicitly passed as the first parameter to methods). Used for `ebp`-relative field or method offset resolution.
* **`import`**: Loads external modules (searches current directory first, then fallback to `stdlib/`). Circular imports are handled safely via a global import visited set.
  * *Syntax*: `import math_utils`
* **`from` / `as`**: Used in imports for aliasing module namespaces or specifying FFI libraries.
  * *Syntax*: `import "kernel32.dll" as kernel32` or `import math_utils as mu`
* **`if` / `elif` / `else`**: Conditional branching. Codegen emits test instructions (`cmp eax, 0`) and conditional jumps (`je`, `jne`, etc.) using generated unique labels.
* **`while`**: Basic loop iteration. Evaluates a condition before executing the loop body.
* **`for`**: Supports two iteration syntaxes:
  1. **Range-based loops**: `for i = start to end step s { ... }` or `for i = start downto end step s { ... }` for descending iteration.
  2. **Collection loops**: `for item in list { ... }` (syntactic sugar over index-based list retrieval).
* **`break` / `continue`**: Controls loop execution. The compiler maintains stacks of active loop labels to resolve jumps to loop heads or loop exits.
* **`return`**: Returns a value from a function. Pops the returned value into `eax`, restores any pushed registers, cleans local stack frames, and executes the x86 `ret` instruction.
* **`const`**: Enforces compile-time variable immutability. Assigning to a variable declared with `const` will cause a static compilation error.
* **`null`**: Evaluates to the memory address `0` (used for pointer checks and object initialization checks).

### Heap Allocation & Raw Memory
* **`data`**: Declares C-style structs with statically typed fields. Offsets are resolved during codegen based on field order (4 bytes per field).
  * *Syntax*:
    ```python
    data Point {
        x: int
        y: int
    }
    ```
* **`alloc(size)`**: Dynamically allocates `size` bytes of raw memory on the heap. Only allowed inside `@raw` blocks. Calls `_malloc` (`HeapAlloc` on Windows) under the hood.
* **`free(ptr)`**: Deallocates memory pointed to by `ptr`. Only allowed inside `@raw` blocks. Calls `_free` (`HeapFree` on Windows) under the hood.

### File I/O Keywords
* **`open(path, mode)`**: Opens the file at `path` using mode `mode` (`"r"` or `"w"`). Returns a 32-bit integer file descriptor.
* **`read(fd)`**: Reads the entire contents of the file referenced by `fd` and returns it as a string.
* **`write(fd, content)`**: Writes a string `content` to the file referenced by `fd`.
* **`close(fd)`**: Closes the file descriptor `fd`.

---

## 2. Built-In Data Types

The static type checker (`type_checker.nv`) resolves, infers, and enforces the following types:
* **`int`**: 32-bit signed integer.
* **`float`**: IEEE-754 32-bit single-precision floating point.
* **`bool`**: Boolean values (`true` and `false`).
* **`string`**: Null-terminated character sequences (e.g. `"hello\n"`).
* **`byte`**: 8-bit unsigned byte.
* **`void`**: Denotes an empty expression or a function returning no value.
* **`list[T]`**: Dynamically-sized array containing elements of type `T` (e.g. `list[int]`).
* **User-defined structs**: Types defined using the `data` keyword.
* **User-defined classes**: Object templates defined using the `class` keyword.

---

## 3. Pointer Suffix Properties (Unsafe `@raw` Mode)

Within `@raw` blocks, pointers (integer addresses representing memory locations) can be read or written to using suffix properties:
* **`ptr.value` / `ptr.value_dword`**: Dereferences the pointer to read or write a 32-bit double-word (4 bytes).
  * *Syntax*: `val = ptr.value` (read) or `ptr.value = 42` (write).
* **`ptr.value_byte`**: Dereferences the pointer to read or write a single 8-bit byte.
  * *Syntax*: `b = ptr.value_byte` (read) or `ptr.value_byte = 10` (write).
* **`ptr.value_word`**: Dereferences the pointer to read or write a 16-bit word (2 bytes).
  * *Syntax*: `w = ptr.value_word` (read) or `ptr.value_word = 1000` (write).
* **`ptr.addr`**: Returns the raw memory address of the variable or property itself.
* **`ptr.isValid`**: Checks if the pointer address is valid (returns `true` if `addr != 0`, `false` if `addr == 0`).
* **`ptr.isNull`**: Checks if the pointer address is null (returns `true` if `addr == 0`, `false` if `addr != 0`).
* **`ptr.bytes`**: Accesses raw byte-level array representations of memory.

---

## 4. Operators

Nova supports a complete range of unary and binary operators, which are type-checked and folded if possible:
* **Arithmetic**: `+` (addition / string concatenation), `-` (subtraction / negation), `*` (multiplication), `/` (signed division), `%` (modulo)
* **Bitwise**: `&` (AND), `|` (OR), `^` (XOR), `~` (NOT), `<<` (logical left shift), `>>` (arithmetic right shift)
* **Logical**: `and` (short-circuiting logical AND), `or` (short-circuiting logical OR), `not` (logical NOT)
* **Comparison**: `==` (equality), `!=` (inequality), `<` (less than), `>` (greater than), `<=` (less than or equal), `>=` (greater than or equal)
* **Structure Check**: `has` (evaluates whether a property field exists on a `data` structure at compile-time)
* **Assignment**: `=` (assigns value to variables, pointer locations, array indices, or struct/class fields)
* **Type Signatures**: `:` (declares types for parameters/variables/fields), `->` (return type annotation on functions)

---

## 5. Built-In Standard Functions

These functions are available natively in all programs without requiring manual imports:

### General & String Utilities
* **`len(var)`**: Returns the count of elements. For `string` values, it computes the length via a built-in `_strlen` loop. For lists, it reads the internal capacity/size fields. For objects, it invokes the custom `__len__` dunder method if defined.
* **`str(var)`**: Converts integers or floats into their string representation using an internal FFI `sprintf` routine.
* **`sizeof(var)`**: Evaluates the compile-time byte size of variables, structures, or data types.

### Lists & Arrays
* **`lst.append(value)`**: Appends `value` to `lst`. If size exceeds current capacity, dynamically doubles the allocated memory buffer (`HeapReAlloc`), preventing linear allocation overhead.
* **`lst.pop()`**: Removes and returns the last element from the list, decreasing the logical length.
* **Array bounds checking**: Array reads (`arr[i]`) and writes (`arr[i] = val`) emit bounds checking instructions:
  ```asm
  cmp ecx, 0
  jl _out_of_bounds       ; negative index
  cmp ecx, [edx]          ; index >= list length
  jge _out_of_bounds      ; exits process with code 1
  ```

### Native OS Interface (`os_win.nv` / `os_linux.nv`)
* **`sys_get_args()`**: Extracts CLI arguments via FFI (using `GetCommandLineA` on Windows), returning them as a parsed string array. Surrounding quotes are automatically stripped.
* **`sys_system(cmd)`**: Executes shell commands via system sub-processes (uses `WinExec` FFI on Windows).
* **`sys_flush()`**: Flushes standard output buffers.
* **`sys_exit(code)`**: Terminates the current process immediately with status `code` (uses `ExitProcess` FFI on Windows).
* **`sys_platform()`**: Returns the host platform identifier (e.g. `"windows"` or `"linux"`).
* **`sys_get_tick_count()`**: Returns the system uptime tick count in milliseconds (uses `GetTickCount` FFI on Windows).

### Cryptographically Secure PRNG
* **`random()`**: Returns a cryptographically secure 32-bit random integer. Uses an optimized, fully-unrolled ChaCha20 block generation algorithm. The CSPRNG is automatically initialized and seeded at startup using `sys_get_tick_count()`.
* **`chacha20_init(seed1, seed2)`**: Manually initializes or seeds the ChaCha20 CSPRNG with specific seeds (useful for reproducible deterministic pseudorandom sequences).

---

## 6. Low-Level Compiler Directives

* **`@raw { ... }`**: Unsafe block mode. Permits inline assembly instructions, pointer dereferencing, heap allocations, and direct FFI calls.
  * *Example*:
    ```python
    @raw {
        mov eax, 42
        push eax
    }
    ```
* **`@export { name1, name2 }`**: Exports defined symbols globally, allowing them to be resolved externally or by other compiled modules.

---

## 7. Compiler Infrastructure

### Self-Hosted Compiler pipeline
The self-hosted compiler files located in `stdlib/` run as a sequential pipeline:
1. **`lexer.nv`**: Tokenizes source characters into a stream of structured `Token` structs.
2. **`parser.nv`**: Constructs a syntax tree (AST) via recursive-descent parsing. Performs constant folding for integer operations.
3. **`types.nv` & `type_checker.nv`**: Infers and validates static types across all AST nodes.
4. **`codegen.nv` (+ `codegen_expr.nv`, `codegen_stmt.nv`)**: Generates Intel-syntax x86-32 assembly lines. Injects list/array bounds checking code and maps local variables to CPU registers (`esi` and `edi`) where possible.
5. **`assembler.nv` (+ submodules)**: Encodes x86-32 assembly lines to native machine code bytes.
6. **`linker.nv`**: Manually packages machine code, imports, and resources into a valid Windows PE binary (GCC-free compilation).

---

## 8. CLI Modes

| Command | Mode | Description |
|---------|------|-------------|
| `python main.py build <file.nv>` | Production | Compiles to native x86 executable using python codegen + GCC |
| `python main.py dev <file.nv>` | Development | Runs in Python bytecode VM |
| `nova_main.exe build <file.nv>` | Self-hosted | Nova-compiled compiler compiles directly to native PE executable using internal assembler + linker (no external toolchain required) |
| `nova_main.exe assemble-link <file.s> <out.exe>` | Assembler/Linker | Assembles and links a raw x86 assembly file directly to a PE executable |
| `nova_main.exe build-bare <file.nv> <org> <entry>` | Flat Binary | Compiles to a flat, headerless binary (ideal for bare-metal/bootloader use) |
