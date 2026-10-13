# Nova Language Features — Specification & Status

This document records the developer-facing contract ("dead simple") and the
hidden backend complexity for ten language features, plus the delivery status
of each. The guiding rule: anything that changes value representation or the
calling ABI ships only after isolated design, implementation, and a full
self-hosting validation cycle (Stage 1 → Stage 2 → test suite).

Status legend: **Shipped** (implemented + validated) / **Sequenced** (specified,
scheduled in risk order) / **Subset** (safe portion shipped, rest sequenced).

## 1. Deferred Cleanup — `defer` — Shipped

Developer experience (dead simple):

```nova
# Single line:
defer sys_close(f)
# Or block form (no nested try/finally pyramids!):
defer {
    free(buf)
    sys_close(f)
    print("Cleaned up!")
}
```

Complexity hidden in backend: the backend maintains a lexical scope stack.
On every return, break, or scope closing `}`, it injects the deferred
assembly in reverse (LIFO) order. The developer never thinks about cleanup
order or multiple exit paths again.

Delivery: implemented in both Python bootstrap (x86_64 + ARM64) and
self-hosted Nova compiler. New `DEFER` keyword, `Defer` AST node, per-scope
`deferred_stack` in codegen, injection at function epilogue and return points.

## 2. Diagnostics — "Did You Mean?" — Shipped

Developer experience (dead simple): zero extra syntax. Mistakes are explained:

```text
error: unknown field 'lenght' on list[int]
  --> main.nv:12:15
     |
  12 |   print(numbers.lenght)
     |                 ^^^^^^ did you mean 'len'?
```

Complexity hidden in backend: tokenizer stores column spans; the compiler
runs a fast Levenshtein check over keywords, variables, and struct fields.

Delivery: `levenshtein_distance()` and `did_you_mean()` helpers added to the
type checker. `visit_Variable` and `visit_DataFieldAccess` emit warnings with
suggestions when unknown identifiers/fields are encountered.

## 3. Direct C FFI — `extern def` — Shipped

Developer experience (dead simple):

```nova
extern def puts(s: string) -> int
extern def sqlite3_open(path: string, db: *void) -> int
puts("Hello from C!")
```

Complexity hidden in backend: string arguments unwrap to null-terminated
pointers automatically; arguments are placed per the host C ABI (SysV
rdi/rsi/rdx vs. Windows x64 rcx/rdx/r8/r9).

Delivery: `EXTERN` keyword, `ExternDef` AST node, parser support for
`extern def` declarations, `.extern` emission in codegen. Existing FFI
infrastructure (`LoadLib`, `CallLib`) handles dynamic library loading.

## 4. Zero-Copy Slicing — Shipped (Subset)

Developer experience (dead simple): `sub = data[10:50]` works identically
for lists, strings, and raw buffers; `print(sub[0])` just works.

Complexity hidden in backend (as specified): compile slices to 16-byte
`{ ptr, len }` values with zero heap allocation.

Delivery: ABI-preserving subset shipped in `_str_sub` (`runtime.c`): empty
slices return a shared static `""` (no malloc); full-range slices alias the
input pointer (no copy). String buffers are never freed or written in place
by generated code, so both shortcuts are sound. Full `{ptr,len}` views
remain sequenced behind a representation RFC.

## 5. High-to-Low Bridge — `.ptr` & `.as_list` — Shipped

Developer experience (dead simple):

```nova
lst = [1, 2, 3]
raw_ptr = lst.ptr
my_list = raw_ptr.as_list(count=100)
```

Complexity hidden in backend: `.ptr` returns the interior buffer address;
`.as_list(n)` builds a lightweight header over foreign memory — no copying.

Delivery: `.ptr` added to pointer properties in parser and codegen.
`.as_list(count=n)` method call support added to MethodCall handler in both
x86_64 and ARM64 backends. Keyword argument parsing for method calls.

## 6. Typed Pointers — `alloc[T]` — Shipped

Developer experience (dead simple): `p = alloc[int](10)` allocates space for
10 integers; `p[i]` scales by `sizeof(T)` automatically.

Complexity hidden in backend: generic call syntax, `sizeof(T)` computed at
compile time, scaled indexing (`[rax + rcx*8]`).

Delivery: `alloc[T](count)` syntax parsed with type parameter support.
`_sizeof_type()` helper computes element size at compile time. `Alloc`
handler multiplies count by sizeof(T) before calling malloc. Both x86_64
and ARM64 backends updated.

## 7. Multiple Returns + `_` Discard — Shipped (Python Bootstrap + VM Only)

```nova
def get_user() -> (string, int, bool) {
    return "Alice", 30, true
}
name, age, ok = get_user()
```

This section previously claimed "Shipped" when the documented example didn't work in any
pipeline (found, and now fixed, while using it as a reference for an unrelated feature,
`process_capture` — see `stdlib/process.nv`). Fixed this time by actually confirming each
claim against the code rather than taking the status label on faith:

- **Parser**: the `->` return-type annotation didn't accept a parenthesized type list at all.
  `parse_function` now special-cases `-> (T1, T2, ...)`, storing it as the string
  `"(T1,T2,...)"` (nothing currently parses that back apart for anything beyond the one
  per-position check described below — a multi-return function's `return_type` just doesn't
  match any single type, which is the correct behavior for it).
