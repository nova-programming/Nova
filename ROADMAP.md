# Nova Future Roadmap

The Nova programming language aims to provide Python-like simplicity while maintaining full low-level control comparable to C/Rust. A key philosophy of Nova is **avoiding cryptic syntax** (like `*` or `&` for pointers) in favor of intuitive, logical abstractions (such as `ptr.value`, `ptr.addr`, or array-like indexing).

With our Custom Bytecode Virtual Machine, OOP with dunder methods, High-Level ARC, FFI bridging, `.nv` file imports, a self-hosted Lexer & Parser, Dynamic Lists, a **Self-Hosted Native Compiler**, and the recent **Python-Simplicity Features** now implemented, here are the **next top 5 paths** for the future development of Nova:

## 1. Self-Hosting the Compiler ✅ *(Phase 1 & 2 Complete)*

**Goal:** Rewrite the Nova compiler (Lexer, Parser, Code Generator) directly in Nova, making the language completely independent.

### Completed
*   **Self-Hosted Lexer (`stdlib/lexer.nv`):** A complete character-by-character tokenizer written entirely in Nova. Recognizes all token types: keywords, identifiers, numbers, strings, operators, delimiters, directives, and comments.
*   **Self-Hosted Parser (`stdlib/parser.nv`):** A recursive-descent parser written in Nova that generates an AST for all major language constructs (functions, classes, data structs, control flow, imports).
*   **Self-Hosted Code Generator (`stdlib/codegen.nv`):** A full x86-32 assembly emitter written in Nova with stack-based variable management, loop label stacks, and function compilation.
*   **Self-Hosted Compiler Entry Point (`stdlib/compiler.nv`):** Orchestrates the pipeline by importing `lexer.nv`, `parser.nv`, and `codegen.nv`. Reads a `.nv` file, tokenizes → parses → generates assembly.
*   **`.nv` File Import System (`modules/resolver.py`):** Full module resolution with circular import prevention, multi-directory search (relative, project root, stdlib/), and seamless integration with the compiler pipeline.
*   **Dynamic Arrays/Lists:** Full in-memory AST construction using lists with `append`, `pop`, `insert`, and `clear` operations.

### Supported Features (Self-Hosted Compiler)
*   Functions with parameters and return values
*   Recursive function calls (e.g., factorial, fibonacci, power)
*   If/else control flow (nested)
*   While loops (including nested)
*   For loops (`to`, `downto`, `step`)
*   Break and Continue (with loop label stacks)
*   Logical operators: `and`, `or`, `not`
*   Unary negation (`-x`)
*   String and integer print output (with automatic type inference)
*   All arithmetic operators: `+`, `-`, `*`, `/`, `%`
*   All comparison operators: `==`, `!=`, `<`, `>`, `<=`, `>=`
*   Variable declarations (`mut`) and assignments

### Known Limitations (Self-Hosted Compiler)
*   No support for classes, data structs, or lists in native codegen
*   No `str()` conversion in native codegen (use VM dev mode for string operations)
*   Generates 32-bit x86 assembly (requires GCC with `-m32` flag)

### Remaining
*   **Full Feature Parity:** Extend the self-hosted compiler to support all Nova language features (classes, data structs, lists, for loops, boolean operators).
*   **Self-Compilation (Bootstrapping):** Compile `stdlib/compiler.nv` using itself — the ultimate test of language independence.
*   **64-bit x86_64 Support:** Generate 64-bit assembly for modern platforms.

## 2. Python-Simplicity Features ✅ *(Complete)*

**Goal:** Make Nova feel as natural as Python while maintaining full low-level control.

### Completed
*   **Auto-Constructor (`__init__`):** Classes can now define `__init__` methods that are automatically called on instantiation. `Vehicle("NovaCar", 60)` just works — no separate `.init()` call needed.
*   **Dunder Methods (Special Methods):** Full Python-like operator overloading:
    - `__str__()` — auto-called by `print()` and `str()`
    - `__len__()` — auto-called by `len()`
    - `__eq__(other)` — auto-called by `==` operator
    - `__add__(other)` — auto-called by `+` operator
    - `__sub__(other)` — auto-called by `-` operator
    - `__mul__(other)` — auto-called by `*` operator
