# Nova Programming Language

A language that bridges high-level simplicity with low-level control.

## Installation

```bash
# Clone the repository
git clone https://github.com/laksh-goyal22/Nova.git
cd Nova

# Install dependencies
pip install llvmlite

# Ensure clang is installed (for LLVM)
# On Windows: download LLVM from https://releases.llvm.org/
# On Linux: sudo apt-get install clang
# On Mac: brew install llvm
```

## Usage
```bash
# Run a Nova program
.\nova run program.nv

# Build only (generate LLVM IR)
.\nova build program.nv
Example
nova
def fibonacci(n) {
    a = 0
    b = 1
    i = 0
    while i < n {
        temp = a
        a = b
        b = temp + b
        i = i + 1
    }
    return a
}

i = 0
while i < 10 {
    print(fibonacci(i))
    i = i + 1
}

```

## Language Features
- ✅ Variables and expressions
- ✅ Functions with parameters
- ✅ While loops
- ✅ For loops
- ✅ If-else conditionals
- ✅ Print statement
- ✅ Raw memory allocation (`alloc`, `free`)
- ✅ Data structures (`data` blocks)
- ✅ Low-level / High-level bridge (`@raw` and `@export`)
- ✅ Classes and Objects
- 🔄 Arrays/Lists (planned)

## Future Roadmap: Top 5 Paths

1. **Custom Compiler Backend (Independence):** Remove dependencies on Python and LLVM by writing a custom compiler backend directly in Nova or C/Rust. This will generate machine code directly or a custom VM bytecode, achieving total independence.
2. **Advanced OOP & Type System:** Expand current Classes and Objects to support inheritance, interfaces, and methods. Implement a robust type checker for static typing guarantees, including type inference.
3. **Comprehensive Standard Library:** Build out a rich standard library natively in Nova, including file I/O, networking, and common data structures (HashMaps, Arrays/Lists).
4. **C Interoperability (FFI):** Leverage the `@raw` blocks to build a seamless Foreign Function Interface (FFI) for linking and using C libraries directly without complex wrappers.
5. **Memory Management Improvements:** Introduce a hybrid memory management model (e.g., optional garbage collection for high-level objects, while retaining manual `alloc`/`free` for `@raw` low-level blocks).

## Project Structure
```
nova/
├── ast/        # Abstract Syntax Tree
├── lexer/      # Tokenizer
├── parser/     # Parser
├── codegen/    # LLVM Code Generator
├── main.py     # Entry point
└── nova.bat    # Runner script

```

## License

This project is licensed under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial 4.0)

- ✅ Personal and educational use allowed
- ✅ Modification and sharing allowed
- ✅ Contributions welcome
- ❌ Commercial use strictly prohibited

For commercial licensing, contact: [developer.laksh22@gmail.com]