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

### `.as_list(ptr, count=n)` — wrap raw memory as an ARC-managed, non-owning view

`raw_ptr.as_list(count=n)` calls `_list_wrap`, which allocates its 16-byte header (count/
capacity/data-pointer) through `_nova_arc_alloc` like any other list, with one difference: it
sets the header's otherwise-unused `pad` field to `1`, marking it "borrowed." The returned
wrapper is a real, safely ARC-manageable list — `_nova_value_retain`/`_release`/`_kind`,
boxing it as a dict value, etc. all work correctly on it — but `_nova_dec_ref` checks that
`pad` flag before freeing anything: when a *normal* list's refcount hits zero it frees its
data pointer too, but a borrowed one only frees its own 16-byte header, never `raw_ptr`.

**Rules:**
- **`.as_list()` does not take ownership of `raw_ptr`.** If you own it, you are still
  responsible for `free(raw_ptr)` yourself once nothing — including the wrapper and anything
  that retained it — still needs it. The wrapper's own lifetime (ARC-managed, freed
  automatically) and the buffer's lifetime (yours, manual) are independent; only the 16-byte
  header goes away when the wrapper is released.
- **The same buffer can safely be wrapped more than once, or aliased by its original owner,
  without risking a double-free** — exactly because wrapping never frees the buffer. (This is
  also why it doesn't: a scheme where releasing a wrapper freed `raw_ptr` would double-free the
  moment the same buffer was wrapped twice, or freed by both its original owner and a wrapper.)
- `.as_list()` is for presenting foreign memory (an `alloc[T]` buffer, an FFI return value) as
  a list *view* — safe to pass anywhere a list is expected, including ARC-generic code — not
  for transferring ownership of that memory to Nova. There is currently no supported way to do
  the latter (hand Nova a buffer and have ARC free it for you); only `[1, 2, 3]`-style literals
  and other Nova-native allocations get that.

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
| `raw_ptr.as_list(count=n)` | Nothing for the wrapper (ARC frees it) — `free(raw_ptr)` separately if you own it | Assume wrapping transfers ownership of `raw_ptr` |
