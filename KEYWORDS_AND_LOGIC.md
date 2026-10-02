# KEYWORDS & LOGIC ARCHITECTURE

Nova bridges high-level Pythonic simplicity with low-level C-like control. This document provides a complete, detailed architectural guide to all keywords, types, pointer properties, operators, built-in functions, and compiler internals of the Nova language.

---

## 1. High-Level Language Keywords

### Flow & Structure Control
* **`def`**: Declares a function. Native codegen generates standard `call`/`ret` routines using the target architecture's calling convention (SysV AMD64 for x86_64, standard AArch64 for ARM64).
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
* **`return`**: Returns a value from a function. Pops the returned value into `eax`/`rax`, restores any pushed registers, cleans local stack frames, and executes the architecture's `ret` instruction.
* **`const`**: Enforces compile-time variable immutability. Assigning to a variable declared with `const` will cause a static compilation error.
* **`null`**: Evaluates to the memory address `0` (used for pointer checks and object initialization checks).
* **`switch`/`case`/`else`**: Multi-branch selection. `switch expr { case val { body } else { body } }` desugars to an if-elif-else chain at parse time (no AST or codegen changes needed).
* **`try`/`catch`/`throw`**: Exception handling. `try { ... } catch e { ... }` compiles to setjmp/longjmp in native mode. `throw val` triggers the exception. Both VM (OP_TRY/OP_THROW/OP_CATCHEND) and native runtimes supported.
* **`defer`**: Deterministic scope cleanup. Executes statements in LIFO (reverse) order right before function or scope exit (`return`, `break`, or block closing `}`). Supports both single-line (`defer sys_close(f)`) and block form (`defer { free(p); sys_close(f) }`).
* **`extern def`**: Direct zero-boilerplate C FFI. Declares external C functions (`extern def puts(s: string) -> int`) with automatic argument register placement (SysV / Win64) and null-terminated string pointer unwrapping.

### Counting loops, constructors and dictionaries
* `for i in range(n)`, `range(a, b)`, `range(a, b, step)`: the end is excluded like Python and the step must be an integer literal (negative counts down). Lowers to the counted `for i = a to b step s` loop.
* `Point(1, 2)` / `Point(x=1, y=2)`: build a `data` value in field order (missing fields are zero). The compiler generates a hidden `__new_Point` function only for types built this way. Applies to types declared earlier in the same file.
* `d["k"]`, `d["k"] = v`, `"k" in d`, `"k" not in d` on dictionaries.
* Functions without a `-> type` that only return strings are treated as returning `string`.

### Standard modules (dotted calls)
`import fs` then `fs.read(p)` calls the flat function `fs_read(p)` (a parse-time rewrite: no runtime cost).
Public modules: `fs`, `path`, `env`, `process`, `time`, `json` (`stringify`, `parse`, `kind`, `asInt`, `asString`, `asBool`, `size`, `at`, `get`, `has`, `keyAt`), `text`. Unknown members are errors with a
did-you-mean hint. Module-qualified names are the preferred API; flat names remain accepted.

### Soft keywords
`read`, `write`, `close`, `api`, `openf` are keywords only when called (`read(fd)`), and `data` only in
`data Name { ... }`; elsewhere they are ordinary identifiers (variables, fields, your own functions).

### Heap Allocation & Raw Memory
* **`data`**: Declares C-style structs with statically typed fields. Offsets are resolved during codegen based on field order (4 bytes per field).
  * *Syntax*:
    ```python
    data Point {
        x: int
        y: int
    }
    ```
* **`alloc(size)` / `alloc[T](count)`**: Dynamically allocates memory on the heap. `alloc[T](count)` automatically scales the allocation by `sizeof(T)` at compile time.
* **`free(ptr)`**: Deallocates memory pointed to by `ptr`. Calls `_free` (`HeapFree` on Windows) under the hood.

### Unsafe memory ownership rules

`alloc` returns memory owned by the caller. The owner must call `free` exactly
once after the last access. Nova does not currently provide ownership
inference, borrowing, or automatic lifetime extension for raw pointers.
Pointers returned by `.ptr` are borrowed views into their source object and
must not be freed directly. `.as_list(count)` is also a borrowed view: the
caller must keep the source allocation alive and must not use the view after
that allocation is freed or resized. `@raw`, FFI, and pointer dereference
operations are explicitly unsafe and remain the user's responsibility.

