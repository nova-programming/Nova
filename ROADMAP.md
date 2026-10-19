# Nova Roadmap

## Near-Term Goals

### 1. Cross-Platform Abstractions (Implemented)
`system.nv` is the unified OS-layer interface; it imports the pseudo-module `os_impl`, which
`resolve_imports` (`stdlib/compiler.nv`, `bootstrap/modules/resolver.py`) rewrites to
`os_windows` or `os_unix` based on `target_os` before resolving the file — one shared Unix
implementation rather than separate Linux/macOS files, which is simpler than originally
specified and has the same effect: end-user code never sees the platform split.

### 2. Galaxy Package Manager (Implemented)
Galaxy is a fully functional package manager with a Git-backed registry website, standalone CLI (`galaxy`), three trust tiers (Core/Verified/Community), template system (`galaxy init`), GitHub Issues-based publishing workflow, and GitHub Actions automation for validation/quarantine/promotion. See the [Galaxy Registry](https://galaxy-registry.vercel.app) for documentation.

### 3. Small Function Inlining (Implemented)
Implement advanced compiler optimizations to inline extremely short, non-recursive functions, entirely eliminating call/ret overhead for utility methods.

### 4. Language Feature Roadmap (All Ten Shipped — Python Bootstrap + VM)
Ten features were specified with developer-vs-backend contracts, sequenced by blast radius to
protect self-hosting stability; all ten now show **Shipped** in `docs/features.md`: `nova run`,
`defer`, `alloc[T]` typed pointers, `@entry` bare-metal annotations, "Did you mean?" Levenshtein
diagnostics, C FFI `extern def`, zero-copy `{ptr,len}` slices, the `.ptr`/`.as_list` bridge,
multiple returns with `_` discard, and auto-inlining with `@noinline`. The tenth was found
broken in every pipeline (not actually shipped despite the doc previously saying so — see
`docs/features.md` section 7's full history) and has now been fixed for the Python bootstrap
and VM: a parser gap (`-> (T1, T2, ...)` didn't parse), a stray copy-paste bug plus a
fundamentally wrong register-smuggling scheme in the native backend, and zero VM opcode support
at all, replaced in both backends with a side-stash that doesn't fight the callee's own
epilogue/frame-cleanup. The identical register-smuggling bug in the ARM64 Python-bootstrap
backend is also now fixed (same side-stash design), verified by cross-assembling with
`clang --target=arm64-apple-macos11 -c` (no ARM64 hardware/emulator available here to run it).
**Still not implemented in the self-hosted compiler at all** (a new feature there, not a fix —
tracked separately; an attempt surfaced a real, unconfirmed memory-safety bug somewhere in the
self-hosted compiler's own internals — see `docs/AGENT_LOG.md` Phase 38/39 — so it was reverted
rather than shipped untested).

Two further items are open and tracked separately, not part of this nine/ten count: full SSO
(inline ≤15B string buffers) was deferred entirely — it changes the `char*` ABI at every
codegen/VM boundary, so the ABI-preserving subset shipped instead (empty-slice static,
full-slice aliasing in `_str_sub`) — and the macOS ARM64 **self-hosted** bootstrap still crashes
during codegen (Python-bootstrap builds on macOS ARM64 work fine); see
`docs/internals/macos_arm64_bootstrap.md`.

## Current Engineering Priorities

The next work is correctness-first rather than another large syntax batch:

1. Maintain VM/native semantic parity with differential tests.
2. ~~Define ownership and lifetime rules for `alloc`, `free`, raw pointers, `.ptr`,
   `.as_list`, and `@raw` before expanding unsafe APIs.~~ Done — see
   `docs/internals/ownership.md`. It documents the current contract (two parallel memory
   systems, ARC-managed vs. manual, and exactly where `.ptr`/`.as_list` cross between them)
   rather than proposing new runtime behavior. The one concrete gap it originally surfaced
   and left open — `.as_list()`'s wrapper having no ARC header, so passing its result
   anywhere that generically retains/releases a value was a heap-buffer-underflow read —
   is now fixed: `_list_wrap`/`_as_list` (`runtime.c`) allocates through `_nova_arc_alloc`
   with a new "borrowed" flag (the header's otherwise-unused `pad` field) so releasing the
   wrapper frees only the 16-byte header, never the caller's buffer. Fixing it surfaced two
   more real, independent bugs in the x86_64 Python-bootstrap backend while verifying the
   round-trip actually worked (`bootstrap/compiler/backend/x86_64/codegen.py`): `.ptr` on a
   list went through a generic struct-field-offset fallback that silently defaulted to
   offset 0 (a list's own element count) instead of offset 8 (the data pointer), since no
   user struct defines a field literally named "ptr"; and `.as_list()`'s inline codegen
   popped the instance pointer into `rax`, then immediately clobbered it with `_malloc`'s
   own return value before it was ever stored, leaving every wrapped list pointing at
   itself with count hardcoded to 0. Both fixed; the ARM64 Python-bootstrap backend had the
   identical bugs and got the identical fixes, verified by cross-assembling with
   `clang --target=arm64-apple-macos11 -c` (no ARM64 hardware/emulator available here to
   run it). See `tests/test_native_exec.py::test_ptr_and_as_list_round_trip`.
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
- Also: `\{` / `\}` write literal braces in strings (inline JSON), and the self-hosted incremental build cache now keys on source content plus the compiler's identity (and is skipped when a local module is imported).
- **Native floats now work end-to-end in both pipelines** (literals, printing, `+ - * /`, all six comparisons, `-> float` returns), fixed this session, with a stage-2 self-host round-trip confirming the fixed point still holds:
  - Python-bootstrap x86_64 (`bootstrap/compiler/backend/x86_64/codegen.py`): arithmetic/compare used double-precision `sd`/`comisd` instructions on values that are 32-bit single-precision bit patterns (only the low 4 bytes were ever meaningful — `movsd`/`addsd`/`comisd` read 8 bytes of garbage); and `Compare` loaded its operands reversed (`xmm0 <- right`, `xmm1 <- left`), so every `<`/`>`/`<=`/`>=` tested the wrong direction. Fixed to `ss`/`comiss` with `xmm0 <- left, xmm1 <- right`. Separately, `.value_byte` emitted `mov al, byte [rdx]` — missing the `ptr` size-override keyword, which GAS's Intel-syntax parser accepts without erroring but always reads as `0`. This was the actual cause of "the self-hosted compiler turns float literals into 0": `float_str_to_hex()` (in the self-hosted backend, but running as nova.exe's own *bootstrap-compiled* code) parses each digit via `s[i].value_byte`, so every digit silently read `0`. Fixed to `byte ptr [rdx]`.
  - Self-hosted x86_64 (`stdlib/backend/x86_64/codegen_expr.nv`): `Compare`'s float branch had the same dead-double/x87 bug (`fld qword ptr [esp]`) *and* a separate, pre-existing structural bug — the block with the actual comparison logic was nested inside the `else` of its own `is_float_op == 1` check, so for floats it never ran at all: both operands were pushed and nothing ever compared them, leaving whichever was last on the stack to stand in for the boolean (this is why `a > b`, `a <= a`, `a == a` happened to look right by coincidence while `a < b`, `b >= a` didn't). Restructured into one correctly-nested `if is_float_op == 1 { comiss+setcc } else { existing int/string path }`. Variable/call float-ness is tracked locally in `CodegenState.float_var_map`/`func_ret_map` (same pattern as `string_var_map`).
  - Unary `-` on a float applied `neg rax` (two's-complement integer negation) to the bit pattern instead of flipping the sign bit, in both bootstrap and both of the self-hosted backend's duplicated `UnaryOp` handlers — `-1.5` printed as `-3.0`-ish garbage, not `-1.5`. Fixed to `xor eax, 2147483648` for float operands in all x86_64 sites. **The ARM64 backend (`bootstrap/compiler/backend/arm64/codegen.py`) has the identical bug and is not fixed** — no ARM64 hardware/emulator is available in this environment to verify a fix.
  - Verified: fresh bootstrap build, fresh self-hosted (stage-1) build, and a stage-2 build (nova.exe rebuilding itself) all give identical, correct results for literals/arithmetic/compare/unary-minus/`-> float`. See `tests/test_float_print.py`, `tests/test_float_vm_native_parity.py`, and `tests/test_stage2.py::test_stage2_float_arithmetic_and_compare`.
- Self-host fixed point: the compiler built by itself now emits byte-identical assembly to the Python-built one for `nova.nv` (the type checker did not visit `str(...)` operands, so `node.line` picked the wrong struct's field offset).

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
