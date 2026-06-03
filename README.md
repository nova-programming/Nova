# Nova Programming Language

A language that bridges high-level Pythonic simplicity with low-level C-like control. Nova features a **fully functional self-hosted compiler pipeline** — the compiler is written in Nova itself, can lex, parse, and generate x86 assembly, and bootstraps via GCC to produce native executables.

## Installation

```bash
git clone https://github.com/laksh-goyal22/Nova.git
cd Nova
# Requires Python 3 and MinGW GCC (Windows) or GCC (Linux)
```

## Usage

```bash
# Build to native executable (uses GCC as linker)
python main.py build program.nv

# Build using self-hosted compiler (no GCC needed)
nova_main.exe build program.nv

# Run in the Python bytecode VM (fast iteration)
python main.py dev program.nv

# Assemble .s file and link directly (GCC-free, uses self-hosted assembler+linker)
nova_main.exe assemble-link input.s output.exe

# Build to bare-metal flat binary (no PE headers, no imports)
nova_main.exe build-bare program.nv 31744 _start
nova_main.exe assemble-bare program.s output.bin 0x7C00
```

## Self-Hosted Bootstrap Chain

The compiler is written in Nova and bootstraps in three stages:

1. **Stage 0** — Python compiler (`main.py`) compiles `nova_main.nv` → `nova_main.s` → GCC → `nova_main.exe`
2. **Stage 1** — `nova_main.exe` (self-hosted compiler) compiles `nova_main.nv` → `nova_main.s` → GCC `nova_main.exe`. Non-self builds use the GCC-free `assemble-link` path: `.s` → `assembler.nv` → `linker.nv` → `.exe` (no external toolchain).
3. **Stage 2** — The Nova-compiled executable can now recompile itself, proving the bootstrap is self-sustaining

The compiler pipeline within a single invocation:

```
.nv source → lexer.nv → parser.nv → type_checker.nv → codegen.nv → assembler.nv → linker.nv → .exe
```

Additional standard library modules:
- `types.nv` — Type system abstraction (scalar, struct, list, func types)
- `type_checker.nv` — Static type inference and enforcement
- `errors.nv` — Structured error/warning printer with fix suggestions
- `assembler.nv` — x86-32 instruction encoder (assembles .s text into byte streams, integrated)
- `linker.nv` — Windows PE executable generator (packages bytes into .exe directly, integrated)
- `memory.nv` — Raw memory byte access utilities

## Project Structure

```
nova/
├── ast/              # AST node definitions (Python)
├── compiler/         # Type checker (Python)
├── lexer/            # Reference tokenizer (Python)
├── parser/           # Reference parser (Python)
├── stdlib/           # Self-hosted compiler written in Nova
│   ├── lexer.nv          # Tokenizer (Nova)
│   ├── parser.nv         # Recursive-descent parser (Nova)
│   ├── codegen.nv        # x86-32 code generator (Nova)
│   ├── codegen_expr.nv   # Expression codegen (Nova)
│   ├── codegen_stmt.nv   # Statement codegen (Nova)
│   ├── compiler.nv       # Pipeline orchestrator (Nova)
│   ├── compiler_driver.nv# CLI driver for compiler (Nova)
│   ├── assembler.nv      # x86 assembler (Nova, integrated via assemble_link_file)
│   ├── assembler_parse.nv# Assembly line/operand parsing (Nova)
│   ├── assembler_encode.nv# Instruction encoding (Nova)
│   ├── assembler_pass.nv # Pass1 + fixup resolution (Nova)
│   ├── types.nv          # Type system abstraction (Nova)
│   ├── type_checker.nv   # Static type inference (Nova)
│   ├── linker.nv         # Native PE linker (Nova, integrated via assemble_link_file)
│   ├── memory.nv         # Raw memory byte access (Nova)
│   ├── errors.nv         # Structured error/warning printer (Nova)
│   ├── os_win.nv         # Windows syscall/runtime facade (Nova)
│   ├── os_linux.nv       # Linux syscall/runtime facade (Nova)
│   └── math_utils.nv     # Math utilities (Nova)
├── main.py           # Python bootstrap compiler entry point
├── nova_main.nv      # Self-hosted compiler entry point
├── modules/          # Standard library modules (Nova)
├── docs/             # Documentation
└── tests/            # Test programs
```

## Language Features

- **Static type inference** — full type checking with `int`, `float`, `bool`, `string`, `byte`, `void`, `list[T]`, struct types
- **Array bounds checking** — runtime bounds checks on all list/array access, safe termination on out-of-bounds
- **List type unification** — `[1, 2, 3]` infers `list[int]`; heterogenous lists rejected at compile time
- **Compile-time constant folding** — `1 + 2 * 3` evaluates to `7` at compile time, emits single `push 7`
- **Capacity-based list allocation** — `append` doubles capacity exponentially, no realloc on every insertion
- **Float literals + x87 runtime** — `x = 3.14; print(x)` uses IEEE 754 single precision, x87 FPU for arithmetic
- **For-in loops `for i in items { ... }`** — iterate over list elements directly
- **Boolean short-circuit** — `and`/`or` skip right operand evaluation when left determines the result
- **Debug prints (`printd`)** — `printd(x)` outputs `debug - [line N]: <value>` with automatic line number, enabled via `--debug` flag
- **Smart error messages** — compiler errors include error category, line number, and fix suggestions
- Variables and expressions (inferred typing)
- Mutable by default; `const` for immutability
- Functions with typed parameters and return types
- While & For loops (with `to`, `downto`, `step`)
- If-elif-else conditionals
- `break` / `continue`
- Logical operators (`and`, `or`, `not`)
- Bitwise operators (`&`, `<<`, `>>`)
- Data structs with `has` field-existence check
- String slicing `s[i:j]`
- String escape sequences
- Raw memory blocks (`@raw`) with `alloc`/`free`
- Data structures (`data` blocks)
- FFI to C libraries
- Module import system (circular-import-safe)
- Bare-metal flat binary output (`build-bare` / `assemble-bare`, no PE headers)
- `@raw` block assembly passthrough (lines starting with x86 mnemonics emit raw assembly; others compile as normal Nova)
- `@export { name1, name2 }` inside `@raw` blocks for `.global` symbol export
- **Self-Hosted Assembler & Linker** — fully integrated in-process x86 assembler and PE executable linker, entirely eliminating the GCC dependency.
- **Variable-to-Register Promotion** — greedily maps local variables to CPU registers (`esi`/`edi`), massively boosting runtime performance.
- **Native Standard Library Injection** — standard library functions (from `os_win` and `math_utils`) are automatically injected and natively compiled into all executables, removing the need for manual imports of core modules.
- **Automatic CSPRNG Initialization** — the built-in ChaCha20 random number generator automatically seeds itself at runtime using the Windows tick count (`sys_get_tick_count()`), removing the need for manual seeding initialization.
- Self-hosted lexer, parser, codegen, type checker

## License

CC BY-NC 4.0 — personal/educational use allowed; commercial use prohibited.
