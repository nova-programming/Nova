# Nova Programming Language

A language that bridges high-level Pythonic simplicity with low-level C-like control. Nova empowers developers by removing cryptic syntax (like `*` or `&` for pointers), integrating high-level Automatic Reference Counting (ARC) alongside manual memory management blocks, and compiling down to a custom high-performance Virtual Machine.

**Nova is now self-hosting** — a compiler written entirely in Nova (`stdlib/compiler.nv`) can lex, parse, and compile Nova source code into x86 assembly, which GCC assembles into native executables. No Python, C, or any third-party dependency is needed at runtime.

## Installation

```bash
# Clone the repository
git clone https://github.com/laksh-goyal22/Nova.git
cd Nova

# The compiler runs on standard Python 3. No external C++ or LLVM dependencies required!
```

## Usage
```bash
# Development mode — run in VM (fast iteration, no build step)
python main.py dev program.nv

# Production mode — compile to native x86 executable
python main.py build program.nv

# Backward-compatible alias for 'dev'
python main.py run program.nv

# Self-hosted compilation pipeline (Nova compiling Nova)
python main.py dev stdlib/compiler.nv    # Compiles test_input.nv -> test_output.s
gcc -m32 test_output.s -o program.exe    # Assemble with GCC
./program.exe                            # Run native binary
```

## Example (High-Level and Low-Level Combined)
```nova
# Import a Nova module
import math_utils

data Point {
    x: int
    y: int
}

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

# Auto-constructor, string conversion, operator overloading
v1 = Vector(3, 4)
v2 = Vector(1, 2)
print(v1 + v2)          # Vector(4, 6)
print("v1 = " + str(v1)) # v1 = Vector(3, 4)

# Const and escape sequences
const MAX = 100
print("Max is:\t" + str(MAX))

# Low-level memory management (safety-enforced)
@raw {
    mem_ptr = alloc(8)
    mem_ptr.value = 99
    print(mem_ptr.value)
    free(mem_ptr)
}
```

## Language Features
- ✅ Variables and expressions (inferred and explicit types)
- ✅ Gradual typing with `mut` for dynamic variables
- ✅ Immutable variables with `const`
- ✅ Functions with typed parameters and return types
- ✅ While & For loops (with `to`, `downto`, `step`)
- ✅ If-else conditionals (nested)
- ✅ Break and Continue
- ✅ Logical operators (`and`, `or`, `not`)
- ✅ Print statement (with `__str__` dunder support)
- ✅ String escape sequences (`\n`, `\t`, `\\`, `\"`, `\r`, `\0`, `\b`, `\a`, `\f`, `\v`)
- ✅ `str()` built-in for value-to-string conversion
- ✅ Raw memory allocation (`alloc`, `free`, pointer operations)
- ✅ **`@raw` safety boundary** — `alloc`/`free`/pointer ops error outside `@raw`
- ✅ Data structures (`data` blocks with typed fields)
- ✅ Low-level / High-level bridge (`@raw` and `@export`)
- ✅ Classes with **dunder methods** (`__init__`, `__str__`, `__len__`, `__eq__`, `__add__`, `__sub__`, `__mul__`)
- ✅ Seamless C Interoperability (FFI via `import`)
- ✅ High-Level Automatic Reference Counting (ARC) Memory Model
- ✅ Custom Bytecode Virtual Machine Backend
- ✅ Built-in File I/O (`open`, `read`, `write`, `close`)
- ✅ `.nv` File Import System (module resolution with circular import prevention)
- ✅ Self-Hosted Lexer (tokenizer written in Nova)
- ✅ Self-Hosted Parser (recursive-descent parser written in Nova)
- ✅ Static Type Checker (compile-time type validation)
- ✅ String mutation and indexing
- ✅ Dynamic Arrays/Lists (`append`, `pop`, `insert`, `clear`)
- ✅ **Self-Hosted Native Compiler** (Nova → x86 assembly → native binary)
- ✅ **Dev/Build CLI modes** for fast iteration vs native compilation

## Architecture Details

To understand the core mechanics and reasoning behind Nova's keywords, please see:
* [ROADMAP.md](ROADMAP.md) - The future plans and logic for language features.
* [KEYWORDS_AND_LOGIC.md](KEYWORDS_AND_LOGIC.md) - Detailed breakdown of every keyword's backend logic and usage intent.

## Project Structure
```
nova/
├── ast/           # Abstract Syntax Tree Nodes
├── compiler/      # Static Type Checker & x86 Codegen
├── lexer/         # Tokenizer (regex + escape processing)
├── modules/       # Module resolver for .nv file imports
├── parser/        # Recursive Descent Parser
├── stdlib/        # Standard library (.nv modules + self-hosted compiler)
│   ├── compiler.nv   # Self-hosted compiler entry point (imports lexer/parser/codegen)
│   ├── lexer.nv      # Self-hosted tokenizer (character-by-character tokenization)
│   ├── parser.nv     # Self-hosted recursive-descent parser (tokens → AST)
│   ├── codegen.nv    # Self-hosted x86 code generator (AST → assembly)
│   └── math_utils.nv # Math utility functions
├── vm/            # Custom Bytecode Compiler & Virtual Machine
├── main.py        # Entry point (dev / build / run)
└── test.nv        # Comprehensive test suite (16 sections)
```

## Self-Hosted Compiler Pipeline

```
┌─────────────┐     ┌──────────────────┐     ┌───────────┐     ┌──────────┐
│ program.nv  │────▶│ stdlib/compiler.nv│────▶│ program   │────▶│ Native   │
│ (Nova source)│     │ (runs in Nova VM)│     │    .s     │     │ Binary   │
└─────────────┘     └──────────────────┘     │(x86 asm)  │     │  .exe    │
                                              └─────┬─────┘     └──────────┘
                                                    │ GCC            ▲
                                                    └────────────────┘
```

The self-hosted compiler is split across 4 modular Nova files:
- **`lexer.nv`:** Character-by-character tokenizer with keyword matching and escape handling
- **`parser.nv`:** Recursive descent parser producing an in-memory AST (expressions, statements, functions, loops)
- **`codegen.nv`:** x86-32 assembly emitter with stack-based calling convention, loop labels, and break/continue
- **`compiler.nv`:** Entry point that imports and orchestrates lexer → parser → codegen pipeline

## License

This project is licensed under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial 4.0)

- ✅ Personal and educational use allowed
- ✅ Modification and sharing allowed
- ✅ Contributions welcome
- ❌ Commercial use strictly prohibited

For commercial licensing, contact: [developer.laksh22@gmail.com]