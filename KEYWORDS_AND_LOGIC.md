# KEYWORDS & LOGIC ARCHITECTURE

Nova aims to simplify programming by blending high-level ease with low-level power. Here is the concise breakdown of the keywords and their backend mechanics.

---

## High-Level Keywords

### `def`
**Use:** Defines functions/methods.
**Logic:** The compiler maps this to a `Function` or `ClassDef` method node. At runtime, the VM sets up a new local `Frame` and jumps the Instruction Pointer (IP) to the function's bytecode block.

### `class`
**Use:** Defines an OOP blueprint with special "dunder" methods.
**Logic:** Creates a metadata definition in the compiler. At runtime, calling `ClassName(args)` instantiates a VM `Instance` dictionary and auto-calls `__init__` if defined.

**Supported dunder methods:**
| Method | Trigger | Description |
|--------|---------|-------------|
| `__init__(...)` | `ClassName(args)` | Auto-constructor — called on instantiation |
| `__str__()` | `print(obj)`, `str(obj)` | String representation |
| `__len__()` | `len(obj)` | Length/size |
| `__eq__(other)` | `obj == other` | Equality comparison |
| `__add__(other)` | `obj + other` | Addition operator |
| `__sub__(other)` | `obj - other` | Subtraction operator |
| `__mul__(other)` | `obj * other` | Multiplication operator |

**Example:**
```nova
class Vector {
    x: int
    y: int

    def __init__(vx: int, vy: int) {
        self.x = vx
        self.y = vy
    }

    def __str__() -> string {
        return "Vector(" + str(self.x) + ", " + str(self.y) + ")"
    }

    def __add__(other) {
        return Vector(self.x + other.x, self.y + other.y)
    }
}

v = Vector(3, 4)     # auto-calls __init__
print(v)             # auto-calls __str__ → "Vector(3, 4)"
v2 = v + Vector(1,2) # auto-calls __add__ → Vector(4, 6)
```

### `self`
**Use:** Refers to the current class instance.
**Logic:** When a method is called, the VM's frame captures the parent object. `LOAD_SELF` pushes this captured context instance to the stack so properties can be evaluated.

### `import`
**Use:** Loads external Nova modules or C libraries.
**Logic:**
1. `import module_name`: The `ModuleResolver` searches for `module_name.nv` in three locations (relative to importing file, project root, `stdlib/` directory). The file is tokenized, parsed, and its functions/classes/data are compiled into the current program's bytecode. A circular import cache prevents infinite loops.
2. `import module_name as alias`: Same as above but registers under an alias namespace.
3. `import "lib" as alias`: Triggers FFI. Uses Python's `ctypes` in the VM to dynamically link the `.so`/`.dll` object into the runtime environment.

### `from` *(reserved)*
**Use:** Selective imports (planned).
**Logic:** Token is reserved for future `from module import func1, func2` syntax. Not yet implemented.

### `if`, `elif`, `else`, `while`, `for`
**Use:** Control flow.
**Logic:** Compiles to `JUMP` and `JUMP_IF_FALSE` opcodes. The compiler tracks offsets to efficiently skip blocks of bytecode based on stack comparisons. `elif` is a single keyword — there is no `else if` syntax.

**Example:**
```nova
x = 2
if x == 1 {
    print("one")
} elif x == 2 {
    print("two")
} else {
    print("other")
}
```

### `for` (extended)
**Use:** Range-based iteration with `to`, `downto`, and optional `step`.
**Logic:** `for i = start to end step s { ... }` compiles to: initialize counter → loop condition (CMP_LE or CMP_GE) → body → increment/decrement → jump back. `downto` reverses the comparison and uses subtraction.

### `break`, `continue`
**Use:** Loop control.
**Logic:** `break` emits a `JUMP` to the end of the loop (patched after loop compilation). `continue` emits a `JUMP` back to the loop's condition check.

### `and`, `or`, `not`
**Use:** Logical operators.
**Logic:** Compile to `AND`, `OR`, and `NOT` opcodes. `AND` pops two values and pushes their logical conjunction. `OR` pushes the disjunction. `NOT` inverts the top of stack.

### `&`, `<<`, `>>`
**Use:** Bitwise operators.
**Logic:** `a & b` computes bitwise AND. `a << b` shifts `a` left by `b` bits. `a >> b` shifts `a` right by `b` bits. All operate on integer values and push the integer result.

**Example:**
```nova
a = 0b1010 & 0b1100     # 8 (bitwise AND)
b = 1 << 8              # 256 (left shift)
c = 256 >> 4            # 16  (right shift)
```

### `has`
**Use:** Checks if a `data` struct has a specific field by name.
**Logic:** At compile time, the type checker resolves the struct definition and verifies the field name exists. If the field is found, the expression evaluates to `true`; otherwise `false`. Only works with `data` structs.

**Example:**
```nova
data Person {
    name: string
    age: int
}
p = Person("Alice", 30)
if p has "age" {
    print("has age field")   # prints
}
if p has "xyz" {
    print("has xyz")         # does not print
}
```