The compiler does not infer these lifetimes yet. `nova lint` reports
`UNSAFE001` for `alloc` and `free` as an advisory review point; it does not
reject or rewrite code. Use an explicit project policy before shipping native
code that uses raw memory.

### File I/O Keywords
* **`open(path, mode)`**: Opens the file at `path` using mode `mode` (`"r"` or `"w"`). Returns a 32-bit integer file descriptor.
* **`read(fd)`**: Reads the entire contents of the file referenced by `fd` and returns it as a string.
* **`write(fd, content)`**: Writes a string `content` to the file referenced by `fd`.
* **`close(fd)`**: Closes the file descriptor `fd`.

### Standard Output & Debugging
* **`print`**: Outputs the value of an expression to standard output. Resolves the value's type at compile time and invokes the appropriate printing routine (e.g. `_printf` with `%d` for integers, `%f` for floats, or `L_write_stdout` for strings).
  * *Syntax*: `print(x)`
* **`printd`**: Debug print. Outputs a debug prefix containing the source file line number, followed by the evaluated value (e.g., `debug - [line 42]: <value>`). The compiler only generates assembly instructions for `printd` statements when compiling with the `--debug` flag active; otherwise, they are discarded as no-ops.
  * *Syntax*: `printd(x)`

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
* **`dict`**: HashMap/dictionary type. `{"key": val}` literal syntax. Methods: `get(key)`, `set(key, val)`, `has(key)`, `remove(key)`, `keys()`, `values()`, `items()`. Native codegen via `_dict_*` runtime calls.
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
* **`lst.ptr`**: Returns the raw memory address of the list's internal backing buffer.
* **`ptr.as_list(count)`**: Wraps a raw memory pointer into a high-level `list` header with `count` elements with zero copying.

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
* **List comprehensions**: `[expr for x in list if cond]` syntax desugars at parse time to a Block + ForIn loop + `append()` call. 7 tests.
* **Array bounds checking**: Array reads (`arr[i]`) and writes (`arr[i] = val`) emit bounds checking instructions:
  ```asm
  cmp ecx, 0
  jl _out_of_bounds       ; negative index
  cmp ecx, [edx]          ; index >= list length
  jge _out_of_bounds      ; exits process with code 1
  ```

### Native OS Interface (`os_win.nv` / `os_linux.nv`)
* **`sys_get_args()`**: Extracts CLI arguments via FFI (using `GetCommandLineA` on Windows), returning them as a parsed string array. Surrounding quotes are automatically stripped.
* **`sys_system(cmd)`**: Executes shell commands via system sub-processes (uses C library `system()`).
* **`sys_flush()`**: Flushes standard output buffers.
* **`sys_exit(code)`**: Terminates the current process immediately with status `code` (uses `ExitProcess` FFI on Windows).
* **`sys_platform()`**: Returns the host platform identifier (e.g. `"windows"` or `"linux"`).
* **`sys_get_tick_count()`**: Returns the system uptime tick count in milliseconds (uses `GetTickCount` FFI on Windows).

### Dict/HashMap Methods
* **`dict.get(key)`**: Returns the value associated with `key`, or `null` if not found.
* **`dict.set(key, val)`**: Associates `key` with `val` in the dictionary.
* **`dict.has(key)`**: Returns `true` if `key` exists in the dictionary, `false` otherwise.
* **`dict.remove(key)`**: Removes `key` and its associated value from the dictionary.
* **`dict.keys()`**: Returns a list of all keys in the dictionary.
* **`dict.values()`**: Returns a list of all values in the dictionary.
* **`dict.items()`**: Returns a list of alternating key-value pairs.

### type() and call() Built-ins
* **`type(val)`**: Returns the type name of `val` as a string. Returns `"int"`, `"string"`, `"float"`, `"bool"`, `"list"`, `"dict"`, or `"unknown"`. In native codegen, resolved to a compile-time string constant.
* **`call(name, args)`**: Dynamically dispatches to a function by name string in VM mode. Native builds reject this operation because native dynamic dispatch is not implemented; use a statically named function call for portable code.

