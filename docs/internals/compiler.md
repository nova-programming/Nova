# Nova Native Compiler Internals (`stdlib/compiler.nv` & `nova_main.nv`)

The compilation pipeline orchestrates tokenizer → parser → codegen → GCC linking.

## Entry Points

- **`nova_main.nv`**: CLI entry point for the self-hosted native compiler. Parses `build` command (reads `.nv` → `compile_to_exe()` → GCC) or `assemble-link` command (reads `.s` → `assemble_link_file()` → in-process PE generation).
- **`stdlib/compiler.nv`**: Core library exposing `compile_file(path)`, `compile_to_file(input, output)`, `compile_to_exe(input, output, debug_mode)`, and `assemble_link_file(asm_path, output_path)`. Orchestrates full pipeline: read file → tokenize → parse → resolve imports → type check → generate assembly.
- **`stdlib/compiler_driver.nv`**: Minimal standalone CLI driver for the compiler (used for testing).

## Pipeline

1. **Read source**: `sys_open(path, "r")` → `sys_read(fd)` → buffer
2. **Tokenize**: `tokenize(source)` → list of `Token` structs
3. **Parse**: `parse(tokens)` → AST (list of `AstNode`). Constant folding applied inline during expression parsing.
4. **Resolve imports**: `resolve_imports(ast, visited)` — recursively loads and tokenizes/parses imported `.nv` files
5. **Type check**: `TypeChecker.tc_check(tc, ast)` — static type inference using `stdlib/types.nv` type abstractions
6. **Generate assembly**: `generate_assembly(ast)` → list of assembly lines. Bounds-checking asm injected for array ops.
7. **Write output**: Assembly lines written to `.s` file via `sys_write()`
8. **Link**: `sys_system("gcc " + out_file + " -o " + exe_file)` produces native `.exe` (build path), OR `assemble()` + `link()` in-process (assemble-link path).

## GCC-Free Assemble-Link Path

The `assemble_link_file(asm_path, output_path)` function (added in Milestone G) reads an `.s` assembly file, splits it into lines, calls `assemble(asm_lines)` to generate raw x86 byte streams, and `link(assembled)` to produce a PE executable — all in-process without any external toolchain.

`main.py` auto-delegates non-self builds to `nova_main.exe assemble-link` when `nova_main.exe` is available, making the pipeline GCC-free for all programs except `nova_main.exe` itself.

## Modularity

The compiler is split into modular `.nv` files:
- `lexer.nv` — tokenizer
- `parser.nv` — recursive-descent parser (includes constant folding)
- `types.nv` — type system abstraction (scalar, struct, list, func types)
- `type_checker.nv` — static type inference engine
- `codegen.nv`, `codegen_expr.nv`, `codegen_stmt.nv` — x86-32 assembly generation (includes bounds checking)
- `assembler.nv` (+ submodules) — x86 instruction encoder (integrated via `assemble_link_file`)
- `linker.nv` — PE executable generator (integrated via `assemble_link_file`)
- `compiler.nv` — pipeline orchestration
- `os_win.nv` — platform runtime facade

All compiler improvements can be written purely in Nova, maintaining a self-sustaining ecosystem.