### `print`
**Use:** Outputs to console.
**Logic:** Pops the top value of the stack and writes to standard output. If the value is an `Instance` with a `__str__` method, it auto-calls the method and prints the result.

### `return`
**Use:** Returns a value from a function.
**Logic:** Pushes the return value onto the stack and emits a `RETURN` opcode, which pops the current frame and restores the instruction pointer to the caller.

### Variable Mutability

**Use:** Variables are **mutable by default**. Use `const` for immutability.

**Logic:** In the type checker, regular variables can be reassigned freely. `const` variables are tracked in a `const_vars` set — any subsequent assignment to a `const` variable raises a `StaticTypeError`.

**Example:**
```nova
const MAX = 100
x = 42       # mutable (default) — can be reassigned
x = 43       # OK
# MAX = 101  # ERROR: Cannot reassign const variable 'MAX'
```

---

## Low-Level Keywords (`@raw` block)

### `@raw`
**Use:** Enters the unsafe, high-performance low-level mode.
**Logic:** Enables manual memory operations (`alloc`/`free`) and pointer access. The type checker **enforces** this boundary — using `alloc`, `free`, or pointer operations outside a `@raw` block raises a `StaticTypeError` at compile time.

### `@export`
**Use:** Bridges `@raw` elements out to high-level code.
**Logic:** While currently passively handled in the VM, in compiled static versions, it exposes C-linkage pointers/structs to the safe GC/ARC memory space.

### `alloc(size)`
**Use:** Allocates raw bytes. **Only inside `@raw`.**
**Logic:** Evaluates an `ALLOC` opcode. The VM now backs the heap with a native `ctypes` buffer, returning an integer pointer address and tracking the allocation size against that native heap region.

### `free(ptr)`
**Use:** Deallocates raw bytes. **Only inside `@raw`.**
**Logic:** Erases the pointer from the active allocations tracker in the VM. The current runtime models deallocation over the native heap buffer rather than delegating to a host language object model.

### `data`
**Use:** Defines raw C-style structs.
**Logic:** Defines a contiguous block definition. Calling `DataName()` evaluates a `NEW` struct instance on the stack. High-level ARC does *not* recursively manage struct internals natively, requiring careful memory design.

---

## Built-In Functions

### `sizeof(var)`
**Use:** Gets the memory size in bytes.
**Logic:** Evaluates a `SIZEOF` opcode. The VM checks if the variable is a tracked heap pointer (returning allocated bytes), an integer (returns 4), a string (returns length), or an object (returns property count × 4).

### `len(var)`
**Use:** Gets the logical element count.
**Logic:** Evaluates a `LEN` opcode. For lists/strings, returns the Python-backed length. For class instances, auto-calls `__len__()` if defined.

### `str(var)`
**Use:** Converts any value to a string.
**Logic:** Evaluates a `STR_CONVERT` opcode. For class instances, auto-calls `__str__()` if defined. For primitives, converts to their string representation (ints → digits, bools → "true"/"false").

**Example:**
```nova
x = 42
print("x = " + str(x))     # "x = 42"
print("flag: " + str(true)) # "flag: true"
```

### `open(path, mode)`, `read(fd)`, `write(fd, content)`, `close(fd)`
**Use:** Standard File I/O operations.
**Logic:** Evaluates to `OPEN_FILE`, `READ_FILE`, `WRITE_FILE`, and `CLOSE_FILE` opcodes. The VM maintains a map of open file descriptors (integer handles) to native OS handles rather than Python file objects.

---

## String Operations

### String Slicing: `s[i:j]`
**Use:** Extract a substring from index `i` (inclusive) to `j` (exclusive).
**Logic:** Evaluates to a `SLICE` opcode in the VM. For native codegen, calls a `_slice_string` runtime helper that allocates a new buffer, copies the bytes, and null-terminates the result.

**Example:**
```nova
s = "hello world"
print(s[0:5])    # "hello"
print(s[6:11])   # "world"
```

### String Escape Sequences

Nova strings support the following escape sequences:

| Escape | Character | Description |
|--------|-----------|-------------|
| `\n` | Newline | Line feed |
| `\t` | Tab | Horizontal tab |
| `\r` | Return | Carriage return |
| `\\` | Backslash | Literal backslash |
| `\"` | Quote | Double quote inside string |
| `\0` | Null | Null character |
| `\b` | Backspace | Backspace |
| `\a` | Bell | Alert/bell |
| `\f` | Form feed | Form feed |
| `\v` | VTab | Vertical tab |

**Example:**
```nova
print("Hello\nWorld")       # Two lines
print("Tab:\there")          # Tab-separated
print("She said \"hi\"")    # Escaped quotes
```

---

## Type Keywords

### `int`, `float`, `bool`, `string`
**Use:** Explicit type annotations for variables, parameters, and return types.
**Logic:** Used by the parser to attach type metadata to `Assignment`, `Function`, and `Data` nodes. The `TypeChecker` validates type consistency at compile time — mismatched assignments or function arguments raise a `StaticTypeError` before bytecode generation.