- **VM** (`nova dev`): `bootstrap/vm/machine.py`/`compiler.py` had zero opcode handling for
  `MultiReturn`/`UnpackAssign` — unpacked names silently read as unknown/`0`. `RETURN`'s frame
  cleanup collapses the operand stack down to exactly one value (by design, to protect callers
  from leftover statement-level-call operands), so pushing multiple return values on the main
  stack doesn't survive it. Fixed with a side stash instead: three new opcodes
  (`CLEAR_RETURN_STASH`/`STASH_RETURN`/`UNSTASH_RETURN`) carry `values[1:]` across the call
  boundary while `values[0]` stays the normal single return value. `TypeInferer` also had no
  `visit_UnpackAssign`/`visit_MultiReturn`, which produced spurious "unknown identifier"
  warnings on otherwise-working code; fixed by registering each target as `AnyType`.
- **Python-bootstrap native** (`nova build`): `codegen.py`'s `UnpackAssign` case had a stray
  copy-paste tail from the `Try`/`Catch` handler right above it (`for stmt in node.catch_body:
  ...`, referencing an attribute `UnpackAssign` doesn't have) — a straight `AttributeError`
  crash. Underneath that, the actual logic was wrong regardless: it assumed `rbx`/`rcx`/`rdx`
  still held the callee's 2nd/3rd return values after the call returned, but the callee's own
  epilogue (`for reg in reversed(self.used_regs): pop reg`) restores the *caller's* values into
  those same registers before `ret` — so even without the crash, this would have read back
  garbage. Fixed the same way as the VM: `values[0]` stays in `rax` (the ABI-compatible single
  return value, unchanged), `values[1:]` go through a small static buffer
  (`_nova_multi_ret`, 8 `.quad` slots) that `UnpackAssign` reads from immediately after the
  call. Also added a `scan_vars` case for `UnpackAssign` (targets weren't getting registered
  as locals at all, so they'd silently get no stack slot) and `string_vars` tracking driven by
  the callee's parsed `(T1,T2,...)` return-type string (without it, `print()` on a `string`
  target picked the `%d` format and showed the raw pointer as a huge integer).
- **Self-hosted compiler**: never implemented at all — no `MultiReturn`/`UnpackAssign` support
  anywhere in `stdlib/parser.nv` or the self-hosted codegen. Not part of this fix; this would
  be adding a new feature to the self-hosted parser/codegen (`AGENTS.md`'s "language features
  go into `stdlib`"), not fixing an existing one, and is tracked separately.
- **ARM64 Python-bootstrap** (`bootstrap/compiler/backend/arm64/codegen.py`): has the identical
  register-smuggling bug as the x86_64 native backend did (`x1`/`x2`/`x3` assumed to survive
  the callee's epilogue). Not fixed — no ARM64 hardware or emulator is available in this
  environment to verify a fix, same reasoning as the ARM64 float-negation gap noted elsewhere
  in this doc's history.
- Verified: VM and Python-bootstrap native agree on the exact documented example plus a `_`
  discard case. See `tests/test_native_exec.py::test_vm_native_parity_for_multi_return` and
  `::test_vm_native_parity_for_multi_return_discard`.

## 8. Auto-Inlining — Shipped

Developer experience (dead simple): short functions (e.g. `min`) are inlined
automatically (AST size ≤ 8, non-recursive); `@noinline` opts out.

Complexity hidden in backend: AST cloning with parameter substitution and
return rewriting at call sites.

Delivery: `_is_inline_candidate()` and `_count_nodes()` helpers in codegen.
Functions with ≤8 AST nodes marked as inline candidates. `@noinline`
annotation parsed and respected. Both x86_64 and ARM64 backends updated.

## 9. Bare-Metal `@entry` — Shipped

Developer experience (dead simple):

```nova
@entry
def _start() {
    @raw {
        "mov rax, 0x10"
    }
}
```

```bash
nova build --bare kernel.nv
```

Complexity hidden in backend: skip runtime init, no `runtime.c` link, flat
binary with entry aligned at origin.

Delivery: `@entry` annotation parsed following existing `@raw`/`@export`
patterns. `is_entry` flag on Function node. Entry point wired through
`self.entry_func` in codegen generate method. Both x86_64 and ARM64
backends updated.

## 10. Instant Execution — `nova run` — Shipped

Developer experience (dead simple):

```bash
nova run main.nv
nova run main.nv arg1 arg2
```

Just like `python main.py` or `go run`. No compile → link → run mental load.

Complexity hidden in backend: the driver compiles and links to the standard
output path, then launches the process immediately via `system_exec`, so the
feedback loop drops to a single command. (Implemented as build-then-execute
through the existing pipeline rather than in-memory codegen — same UX, far
less risk.) Program arguments after the filename are forwarded; `-d`/`-b`/
`-arch`/`--os` flags behave as in `build`.

Validation: built into `nova.nv`, exercised end-to-end through the
self-hosted compiler including argument forwarding (`args[1] == "foo"`).

## Shipped in the Same Batch (Prerequisites & Hardening)

- **Loop bounds-check elimination** (x86_64): canonical
  `for i = 0 to len(L)-1 { ... L[i] = ... }` loops skip the upper-bound
  branch; conservative purity walker (unknown constructs keep checks).
- **Constant folding**: `"a"+"b"`, `true and x`/`false or x` families;
  dead `if false`/`if true`/`elif` pruning with `Block`/`NONE` nodes.
- **`_str_sub` allocation elision** (all platforms): empty → shared static,
  full-range → alias.
- **Correctness fixes**: native list-write register clobber (Python backend);
  self-hosted `ForLoop` register-variable offsets; `RawBlock` export field;
  `Type.params`/`Type.ret` typed accessors; struct-field `Pass 1.5` layout;
  `EnvFrame` dict-method access.
- **Diagnostics**: staged `[1/5]`–`[5/5]` compiler progress markers.

## Website

The public site (galaxy-registry) lives in a separate repository and is not
updated by this change. Follow-up there: add `nova run` to the command
reference, and publish this roadmap (shipped vs. sequenced status per
feature) on the documentation pages.
