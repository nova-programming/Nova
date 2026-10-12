# Ownership & Lifetime Rules — `alloc`/`free`, Raw Pointers, `.ptr`, `.as_list`, `@raw`

Nova runs **two parallel, non-interoperating memory systems** side by side. Every unsafe-API
rule below exists to keep programs on one side of that boundary, or to cross it deliberately
and correctly. This doc is the ownership contract `ROADMAP.md` asks for before expanding the
unsafe surface further; it describes what the compiler and runtime actually do today
(`stdlib/backend/x86_64/codegen_expr.nv`, `runtime.c`), not an aspirational design.

## The two systems

**ARC-managed** (`list`, `dict`, `string` literals and values): every `[1, 2, 3]`, `{}`, or
string value is allocated via `_nova_arc_alloc(size, type_tag)`, which prepends a 16-byte
`NovaARCHeader` (`magic`, `ref_count`, `type_tag`, `pad`) before the pointer the program
actually holds. `_nova_value_retain`/`_nova_value_release` walk backward from that pointer
(`((NovaARCHeader*)ptr) - 1`) to find the header, bump/drop `ref_count`, and free the block
automatically when it hits zero. **You never call `free()` on one of these pointers yourself.**

A list's *header* (count/capacity/data-pointer, 16 bytes, ARC-managed as above) and its
*element storage* are two separate allocations: the header holds a plain `_malloc`'d data
pointer at offset 8, allocated and resized independently of the ARC header. That data pointer
has **no ARC header of its own** — nothing refcounts it directly; only the list header's
lifecycle governs it (growing/reassigning it on append, freeing it when the list itself is
released).

**Raw/manual** (`alloc[T](n)`, `free(p)`, FFI pointers, `.ptr`): `alloc[T]` is a thin wrapper
over `_malloc(n * sizeof(T))` with no header of any kind. `free(p)` always compiles directly to
libc `_free(p)` — it has no idea whether `p` is ARC-managed, and does not check.

## The boundary operations

### `.ptr` — read-only alias into ARC-managed storage

`list.ptr` returns the list's **element data pointer** (the plain `_malloc`'d array at offset
8 in the list header) — a real, independently-malloc'd address, but one the list still owns
and will reuse (on append/resize) or free (when the list's `ref_count` hits zero).
`string.ptr` returns the string's own pointer directly.

**Rules:**
- **Never call `free()` on a `.ptr` result.** For a list, the list still holds and will later
  free that same pointer — this is a guaranteed double-free, and in between, a use-after-free
  the next time the list is read, appended to, or resized (which may `realloc`/replace the data
  pointer out from under your copy regardless). For a string, the pointer may not even be a
  standalone heap allocation to begin with (literal/interned strings).
- **A `.ptr` value is only valid as long as the owning list/string is alive and hasn't been
  mutated.** Appending to or otherwise growing a list can reallocate its backing array,
  silently invalidating every `.ptr` taken before that point. Treat it like a C
  `std::vector::data()` result: a borrow, not an owned value, good only until the next mutation
  or the owner's last use.
- Passing a `.ptr` result to `alloc`-side APIs (anything that expects to own and later `free`
  what you hand it) is the same mistake as calling `free()` on it directly — don't.

### `.as_list(ptr, count=n)` — wrap raw memory as a list header, without ARC

`raw_ptr.as_list(count=n)` calls `_list_wrap`, which does a plain `malloc(16)` for the header
(count/capacity/data-pointer) — **not** `_nova_arc_alloc`. The returned list has no
`NovaARCHeader` at all.

**Rules:**
- **The wrapped list and the buffer it wraps are two independent allocations, and nothing
  frees either one for you.** `free(my_list)` frees only the 16-byte header; `free(my_list.ptr)`
  (equivalently, `free(raw_ptr)`) frees only the buffer. If you own `raw_ptr`, you are still
  responsible for freeing it yourself once you're done — wrapping it in a list does not
  transfer that responsibility to the runtime, because there is no refcounting here at all.
- **Do not let a `.as_list()` result reach any code path that assumes ARC semantics** —
  storing it as a dict value, returning it somewhere that retains/releases generically, or
  anything else that calls `_nova_value_retain`/`_nova_value_release`/`_nova_value_kind` on it.
  Those walk back 16 bytes from the pointer looking for a `NovaARCHeader` that was never
  written there; for a plain `malloc(16)` block, that's a heap-buffer-underflow read of
  whatever memory happens to precede it (unmapped guard page, allocator metadata, or an
  unrelated block), not a defined "not ARC-managed" result. Keep `.as_list()` results on the
  manual side of the boundary — index into them, pass them to other manual/FFI code, free them
  explicitly — and never hand them to anything that might box or generically retain a value.
- `.as_list()` is for consuming foreign memory (an `alloc[T]` buffer, an FFI return value) as a
  list *view*, not for turning foreign memory into a first-class, refcounted Nova value. There
  is currently no supported way to do the latter.

### `alloc[T]` / `free` — manual, and only manual

- Every `alloc[T](n)` must be matched by exactly one `free(p)` on that exact pointer, once
  nothing (including no `.as_list()` wrapper, no outstanding `.ptr`-style alias from something
  else) still needs it. No automatic cleanup exists or is planned for this pair.
- Double-free and use-after-free on `alloc`/`free` pointers are undefined behavior, same as C —
  the language gives you no help here by design; this is the deliberately-unsafe tier.

### `@raw` — no guarantees, full responsibility

Code inside `@raw` is raw assembly; it is not checked against any of the above. If it touches
an ARC-managed pointer (reads/writes a list or string's header fields, or a value's
`NovaARCHeader`), it must preserve every invariant this document describes manually — the
compiler enforces nothing inside `@raw`, the same way an `unsafe` block in other languages
doesn't make the invariants it violates stop mattering.

## Summary table

| You have... | Free it with... | Never... |
|---|---|---|
| A list/dict/string value | Nothing — ARC frees it when unreferenced | `free()` it directly |
| `alloc[T](n)` result | `free(p)`, exactly once | Double-free, use-after-free, or `.as_list()`-wrap-then-forget |
| `list.ptr` / `string.ptr` | Nothing — you don't own it | `free()` it; use it after the owner mutates or drops |
| `raw_ptr.as_list(count=n)` | `free(wrapped)` **and separately** `free(raw_ptr)` if you own it | Let it reach ARC-aware code (dict values, generic retain/release) |
