# Nova Roadmap

## Bootstrap Status

The self-hosted compiler pipeline is **fully functional** and bootstraps successfully:

| Stage | Description | Status |
|-------|-------------|--------|
| Python bootstrap | `main.py` compiles `nova_main.nv` → `nova_main.exe` (via GCC) | ✅ |
| Self-hosted build | `nova_main.exe build hello.nv` → in-process assemble+link → `.exe` | ✅ |
| Self-hosted bootstrap | `nova_main.exe build nova_main.nv` produces working compiler | ✅ |
| GCC-free (Nova path) | `nova build` uses `assemble()` + `link()` — zero GCC involved | ✅ |
| GCC-free (Python path) | `main.py build` delegates non-self builds to Nova binary | ✅ |

## Near-Term Goals

### GCC-Free Pipeline (Phase 1) — ✅ Complete

The assembler (`assembler.nv` + submodules) and linker (`linker.nv`) are fully integrated. The `build` command uses `compile_to_exe()` which calls `assemble()` + `link()` in-process — no `.s` file written, no GCC invoked. The Python fallback (`main.py`) delegates non-self builds to the Nova binary's `assemble-link` command. The runtime uses kernel32-only APIs (`HeapAlloc`/`HeapFree`/`WriteFile`/etc.) with zero MSVCRT dependency.

### Language Completeness & Remaining Work

| Feature | Status |
|---------|--------|
| Self-hosted lexer | ✅ |
| Self-hosted parser | ✅ |
| Self-hosted codegen | ✅ |
| Self-hosted type checker | ✅ |
| Static type inference | ✅ |
| Array bounds checking | ✅ |
| List type unification | ✅ |
| Compile-time constant folding | ✅ |
| Capacity-based list alloc | ✅ |
| `String` character access via static table (no malloc) | ✅ |
| Boolean short-circuit (`and`/`or`) | ✅ |
| For-in loop over lists (`for i in items`) | ✅ |
| Float literals + x87 runtime `print` | ✅ |
| Debug print (`printd`) with line numbers | ✅ (`debug - [line N]: <value>`) |
| Smart error messages with fix suggestions | ✅ (`errors.nv` module with `err()`/`warn()`) |
| Self-hosted assembler + linker integration | ✅ (in-process `assemble()` + `link()` in `build` path) |
| `_realloc` no `HEAP_REALLOC_IN_PLACE_ONLY` | ✅ (flag 0, allows heap block movement) |
| Self-hosted GCC-free pipeline | ✅ (fully integrated in `build` command) |
| Struct-aware `get_prop_offset` | ✅ (per-struct field tables via `struct_fields`, resolves from `inferred_type`) |
| Class dunder methods in native codegen | ✅ (`__init__`, `__str__`, `__len__`, `__eq__`, `__add__`, `__sub__`, `__mul__`) |
| Raw memory (`@raw`, `alloc`/`free`) | ✅ |
| String slice + concat runtime helpers | ✅ (`_slice_string`, `_concat_strings`) |
| Dynamic arrays/lists (native) | ✅ |
| `sys_get_args` (native) | ✅ |
| `sys_system` (native GCC invocation) | ✅ |
| Variable-to-Register Promotion (Phase 3) | ✅ (Maps vars directly to `esi`/`edi` reducing latency ~50%) |

## Near-Term Goals

### 1. Cross-Platform Abstractions (`os_*.nv`)
Develop a unified OS-layer interface (`system.nv`) that automatically swaps out implementations based on whether the host is Windows (`os_win.nv`), Linux (`os_linux.nv`), or macOS (`os_mac.nv`), completely hiding specific configs from end-users.

### 2. The "Galaxy" Package Manager
Design and architect a central repository and library manager (akin to `pip` or `cargo`) to allow developers to build, pull, and distribute pure Nova codebase packages effortlessly.

### 3. Small Function Inlining (Phase 4)
Implement advanced compiler optimizations to inline extremely short, non-recursive functions, entirely eliminating call/ret overhead for utility methods.

## Long-Term Goals

### 64-bit x86_64 Support

- Update codegen to emit 64-bit registers (`rax`/`rbx`/`rcx`)
- Adopt System V AMD64 or Windows x64 calling convention
- Implement 16-byte stack alignment for external calls

### Self-Hosted VM

- Rewrite the Python bytecode VM in Nova
- `nova dev` mode runs entirely within native Nova binary
