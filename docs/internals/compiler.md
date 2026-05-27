# Nova Native Compiler Internals (`stdlib/compiler.nv` & `nova_main.nv`)

The compilation pipeline orchestrates tokenizer → parser → codegen → GCC linking.

## Entry Points

- **`nova_main.nv`**: CLI entry point for the self-hosted native compiler. Parses `build` command, reads the `.nv` source, calls `compile_to_file()`, then invokes `gcc` via `sys_system()`.
- **`stdlib/compiler.nv`**: Core library exposing `compile_file(path)` and `compile_to_file(input, output)`. Orchestrates: read file → tokenize → parse → resolve imports → generate assembly.
- **`stdlib/compiler_driver.nv`**: Minimal standalone CLI driver for the compiler (used for testing).

## Pipeline

1. **Read source**: `sys_open(path, "r")` → `sys_read(fd)` → buffer
2. **Tokenize**: `tokenize(source)` → list of `Token` structs
3. **Parse**: `parse(tokens)` → AST (list of `AstNode`)
4. **Resolve imports**: `resolve_imports(ast, visited)` — recursively loads and tokenizes/parses imported `.nv` files
5. **Generate assembly**: `generate_assembly(ast)` → list of assembly lines
6. **Write output**: Assembly lines written to `.s` file via `sys_write()`
7. **Link**: `sys_system("gcc " + out_file + " -o " + exe_file)` produces native `.exe`

## Modularity

The compiler is split into modular `.nv` files:
- `lexer.nv` — tokenizer
- `parser.nv` — recursive-descent parser
- `codegen.nv`, `codegen_expr.nv`, `codegen_stmt.nv` — x86-32 assembly generation
- `assembler.nv` (+ submodules) — x86 instruction encoder (not yet in default path)
- `linker.nv` — PE executable generator (not yet in default path)
- `compiler.nv` — pipeline orchestration
- `os_win.nv` — platform runtime facade

All compiler improvements can be written purely in Nova, maintaining a self-sustaining ecosystem.
