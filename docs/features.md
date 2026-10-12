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

## 7. Multiple Returns + `_` Discard — Broken, Not Shipped (Correcting an Earlier Status Here)

The example this section used to show does not work in any pipeline, found while using it as
a reference for an unrelated feature (`process_capture`, see `stdlib/process.nv`) and
confirming every claim here against the actual code rather than taking "Shipped" on faith:

- `def get_user() -> (string, int, bool) { ... }` — the `->` return-type annotation does not
  accept a parenthesized type list at all (`bootstrap/parser/parser.py`'s `parse_function`
  calls `parse_type_annotation()`, which parses one type, not a tuple); this is a parse error
  (`Expected LBRACE, got LPAREN`) in every pipeline.
- Dropping the return-type annotation (`def get_user() { return "Alice", 30, true }` with
  `name, age, _ = get_user()`) parses, but:
  - **VM** (`nova dev`): `bootstrap/vm/machine.py` has no handling at all for `MultiReturn` or
    `UnpackAssign` — the unpacked names resolve as unknown identifiers and silently read as
    `0`/empty, with only a resolver warning, no error.
  - **Python-bootstrap native** (`nova build`): `bootstrap/compiler/backend/x86_64/codegen.py`'s
    `compile_stmt` crashes outright — `AttributeError: 'UnpackAssign' object has no attribute
    'catch_body'` — so the feature was never reachable here either.
- Not fixed this session; this needs a real pass across both bootstrap backends plus the VM,
  not a touch-up. Tracked in `ROADMAP.md`. Until then, functions needing to return more than
  one value should use a `data` struct or encode multiple values into one return (as
  `process_capture` does) instead of `MultiReturn`/`UnpackAssign`.

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