---

## List Operations

### List Literals: `[1, 2, 3]`
**Use:** Create a list with initial elements.
**Logic:** Evaluates a `BUILD_LIST` opcode that pops N elements from the stack and creates a Python list in the VM.

### `.append(val)`, `.pop()`, `.insert(idx, val)`, `.clear()`
**Use:** Dynamic list manipulation methods.
**Logic:** Evaluate to `LIST_APPEND`, `LIST_POP`, `LIST_INSERT`, and `LIST_CLEAR` opcodes respectively. The VM operates directly on the underlying Python list.

### `list[idx]` and `list[idx] = val`
**Use:** Index-based access and mutation.
**Logic:** Evaluates to `LOAD_INDEX` and `STORE_INDEX` opcodes.

---

## CLI Modes

Nova supports two execution modes:

| Command | Mode | Description |
|---------|------|-------------|
| `nova dev <file.nv>` | Development | Runs in VM — fast iteration, no .exe build step |
| `nova build <file.nv>` | Production | Compiles to native x86 executable via GCC |
| `nova run <file.nv>` | Development | Backward-compatible alias for `dev` |

---

## Self-Hosted Compiler Components

### `stdlib/lexer.nv`
**Use:** Tokenizer written entirely in Nova.
**Logic:** Character-by-character scanner using `is_digit()`, `is_alpha()`, and `match_keyword()` helper functions. Produces a list of `Token` structs with `kind` and `val` fields. Handles strings with escape sequences, multi-character operators (`==`, `!=`, `<=`, `>=`, `->`), comments, and all Nova keywords including `elif`, `has`, `const`.

### `stdlib/parser.nv`
**Use:** Recursive-descent parser written in Nova.
**Logic:** Imports `lexer.nv`. Implements a full expression hierarchy (`parse_primary` → `parse_unary` → `parse_mul` → `parse_add` → `parse_compare` → `parse_logic` → `parse_expr`) and statement parsing (`parse_statement` for assignments, if/elif/else, while, for, break, continue, return, functions). Produces a list of `AstNode` structs representing the program AST.

### `stdlib/codegen.nv`
**Use:** x86-32 assembly code generator written in Nova.
**Logic:** Imports `parser.nv`. Walks the AST and emits Intel-syntax x86 assembly using a `CodegenState` struct that tracks assembly lines, data section entries, string literals, label counters, local variable offsets, loop label stacks, per-struct field offset tables (`struct_names`, `struct_field_names`, `struct_field_offsets`), and variable-to-struct-type mappings (`var_struct_types`). Implements:
- Stack-based function calling convention (`push ebp` / `mov ebp, esp`)
- Variable scanning for local stack allocation
- Loop label stacks for `break`/`continue` support
- Comparison operators via conditional jumps
- Per-struct field offset resolution for `DataFieldAccess`/`DataFieldAssign`
- Variable struct type tracking via constructor calls and array-index assignment
- Format string selection (`fmt_int` vs `fmt_str`) for `print`
- String concatenation via `_concat_strings` runtime helper
- String slicing via `_slice_string` runtime helper

### `stdlib/compiler.nv`
**Use:** Compiler entry point that orchestrates the full pipeline.
**Logic:** Imports `lexer.nv`, `parser.nv`, `codegen.nv`, `assembler.nv`, `linker.nv`, and the platform runtime facades. Exposes `compile_file(path)` which reads a `.nv` source file, tokenizes → parses → generates assembly → assembles → links, returning a `CompilePackage` struct with both the assembly lines and linked binary image. `compile_to_file(input, output)` writes the assembly to `.s` and the linked binary to `.s.bin`.

### `stdlib/assembler.nv`
**Use:** x86 instruction encoder and assembler written in Nova.
**Logic:** Parses Intel-syntax assembly lines into `AsmLine` structs, then runs a two-pass assembly: `pass1_collect_labels` to calculate label offsets and encode instructions, and `resolve_fixups` to patch jump targets. Encodes a wide range of x86 instructions (mov, push, pop, add, sub, imul, idiv, cmp, je, jmp, call, ret, etc.) with ModRM/SIB byte encoding for memory addressing modes.

### `stdlib/linker.nv`
**Use:** Binary linker that packages code and data sections into a structured image.
**Logic:** Takes the two-section output from `assemble()` (code bytes and data bytes) and produces a linked binary image with an `NVL3` header containing section offsets, sizes, and entry point metadata.

### `stdlib/os_win.nv` / `stdlib/os_linux.nv`
**Use:** OS-specific syscall façade for the self-hosted compiler's I/O operations.
**Logic:** Provides `sys_open`, `sys_read`, `sys_write`, `sys_write_raw`, `sys_close` functions that abstract OS-level file I/O. The self-hosted compiler imports the appropriate facade instead of using built-in `open`/`read`/`close` directly, enabling cross-platform compilation.
