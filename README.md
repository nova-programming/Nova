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

- ✅ If-else conditionals

- ✅ Print statement

- ✅ Raw memory allocation

- 🔄 Data structures (planned)

- 🔄 Arrays/Lists (planned)

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