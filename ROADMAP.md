# Nova Future Roadmap

The Nova programming language aims to provide Python-like simplicity while maintaining full low-level control comparable to C/Rust. A key philosophy of Nova is **avoiding cryptic syntax** (like `*` or `&` for pointers) in favor of intuitive, logical abstractions (such as `ptr.value`, `ptr.addr`, or array-like indexing).

With our Custom Bytecode Virtual Machine, foundational OOP features (Classes, `self`, `__init__` auto-calling), High-Level ARC, and FFI bridging now implemented, here are the **next top 5 paths** for the future development of Nova:

## 1. Algorithmic Data Structure Optimization (Backend)

**Goal:** Ensure that high-level programming feels blazingly fast by implementing strict, optimized Data Structures and Algorithms (DSA) under the hood.

*   **Optimized Built-ins:** Re-write the backing mechanics of high-level arrays, lists, and maps inside the VM using highly optimized C-style contiguous memory blocks and hash algorithms.
*   **Zero-Cost Abstractions:** When a user writes `list.append(5)` in high-level Nova, the backend will use an optimized dynamic array scaling algorithm (`O(1)` amortized) rather than a naive Python list wrapper.

## 2. Self-Hosting the Compiler

**Goal:** Rewrite the Nova compiler (Lexer, Parser, Compiler) directly in Nova, completely detaching from Python.

*   **Bootstrapping:** Use the current Python-based compiler to compile a Nova-written compiler into custom bytecode.
*   **Dogfooding:** By writing the compiler in Nova, we will stress-test our own language features (Classes, Arrays, Structs, String manipulation) and uncover necessary ergonomics improvements.

## 3. Advanced Static Type System & Inference

**Goal:** Introduce strict compile-time safety while keeping the typing system mostly invisible to the developer.

*   **Type Inference Engine:** Implement a system where types are strictly checked at compile-time but rarely need to be explicitly declared by the user (e.g., `x = 5` is strictly an `int`, verified by the compiler without requiring `int x = 5`).
*   **Interfaces and Traits:** Expand the current Class system by introducing Interfaces. Keep OOP simple by avoiding the "diamond problem" (no multiple inheritance).

## 4. Comprehensive Native Standard Library

**Goal:** Build a rich, built-in standard library so developers don't have to rely on external tools for basic tasks.

*   **Built Natively in Nova:** The standard library (File I/O, Networking, Timers) will be written entirely in Nova, wrapping core `@raw` FFI system calls inside high-level intuitive classes (e.g., `File`).
*   **Simplicity Focus:** Standardize intuitive methods. For example, reading a file should just be `content = File.read("data.txt")`.

## 5. Multi-Threading and Concurrency

**Goal:** Introduce modern, safe, and intuitive multi-threading capabilities.

*   **Async/Await Syntax:** Provide high-level asynchronous programming using Python-like `async` and `await` keywords, making network and file I/O operations non-blocking by default.
*   **Low-Level Threading via `@raw`:** For performance-critical blocks, allow developers to spawn raw OS threads using the C FFI (`pthreads`), directly mapping work to CPU cores natively.