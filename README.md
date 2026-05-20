# Nova Programming Language

A language that bridges high-level Pythonic simplicity with low-level C-like control. Nova empowers developers by removing cryptic syntax (like `*` or `&` for pointers), integrating high-level Automatic Reference Counting (ARC) alongside manual memory management blocks, and compiling down to a custom high-performance Virtual Machine.

## Installation

```bash
# Clone the repository
git clone https://github.com/laksh-goyal22/Nova.git
cd Nova

# The compiler runs on standard Python 3. No external C++ or LLVM dependencies required!
```

## Usage
```bash
# Run a Nova program
python main.py run program.nv
```

## Example (High-Level and Low-Level Combined)
```nova
data Point {
    x: int
    y: int
}

class SystemMonitor {
    name
    version

    def init(monitorName, v) {
        self.name = monitorName
        self.version = v
        print("Initialized:")
        print(self.name)
    }

    def checkMemory() {
        @raw {
            # Low Level C-like memory control
            import "c" as libc
            libc.puts("Running FFI inside Nova!")

            mem_ptr = alloc(8)
            print(sizeof(mem_ptr)) # Returns bytes allocated

            mem_ptr.value = 99
            free(mem_ptr)
        }
    }
}

monitor = SystemMonitor()
monitor.init("NovaCore", 1)
monitor.checkMemory()
```

## Language Features
- ✅ Variables and expressions
- ✅ Functions with parameters
- ✅ While & For loops
- ✅ If-else conditionals
- ✅ Print statement
- ✅ Raw memory allocation (`alloc`, `free`)
- ✅ Data structures (`data` blocks)
- ✅ Low-level / High-level bridge (`@raw` and `@export`)
- ✅ Classes and Objects (OOP with `self`)
- ✅ Seamless C Interoperability (FFI via `import`)
- ✅ High-Level Automatic Reference Counting (ARC) Memory Model
- ✅ Custom Bytecode Virtual Machine Backend
- ✅ Built-in File I/O (`open`, `read`, `write`, `close`)
- 🔄 Arrays/Lists (planned)

## Architecture Details

To understand the core mechanics and reasoning behind Nova's keywords, please see:
* [ROADMAP.md](ROADMAP.md) - The future plans and logic for language features.
* [KEYWORDS_AND_LOGIC.md](KEYWORDS_AND_LOGIC.md) - Detailed breakdown of every keyword's backend logic and usage intent.

## Project Structure
```
nova/
├── ast/        # Abstract Syntax Tree Nodes
├── lexer/      # Tokenizer and Regex definitions
├── parser/     # Recursive Descent Parser
├── vm/         # Custom Bytecode Compiler & Virtual Machine
├── main.py     # Entry point
```

## License

This project is licensed under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial 4.0)

- ✅ Personal and educational use allowed
- ✅ Modification and sharing allowed
- ✅ Contributions welcome
- ❌ Commercial use strictly prohibited

For commercial licensing, contact: [developer.laksh22@gmail.com]