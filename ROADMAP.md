# Nova Roadmap

## Near-Term Goals

### 1. Cross-Platform Abstractions (`os_*.nv`)
Develop a unified OS-layer interface (`system.nv`) that automatically swaps out implementations based on whether the host is Windows (`os_win.nv`), Linux (`os_linux.nv`), or macOS (`os_mac.nv`), completely hiding specific configs from end-users.

### 2. Galaxy Package Manager (Implemented)
Galaxy is a fully functional package manager with a Git-backed registry website, standalone CLI (`galaxy`), three trust tiers (Core/Verified/Community), template system (`galaxy init`), GitHub Issues-based publishing workflow, and GitHub Actions automation for validation/quarantine/promotion. See the [Galaxy Registry](https://galaxy-registry.vercel.app) for documentation.

### 3. Small Function Inlining (Phase 4)
Implement advanced compiler optimizations to inline extremely short, non-recursive functions, entirely eliminating call/ret overhead for utility methods.

## Completed Milestones

### Frame Pointer Optimization (June 2026)
x86_64 now uses `rsp`-relative offsets (`state.bp="rsp"`), ARM64 uses `sp`-relative (`state.bp="sp"`). No `push rbp; mov rbp, rsp` in x86_64 prologue, no `mov fp, sp` in ARM64. Saves 1-2 instructions per function call, frees RBP/FP as GP register. Verified by all 229 tests.

### HashMap/Dict Native Codegen (June 2026)
All 4 backends (x86_64 .nv, ARM64 .nv, x86_64 Python, ARM64 Python) emit proper `_dict_new`/`_dict_set`/`_dict_get`/`_dict_has`/`_dict_remove`/`_dict_keys`/`_dict_values`/`_dict_items` native calls. Dict construction `{"key": val}` and all 7 dict methods work natively. No more placeholder — complete.

### Self-Hosted VM (June 2026)
`stdlib/vm.nv` implements a full Nova bytecode VM written in Nova. Supports 20+ opcodes (LOAD_CONST, LOAD_NAME, STORE_NAME, ADD, SUB, MUL, DIV, CMP, JMP, CJMP, CALL, RETURN, PRINT, LOAD_STR, LOAD_BOOL, OP_TRY, OP_THROW, OP_CATCHEND, NEW_LIST, LIST_APPEND, DICT_SET, DICT_GET). `nova dev` now uses the Nova-in-Nova VM via `nova.exe dev <file.nv>` or `nova repl`.

### Exceptions (try/catch/throw) (June 2026)
Full implementation: lexer keywords (try, catch, throw), parser AST nodes (Try, Throw with catch_body/catch_var_name), VM opcodes (OP_TRY, OP_THROW, OP_CATCHEND), native runtime using setjmp/longjmp in runtime.c. 10 tests all passing.

### List Comprehensions (June 2026)
`[expr for x in list if cond]` syntax desugars to Block + ForIn + append at parse time. No AST/codegen changes needed. 7 tests.

### Switch/match (June 2026)
`switch expr { case val { body } else { body } }` syntax desugars at parse time to if-elif-else chain. Both Python parser and self-hosted parser implement it.

### REPL (June 2026)
`nova repl` command with multi-line input, persistent state across lines. Integration with both VM and native modes.

### Cross-Compilation Infrastructure (June 2026)
`target_os` field through CodegenState, platform-aware GCC command generation, OS-appropriate output extension (.exe on Windows). os_linux.nv and os_macos.nv platform stubs filled in.

### type() and call() Built-ins (June 2026)
`type(val)` returns type name string at compile time (native) or runtime (VM). `call(name, args)` for dynamic function dispatch (VM). 17 tests.

### 64-bit x86_64 Support (June 2026)
The codegen has been fully ported to x86_64 with:
- 64-bit registers (`rax`/`rbx`/`rcx`/`rdi`/`rsi`/`rdx`/`r8`/`r9`)
- System V AMD64 calling convention (args in `rdi`/`rsi`/`rdx`/`rcx`/`r8`/`r9`, as used by MinGW GCC)
- 16-byte stack alignment for external calls
- Self-hosting verified end-to-end — `nova.exe build nova.nv` produces a working 64-bit compiler
