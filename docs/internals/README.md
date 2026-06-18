# Nova Internals Documentation

This directory contains internal documentation for the Nova compiler, organized by component:

- `tokenizer.md` — Lexical analysis (47 keywords, switch-based dispatch)
- `parser.md` — Recursive-descent parsing (list comprehension and switch desugaring, try/catch/throw AST, dict literals)
- `codegen.md` — Native code generation (x86_64 & ARM64 backends, frame pointer optimization, exceptions, cross-compilation)
- `compiler.md` — Pipeline orchestration (REPL, VM self-hosting, cross-compilation)
- `linker.md` — PE executable generation (x86_64 PE32+, ARM64 PE32+)
- `os_win.md` — Windows OS runtime facade (cross-platform stubs for Linux/macOS)

All compiler code is written in Nova under `stdlib/`. The Python bootstrap in `bootstrap/` is frozen.