*   **String Escape Sequences:** Full support for `\n`, `\t`, `\r`, `\\`, `\"`, `\0`, `\b`, `\a`, `\f`, `\v`.
*   **`str()` Built-in:** Convert any value to string: `str(42)` → `"42"`, `str(true)` → `"true"`. Supports `__str__` for class instances.
*   **`const` Keyword:** Opt-in immutability — `const PI = 3` prevents reassignment at compile time.
*   **`@raw` Safety Boundary:** The type checker now **enforces** that `alloc()`, `free()`, and pointer operations are only used inside `@raw` blocks. Using them outside raises a `StaticTypeError`.
*   **Dev/Build CLI Modes:** `nova dev file.nv` for fast VM iteration, `nova build file.nv` for native compilation.

## 3. Advanced Static Type System & Inference

**Goal:** Introduce strict compile-time safety while keeping the typing system mostly invisible to the developer.

### Completed
*   **Static Type Checker (`compiler/type_checker.py`):** Validates type consistency for assignments, function parameters, return types, and binary operations at compile time. Supports gradual typing via `mut` for dynamic variables. Enforces `@raw` safety boundary and `const` immutability.

### Remaining
*   **Type Inference Engine:** Implement a system where types are strictly checked at compile-time but rarely need to be explicitly declared by the user (e.g., `x = 5` is strictly an `int`, verified by the compiler without requiring `int x = 5`).
*   **Interfaces and Traits:** Expand the current Class system by introducing Interfaces. Keep OOP simple by avoiding the "diamond problem" (no multiple inheritance).
*   **Compiler Validations:** Throw clear `NovaError`s during the bytecode compilation phase if an incorrect type is passed to a function or method, rather than failing at runtime.

## 4. Comprehensive Native Standard Library

**Goal:** Build a rich, built-in standard library so developers don't have to rely on external tools for basic tasks.

### Completed
*   **Math Utilities (`stdlib/math_utils.nv`):** Square, cube, absolute value, min, max, factorial — all written in Nova and importable via the module system.
*   **File I/O:** `open`, `read`, `write`, `close` exist as built-in VM opcodes.

### Remaining
*   **Built Natively in Nova:** The standard library (Networking, Timers) will be written entirely in Nova, wrapping core `@raw` system calls inside high-level intuitive classes (e.g., `File`).
*   **Advanced Collections:** Implement core data structures (Lists, Maps, Sets) using highly optimized Data Structures and Algorithms underneath. High-level programming will feel extraordinarily fast due to the `@raw` memory control optimizing the backend collections.
*   **Simplicity Focus:** Standardize intuitive methods. For example, reading a file should just be `content = File.read("data.txt")`.

## 5. Multi-Threading and Concurrency

**Goal:** Introduce modern, safe, and intuitive multi-threading capabilities.

*   **Async/Await Syntax:** Provide high-level asynchronous programming using Python-like `async` and `await` keywords, making network and file I/O operations non-blocking by default.
*   **Low-Level Threading via `@raw`:** For performance-critical blocks, allow developers to spawn raw OS threads using the C FFI (`pthreads`), directly mapping work to CPU cores without fighting a Global Interpreter Lock.

## 6. Enhanced Tooling and Package Manager

**Goal:** Provide a world-class developer experience straight out of the box.

*   **Nova Package Manager (NPM / NVP):** A built-in command line tool for easily sharing and downloading Nova libraries globally.
*   **Built-in Formatter & Linter:** Enforce clean, readable code style universally across all Nova projects automatically via `nova fmt`.
*   **Language Server Protocol (LSP):** Build an LSP to integrate deeply with VSCode, providing real-time autocompletion, type hinting (from the inference engine), and inline documentation for developers.
