# Nova Native Compiler Internals (`stdlib/compiler.nv` & `nova.nv`)

The compilation pipeline orchestrates tokenizer → parser → codegen → in-process assembler → in-process linker.

## Entry Points

- **`nova.nv`**: CLI entry point for the self-hosted native compiler. Parses `build` command (reads `.nv` → `compile_to_exe()` → native PE executable) or `assemble-link` command (reads `.s` → `assemble_link_file()` → in-process PE generation).
- **`stdlib/compiler.nv`**: Core library exposing `compile_file(path)`, `compile_to_file(input, output)`, `compile_to_exe(input, output, debug_mode)`, and `assemble_link_file(asm_path, output_path)`. Orchestrates full pipeline: read file → tokenize → parse → resolve imports → type check → generate assembly.
- **`stdlib/compiler_driver.nv`**: Minimal standalone CLI driver for the compiler (used for testing).

## Pipeline

1. **Read source**: `sys_open(path, "r")` → `sys_read(fd)` → buffer
2. **Tokenize**: `tokenize(source)` → list of `Token` structs (supports decimal integers and float `.` notation). 47 Nova keywords matched via `switch` statement.
3. **Parse**: `parse(tokens)` → AST (list of `AstNode`). Float literals detected by `.` in number token. Constant folding applied inline for integer arithmetic only. **List comprehensions** (`[expr for x in list if cond]`) and **switch/match** (`switch expr { case val { ... } }`) desugar at parse time — no special AST nodes needed. **Dict literals** (`{"key": val}`) parsed with interleaved key-value pairs in args list. **try/catch/throw** produces `Try` and `Throw` AST nodes.
4. **Resolve imports**: `resolve_imports(ast, visited)` — recursively loads and tokenizes/parses imported `.nv` files
5. **Type check**: `TypeChecker.tc_check(tc, ast)` — static type inference using `stdlib/types.nv` type abstractions. Returns `float` type for float literals.
6. **Generate assembly**: `generate_assembly(ast)` → list of assembly lines via `backend/<arch>/codegen.nv`. Bounds-checking asm injected for array ops. Dict ops emit `_dict_*` C helper calls. Exceptions emit `_try_block`/`_throw_error`/`_catch_error` wrappers.
7. **Write output**: Assembly lines written to `.s` file via `sys_write()` (optional, mainly for debugging)
8. **Assemble + Link**: `assemble()` + `link()` in-process — no GCC or external toolchain needed. The assembler supports all standard x86/ARM64 instructions used by the codegen.

## GCC-Free Assemble-Link Path

The `assemble_link_file(asm_path, output_path)` function reads an `.s` assembly file, splits it into lines, calls `assemble(asm_lines)` to generate raw x86 byte streams, and `link(assembled)` to produce a PE executable — all in-process without any external toolchain. The in-process assembler+linker works for **both** x86_64 and ARM64 (via `backend/arm64/linker.nv`).

`main.py` auto-delegates non-self builds to `nova.exe assemble-link` when `nova.exe` is available, making the pipeline fully GCC-free for all programs compiled with the self-hosted compiler.

## REPL

`nova repl` starts an interactive REPL with:
- Multi-line input (reads until complete parse succeeds)
- Persistent state across lines (variables, functions accumulate in the same scope)
- Calls the full compiler pipeline (tokenize → parse → type check → execute via `vm.nv`)
- Modes: `nova repl` for Nova source execution, `nova repl --vm` for bytecode execution

## Cross-Compilation

The compiler supports targeting different platforms via `target_os` in `CodegenState`:
- `compile_to_exe` dispatches on OS: Windows bundled MinGW, macOS/Linux system GCC, ARM64 Windows internal PE linker
- Output extension: `.exe` on Windows, no extension on Unix
- GCC auto-detection with cross-toolchain lookup (`x86_64-w64-mingw32-gcc` on Windows)

## Modularity

The compiler is split into modular `.nv` files:
- `lexer.nv` — tokenizer (44 Nova keywords matched via `switch`)
- `parser.nv` — recursive-descent parser (includes constant folding, list comprehension desugaring, switch→if-elif desugaring)
- `types.nv` — type system abstraction (scalar, struct, list, func types)
- `type_checker.nv` — static type inference engine
- `codegen.nv`, `codegen_expr.nv`, `codegen_stmt.nv` — Architecture-specific assembly generation in `backend/<arch>/` (x86_64, ARM64). `codegen_expr.nv` and `codegen_stmt.nv` handle expression→asm and statement→asm separately.
- `assembler.nv` (+ submodules) — x86 instruction encoder (integrated via `assemble_link_file`)
- `linker.nv` — PE executable generator (integrated via `assemble_link_file`). ARM64 PE32+ variant at `backend/arm64/linker.nv`
- `errors.nv` — structured error/warning printer with fix suggestions
- `compiler.nv` — pipeline orchestration
- `vm.nv` — Nova bytecode VM written in Nova (stack-based bytecode execution for 20+ opcodes via `exec_func`)
- `os_win.nv` — Windows platform runtime facade
- `os_linux.nv`, `os_macos.nv` — Linux/macOS platform stubs with same API

All compiler improvements can be written purely in Nova, maintaining a self-sustaining ecosystem.
