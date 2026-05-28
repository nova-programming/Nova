# Nova Native Compiler Internals (`stdlib/compiler.nv` & `nova_main.nv`)

The compilation pipeline orchestrates tokenizer → parser → codegen → GCC linking.

## Entry Points

- **`nova_main.nv`**: CLI entry point for the self-hosted native compiler. Parses `build` command, reads the `.nv` source, calls `compile_to_file()`, then invokes `gcc` via `sys_system()`.
- **`stdlib/compiler.nv`**: Core library exposing `compile_file(path)` and `compile_to_file(input, output)`. Orchestrates: read file → tokenize → parse → resolve imports → generate assembly.
- **`stdlib/compiler_driver.nv`**: Minimal standalone CLI driver for the compiler (used for testing).

## Pipeline

1. **Read source**: `sys_open(path, "r")` → `sys_read(fd)` → buffer
2. **Tokenize**: `tokenize(source)` → list of `Token` structs
3. **Parse**: `parse(tokens)` → AST (list of `AstNode`). Constant folding applied inline during expression parsing.
4. **Resolve imports**: `resolve_imports(ast, visited)` — recursively loads and tokenizes/parses imported `.nv` files
5. **Type check**: `TypeChecker.tc_check(tc, ast)` — static type inference using `stdlib/types.nv` type abstractions
6. **Generate assembly**: `generate_assembly(ast)` → list of assembly lines. Bounds-checking asm injected for array ops.
7. **Write output**: Assembly lines written to `.s` file via `sys_write()`
8. **Link**: `sys_system("gcc " + out_file + " -o " + exe_file)` produces native `.exe`

## Modularity

The compiler is split into modular `.nv` files:
- `lexer.nv` — tokenizer
- `parser.nv` — recursive-descent parser (includes constant folding)
- `types.nv` — type system abstraction (scalar, struct, list, func types)
- `type_checker.nv` — static type inference engine
- `codegen.nv`, `codegen_expr.nv`, `codegen_stmt.nv` — x86-32 assembly generation (includes bounds checking)
- `assembler.nv` (+ submodules) — x86 instruction encoder (not yet in default path)
- `linker.nv` — PE executable generator (not yet in default path)
- `compiler.nv` — pipeline orchestration
- `os_win.nv` — platform runtime facade

All compiler improvements can be written purely in Nova, maintaining a self-sustaining ecosystem.
