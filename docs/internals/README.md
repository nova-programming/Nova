# Nova Internals Documentation

This directory contains internal documentation for the Nova compiler, organized by component:

- `tokenizer.md` — Lexical analysis
- `parser.md` — Recursive-descent parsing
- `codegen.md` — Native code generation (x86_64 & ARM64 backends)
- `compiler.md` — Pipeline orchestration
- `linker.md` — PE executable generation
- `os_win.md` — Windows OS runtime facade

All compiler code is written in Nova under `stdlib/`. The Python bootstrap in `bootstrap/` is frozen.