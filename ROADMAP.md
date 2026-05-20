# Nova Future Roadmap

The Nova programming language aims to provide Python-like simplicity while maintaining full low-level control comparable to C/Rust. A key philosophy of Nova is **avoiding cryptic syntax** (like `*` or `&` for pointers) in favor of intuitive, logical abstractions (such as `ptr.value`, `ptr.addr`, or array-like indexing).

With our Custom Bytecode Virtual Machine, foundational OOP features, High-Level ARC, and FFI bridging now implemented, here are the **next top 5 paths** for the future development of Nova:

## 1. Self-Hosting the Compiler

**Goal:** Rewrite the Nova compiler (Lexer, Parser, Compiler) directly in Nova, completely detaching from Python.

*   **Bootstrapping:** Use the current Python-based compiler to compile a Nova-written compiler into custom bytecode.
*   **Dogfooding:** By writing the compiler in Nova, we will stress-test our own language features (Classes, Arrays, Structs, String manipulation) and uncover necessary ergonomics improvements.
*   **Simplicity Focus:** The compiler itself should remain highly readable. We will continue using a clean Recursive Descent approach in Nova without relying on complex, external compiler-compiler tools (like Yacc/Bison).

## 2. Advanced Static Type System & Inference

**Goal:** Introduce strict compile-time safety while keeping the typing system mostly invisible to the developer.

*   **Type Inference Engine:** Implement a system where types are strictly checked at compile-time but rarely need to be explicitly declared by the user (e.g., `x = 5` is strictly an `int`, verified by the compiler without requiring `int x = 5`).
*   **Interfaces and Traits:** Expand the current Class system by introducing Interfaces. Keep OOP simple by avoiding the "diamond problem" (no multiple inheritance).
*   **Compiler Validations:** Throw clear `NovaError`s during the bytecode compilation phase if an incorrect type is passed to a function or method, rather than failing at runtime.

## 3. Comprehensive Native Standard Library

**Goal:** Build a rich, built-in standard library so developers don't have to rely on external tools for basic tasks.

*   **Built Natively in Nova:** The standard library (File I/O, Networking, Timers) will be written entirely in Nova, wrapping core `@raw` system calls inside high-level intuitive classes (e.g., `File`).
*   **Advanced Collections:** Implement core data structures (Lists, Maps, Sets) using highly optimized Data Structures and Algorithms underneath. High-level programming will feel extraordinarily fast due to the `@raw` memory control optimizing the backend collections.
*   **Simplicity Focus:** Standardize intuitive methods. For example, reading a file should just be `content = File.read("data.txt")`.

## 4. Multi-Threading and Concurrency

**Goal:** Introduce modern, safe, and intuitive multi-threading capabilities.

*   **Async/Await Syntax:** Provide high-level asynchronous programming using Python-like `async` and `await` keywords, making network and file I/O operations non-blocking by default.
*   **Low-Level Threading via `@raw`:** For performance-critical blocks, allow developers to spawn raw OS threads using the C FFI (`pthreads`), directly mapping work to CPU cores without fighting a Global Interpreter Lock.

## 5. Enhanced Tooling and Package Manager

**Goal:** Provide a world-class developer experience straight out of the box.

*   **Nova Package Manager (NPM / NVP):** A built-in command line tool for easily sharing and downloading Nova libraries globally.
*   **Built-in Formatter & Linter:** Enforce clean, readable code style universally across all Nova projects automatically via `nova fmt`.
*   **Language Server Protocol (LSP):** Build an LSP to integrate deeply with VSCode, providing real-time autocompletion, type hinting (from the inference engine), and inline documentation for developers.
