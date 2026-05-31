# Nova Roadmap

## Bootstrap Status

The self-hosted compiler pipeline is **fully functional** and bootstraps successfully:

| Stage | Description | Status |
|-------|-------------|--------|
| Python compiler | `main.py` compiles `nova_main.nv` → x86 assembly | ✅ |
| Bootstrap 1 | `nova_main.exe` compiles `nova_main.nv` → working executable | ✅ |
| Bootstrap 2 | Nova-compiled exe recompiles itself identically | ✅ |
| GCC dependency | Assembly is linked via `gcc` call from within the Nova binary | ⏳ |

## Near-Term Goals

### GCC-Free Pipeline (Phase 1)

The assembler (`assembler.nv` + submodules) and linker (`linker.nv`) are already implemented in stdlib but not yet integrated into the default compilation path. The goal is:

1. **Assembly pipeline**: Replace the `.s` file output + GCC invocation with `assembler.nv` to emit raw byte streams directly in-process
2. **Linker pipeline**: Feed byte streams to `linker.nv` to produce PE `.exe` files without any external toolchain
3. **Native memory allocator**: Replace MSVCRT `malloc`/`free` dependencies with a syscall-backed allocator in `stdlib/os_win.nv`

### Language Completeness

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
| Self-hosted assembler `dl` register encoding | ✅ (fix for `str()` output) |
| `_realloc` no `HEAP_REALLOC_IN_PLACE_ONLY` | ✅ (flag 0, allows heap block movement) |
| Self-hosted assembler | ⏳ (not integrated into default path) |
| Self-hosted PE linker | ⏳ (not integrated into default path) |
| Self-hosted GCC-free pipeline | ⏳ (assembler+linker not integrated) |
| Struct-aware `get_prop_offset` | ⏳ (blocker for adding fields to structs) |
| Class dunder methods in native codegen | ✅ (`__init__`, `__str__`, `__len__`, `__eq__`, `__add__`, `__sub__`, `__mul__`) |
| Raw memory (`@raw`, `alloc`/`free`) | ✅ |
| String slice + concat runtime helpers | ✅ (`_slice_string`, `_concat_strings`) |
| Dynamic arrays/lists (native) | ✅ |
| `sys_get_args` (native) | ✅ |
| `sys_system` (native GCC invocation) | ✅ |

## Long-Term Goals

### 64-bit x86_64 Support

- Update codegen to emit 64-bit registers (`rax`/`rbx`/`rcx`)
- Adopt System V AMD64 or Windows x64 calling convention
- Implement 16-byte stack alignment for external calls

### Self-Hosted VM

- Rewrite the Python bytecode VM in Nova
- `nova dev` mode runs entirely within native Nova binary
