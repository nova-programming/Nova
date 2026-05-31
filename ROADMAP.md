# Nova Roadmap

## Bootstrap Status

The self-hosted compiler pipeline is **fully functional** and bootstraps successfully:

| Stage | Description | Status |
|-------|-------------|--------|
| Python compiler | `main.py` compiles `nova_main.nv` → x86 assembly | ✅ |
| Bootstrap 1 | `nova_main.exe` compiles `nova_main.nv` → working executable | ✅ |
| Bootstrap 2 | Nova-compiled exe recompiles itself identically | ✅ |
| GCC dependency | Assembly is linked via `gcc` call from within the Nova binary | ⏳ |
| GCC-free pipeline | `assemble_link_file` in `compiler.nv` uses `assemble()` + `link()` directly | ✅ |
| GCC-free bootstrap | `main.py` delegates non-self builds to `nova.exe assemble-link` (GCC-free) | ✅ |

## Near-Term Goals

### GCC-Free Pipeline (Phase 1)

The assembler (`assembler.nv` + submodules) and linker (`linker.nv`) are now integrated via `assemble_link_file()` in `stdlib/compiler.nv`. The `nova assemble-link` command in `nova_main.nv` reads assembly text, assembles it to bytecode, and links a PE executable — all in-process without GCC. `main.py` also auto-delegates non-self builds to this path. Remaining goals:

1. **Default pipeline integration**: The `build` command still generates `.s` assembly and invokes GCC. Goal is to replace the `.s` write + GCC step with in-process assemble+link.
2. **Native memory allocator**: Replace MSVCRT `malloc`/`free` dependencies with a syscall-backed allocator in `stdlib/os_win.nv`

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
| Self-hosted assembler `and reg, imm` encoding | ✅ (fix for `AluImm` op 4) |
| Self-hosted PE linker heap expansion | ✅ (16MB reserve) |
| Self-hosted PE linker `@N` stdcall stripping | ✅ (strips `@N` decorations for Win32 APIs) |
| Self-hosted GCC-free pipeline | ✅ (`nova assemble-link` command, `main.py` auto‑fallback) |
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