### PRNG
* **`random()`**: Returns a 32-bit pseudorandom integer. Uses a fast xorshift64 algorithm (not CSPRNG). Automatically seeded at startup via `sys_get_tick_count()`. `random(lo, hi)` returns a value in `[lo, hi]`.
* **`chacha20_init(seed1, seed2)`**: Seeds the PRNG with `((seed1 << 32) | seed2)` for reproducible deterministic sequences. Name retained for compatibility; currently seeds the same xorshift64 state.

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
* **`@entry`**: Marks a bare-metal function as the executable entry point when building with `--bare` (bypasses runtime CRT initialization).
* **`@noinline`**: Disables automatic function inlining for a specific function.

---

## 7. Compiler Infrastructure

### Self-Hosted Compiler pipeline
The self-hosted compiler files located in `stdlib/` run as a sequential pipeline:
1. **`lexer.nv`**: Tokenizes source characters into a stream of structured `Token` structs. Uses `switch` internally to match 47 keywords and all operators.
2. **`parser.nv`**: Constructs a syntax tree (AST) via recursive-descent parsing. Performs constant folding for integer operations. Desugars switch/match, list comprehensions, and dict literals.
3. **`types.nv` & `type_checker.nv`**: Infers and validates static types across all AST nodes.
4. **`codegen.nv` (+ `codegen_expr.nv`, `codegen_stmt.nv`)**: Generates assembly for the target architecture (x86_64 via `stdlib/backend/x86_64/`, ARM64 via `stdlib/backend/arm64/`). Injects list/array bounds checking code and maps local variables to CPU registers where possible. Emits try/catch/throw via setjmp/longjmp wrappers.
5. **`assembler.nv` (+ submodules)**: Encodes x86 assembly lines to native machine code bytes.
6. **`linker.nv`**: Manually packages supported Windows machine code, imports, and resources into a PE binary; Unix final linking currently uses GCC.
7. **`vm.nv`**: Nova bytecode VM written in Nova. Supports 20+ opcodes and stack-based execution for `nova dev` and `nova repl` modes.

---

## 8. Additional Compiler Optimizations

### Frame Pointer Optimization
Both x86_64 and ARM64 backends have been optimized to eliminate the frame pointer:
- **x86_64**: `state.bp = "rsp"` — no `push rbp; mov rbp, rsp` emitted in function prologue. Local variable offsets are positive from `rsp` with +8 compensation.
- **ARM64**: `state.bp = "sp"` — no `mov fp, sp` emitted. Offsets converted via `new = stack_size - old` formula.
- Saves 1-2 instructions per function call, frees `rbp`/`fp` as a general-purpose register.

### Cross-Compilation
The compiler supports building for different target platforms via the `target_os` field in `CodegenState`:
- Platform-aware GCC command generation (`gcc` on Linux/macOS, bundled `gcc/bin/gcc.exe` on Windows)
- OS-appropriate output extensions (`.exe` on Windows, no extension on macOS/Linux)
- Platform-specific stub selection (`os_win.nv`, `os_linux.nv`, `os_macos.nv`)
- `--target` flag for cross-compilation invocations

### 8. CLI Modes

### Nova Compiler

| Command | Mode | Description |
|---------|------|-------------|
| `python main.py build <file.nv>` | Production | Compiles to native x86 executable using python codegen + GCC |
| `python main.py dev <file.nv>` | Development | Runs in Python bytecode VM |
| `nova.exe build <file.nv>` | Self-hosted | Nova-compiled compiler compiles directly to native PE executable using internal assembler + linker (no external toolchain required) |
| `nova.exe run <file.nv> [args...]` | Self-hosted | Compiles and immediately executes native binary with argument forwarding |
| `nova.exe assemble-link <file.s> <out.exe>` | Assembler/Linker | Assembles and links a raw x86 assembly file directly to a PE executable |
| `nova.exe build-bare <file.nv> <org> <entry>` | Flat Binary | Compiles to a flat, headerless binary (ideal for bare-metal/bootloader use) |
| `nova.exe dev <file.nv>` | Development | Runs in the Nova-written bytecode VM (stdlib/vm.nv) |
| `nova.exe repl` | Interactive | Starts the interactive REPL with multi-line input and persistent state |

