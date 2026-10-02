# Nova Roadmap

## Near-Term Goals

### 1. Cross-Platform Abstractions (`os_*.nv`)
Develop a unified OS-layer interface (`system.nv`) that automatically swaps out implementations based on whether the host is Windows (`os_win.nv`), Linux (`os_linux.nv`), or macOS (`os_mac.nv`), completely hiding specific configs from end-users.

### 2. Galaxy Package Manager (Implemented)
Galaxy is a fully functional package manager with a Git-backed registry website, standalone CLI (`galaxy`), three trust tiers (Core/Verified/Community), template system (`galaxy init`), GitHub Issues-based publishing workflow, and GitHub Actions automation for validation/quarantine/promotion. See the [Galaxy Registry](https://galaxy-registry.vercel.app) for documentation.

### 3. Small Function Inlining (Implemented)
Implement advanced compiler optimizations to inline extremely short, non-recursive functions, entirely eliminating call/ret overhead for utility methods.

### 4. Language Feature Roadmap (Specified — Sequenced Delivery)
Ten features specified with developer-vs-backend contracts. Delivered first: `nova run` (instant execution). The remainder are sequenced by blast radius to protect self-hosting stability:
- **Next:** `@entry` annotations (bare-metal), `defer` (LIFO scope cleanup), `alloc[T]` typed pointers.
- **Later (ABI changes):** C FFI `extern def`, zero-copy `{ptr,len}` slices, `.ptr`/`.as_list` bridge, multiple returns with `_` discard, auto-inlining with `@noinline`.
- **Tooling:** "Did you mean?" Levenshtein diagnostics, macOS ARM64 bootstrap, POSIX layer completion.
- Full SSO (inline ≤15B string buffers) deferred: it changes the `char*` ABI at every codegen/VM boundary; shipped instead the ABI-preserving subset (empty-slice static, full-slice aliasing in `_str_sub`).
- See `docs/features.md` for the full specification and status of each item.

## Current Engineering Priorities

The next work is correctness-first rather than another large syntax batch:

1. Maintain VM/native semantic parity with differential tests.
2. Define ownership and lifetime rules for `alloc`, `free`, raw pointers, `.ptr`,
   `.as_list`, and `@raw` before expanding unsafe APIs.
3. Keep VM-only features such as `call()` explicit and rejected by native builds.
4. Add `nova check`, formatting, structured diagnostics, and reproducible
   dependency/build metadata. `nova fmt` is deterministic and opt-in;
   `nova check --json` and `nova lint --json` expose stable diagnostic codes.
5. Expand portable filesystem, path, JSON, and subprocess libraries.

The native test suite now includes a VM/native output comparison for control
flow and collection operations. This is a seed suite, not a proof of complete
parity; new language features should add cases to it.

### Tooling control policy

`nova fmt` only edits files with the explicit `--write` flag. `nova lint` is
advisory unless `--strict` is selected. JSON diagnostics are one object per
line and never alter build behavior, source files, or dependencies.

## Completed Milestones

### Simpler Syntax and a Consistent API (Oct 2026)
- Dotted module calls (`fs.read`, `path.join`, `text.trim`, `json.parse`), camelCase members, and soft keywords (`read`, `write`, `close`, `api`, `openf`, `data` work as ordinary names). Old flat names stay valid; `nova lint` flags them (`STYLE003`) and `nova fmt --write --modernize` migrates.
- `for i in range(...)`, data constructors `Point(1, 2)` / `Point(x=1, y=2)`, `key in d` / `key not in d`, `stdlib/text.nv`, `json.parse` (typed tree), and `-> string` inference for un-annotated functions.
- Self-hosted backend: lightweight Nova-to-Nova calls, a safe peephole optimizer, and compare-and-branch fusion (fib(38) about 1.8x of `gcc -O2`).
- Fixes found on the way: stale build caches, native `downto` loops, a parser rewrite that broke the self-built compiler, and `len(x[i])` miscompiled as strlen (every struct looked two fields wide in a self-built compiler). The test suite now builds and exercises a stage-2 compiler (built by the self-hosted compiler) to catch this class of bug.
- Known gaps: float return types are not inferred (native float returns need work), `Point(...)` shorthand needs the `data` declaration earlier in the same file, the self-hosted driver's incremental build cache keys on file size only.

### Instant Execution — `nova run` (Oct 2026)
`nova run <file.nv> [args...]` compiles, links, and immediately executes in one command (args forwarded to the program). Implemented as a CLI-level composition of `compile_to_exe` + `system_exec` in `nova.nv`; no codegen changes, works identically in Python and self-hosted compilers. Validated end-to-end including argument forwarding.

### Loop Bounds-Check Elimination (Oct 2026)
Self-hosted x86_64 backend detects canonical `for i = 0 to len(L)-1 { ... L[i] = ... }` loops and elides the upper-bound `cmp`+`jge` branch (lower check retained). Guarded by a conservative purity walker (unknown node kinds default to keeping checks; any non-`len` call, method call, `free`, `RawBlock`, or reassignment blocks elimination; innermost loop binding wins for shadowing). Verified in emitted assembly (−2 instructions per store) with correct outputs, plus negative tests proving checks are kept when the body mutates.

### Parse-Time Constant Folding & Dead-Code Pruning (Oct 2026)
Self-hosted parser folds `"a"+"b"` string literals and `true and x` / `false or x` boolean logic, and prunes `if false` / `if true` / `elif` dead branches (multi-statement branches become `Block` nodes, empty branches become `NONE`). `Block` statement support added to both native backends and the type checker. All folding is semantics-preserving; validated via self-hosted builds with correct outputs.

### Native List-Write Correctness Fix (Oct 2026)
Fixed a critical pre-existing bug: the bounds check in list index assignment clobbered the value register (`mov eax,[rbx]` overwrote the value in `rax`, and the `_oob_line` setup clobbered it earlier), so every `lst[i] = x` stored garbage. Fixed with save/restore in the Python bootstrap backend. The self-hosted backend already used the correct non-clobbering form.

### Self-Hosted `for` Loop Fix (Oct 2026)
Fixed a pre-existing self-hosted codegen bug where `ForLoop` reused a possibly-unbound `offset` variable when the loop variable was register-allocated, emitting garbage displacements (e.g. `[rbp-140696080088216]`). Bound-load and step sections now use the register directly or a freshly resolved offset.

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
`target_os` field through CodegenState, platform-aware GCC command generation, OS-appropriate output extension (.exe on Windows). os_linux.nv and os_macos.nv provide the common facade, with narrower platform coverage than Windows.

### type() and call() Built-ins (June 2026)
`type(val)` returns type name string at compile time (native) or runtime (VM). `call(name, args)` for dynamic function dispatch (VM). 17 tests.

### 64-bit x86_64 Support (June 2026)
The codegen has been fully ported to x86_64 with:
- 64-bit registers (`rax`/`rbx`/`rcx`/`rdi`/`rsi`/`rdx`/`r8`/`r9`)
- System V AMD64 calling convention (args in `rdi`/`rsi`/`rdx`/`rcx`/`r8`/`r9`, as used by MinGW GCC)
- 16-byte stack alignment for external calls
- Self-hosting verified end-to-end — `nova.exe build nova.nv` produces a working 64-bit compiler