---

## 9. Native GUI & NSS Styling Engine (`gui`)

Nova includes a native, lightweight GUI and NSS (Nova Style Sheets) layout engine designed with zero third-party web bloat (no Chromium, Electron, or WebView2). It leverages native Win32 double-buffered GDI rendering at a smooth 60 FPS.

### Inline NSS Properties Syntax
Styling is passed directly via the `properties={...}` dictionary parameter on UI components and windows:

```nova
import gui

# Create Window with background styling
app = window("Nova Studio", 520, 500, properties={
    "background-color": "#181825"
})

# Button with hover effect, rounded corners, and padding
btn = Button("Click Me (+1)", 1, properties={
    "background-color": "#89b4fa",
    "color": "#11111b",
    "font-size": 16,
    "border-radius": 10,
    "padding-left": 28,
    "padding-right": 28,
    "padding-top": 12,
    "padding-bottom": 12
})

# Flexbox container with alignment and spacing
card = Container([
    Text("Interactive Counter", properties={"color": "#bac2de", "font-size": 18, "font-weight": "bold"}),
    btn
], properties={
    "background-color": "#1e1e2e",
    "border-radius": 12,
    "border-width": 1,
    "border-color": "#313244",
    "padding": 24,
    "align-items": "center",
    "gap": 16,
    "width": 460
})
app.root = card
```

### Supported NSS Styling Properties
| Property | Value Format | Description |
|---|---|---|
| `background-color` | `"#RRGGBB"` | Background fill color (hex format) |
| `color` | `"#RRGGBB"` | Text / foreground font color |
| `font-size` | `int` | Font size in points (e.g. 14, 16, 24) |
| `font-weight` | `"normal"` / `"bold"` | Text font weight |
| `border-radius` | `int` | Corner curvature radius in pixels |
| `border-width` | `int` | Border thickness in pixels |
| `border-color` | `"#RRGGBB"` | Border color |
| `padding` | `int` | Uniform padding on all 4 edges |
| `padding-left`, `-right`, `-top`, `-bottom` | `int` | Per-side padding in pixels |
| `gap` | `int` | Spacing between flex children |
| `flex-direction` | `"column"` / `"row"` | Flex layout direction |
| `align-items` | `"center"` | Cross-axis alignment |
| `width`, `height` | `int` | Fixed dimensions in pixels |

---

### Galaxy Package Manager

After installing with `python install.py`, the `nova` and `galaxy` commands are available globally:

| Command | Description |
|---------|-------------|
| `nova --version` | Show Nova compiler version |
| `nova build <file.nv>` | Compile a Nova program (alias for `python main.py build`) |
| `nova run <file.nv> [args...]` | Compile and run native binary immediately |
| `nova dev <file.nv>` | Run in the Nova bytecode VM |
| `nova repl` | Start the interactive REPL |
| `nova update` | Update Nova compiler itself |
| `galaxy --version` | Show Galaxy CLI version |
| `galaxy init library <name>` | Scaffold a new library project |
| `galaxy install <pkg>` | Install a package from the registry or GitHub |
| `galaxy search <query>` | Search the registry by name, keyword, or author |
| `galaxy info <pkg>` | Show detailed package information |
| `galaxy publish` | Submit your package to the registry (opens GitHub Issue) |
| `galaxy update` | Update Galaxy CLI itself |
| `galaxy upgrade [pkg]` | Update installed packages |
| `galaxy remove <pkg>` | Uninstall a package |
| `galaxy list` | List locally installed packages |

### Quick Install

**macOS / Linux (bash):**
```bash
curl -O https://galaxy-registry.vercel.app/install.sh && bash install.sh
```
**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri https://galaxy-registry.vercel.app/install.ps1 -OutFile install.ps1; powershell -File install.ps1
```
**Python fallback (any platform):**
```bash
curl -O https://galaxy-registry.vercel.app/install.py && python install.py
```
