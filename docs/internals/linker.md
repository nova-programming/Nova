# Nova Linker Internals (`stdlib/linker.nv`)

The `linker.nv` module constructs a Windows PE (Portable Executable) binary from raw byte streams produced by the assembler. Integrated via `assemble_link_file()` in `stdlib/compiler.nv` — the `nova assemble-link` command and `main.py`'s auto-fallback both use it. Supports both x86_64 (PE32+) and ARM64 PE32+ formats.

## PE Format Construction

The linker manually builds:
1. **DOS Header** — MZ signature and DOS stub
2. **PE Header** — signature, file header (x86_64 or ARM64 machine), optional header (entry point, image base `0x00400000`, alignments)
3. **Section Headers** — `.text` (code), `.data` (static data), `.idata` (imports)
4. **`.text`** — assembled machine code bytes
5. **`.data`** — string literals and static data
6. **`.idata`** — Import Address Table for FFI to `kernel32.dll` (no C runtime dependencies)

## Label Resolution

Two-pass assembly:
- **Pass 1**: Record label positions, encode instructions with placeholder fixups
- **Pass 2 (apply_relocs)**: Calculate relative jump offsets and patch fixup entries

## Heap Reserve

The PE optional header's `HeapReserve` field is set to **16,777,216 (16 MB)** to accommodate the memory needs of self-hosted compilation. The default Windows 1 MB heap reserve was insufficient when the Nova compiler compiles itself (large `List` structures for AST, assembly lines, and fixups).

## Stdcall Decoration Stripping

Import name resolution strips `@N` stdcall suffixes (e.g., `ExitProcess@4` → `ExitProcess`). The linker removes the `@N` decoration from DLL names before looking up imports, ensuring Win32 API functions link correctly even when the assembler emits decorated names.

## Imports (x86_64 & ARM64 PE Linker)

The integrated PE linker (`stdlib/linker.nv`) is used for the assembly-link path on both x86_64 and ARM64. The in-process assembler+linker (`assemble_link_file`) works for both architectures — no GCC or external toolchain needed. ARM64 uses its own PE32+ variant at `stdlib/backend/arm64/linker.nv`. GCC fallback is only used when the in-process path fails or when explicitly requested.

Generates thunks and IAT entries for external functions (`GetProcessHeap`, `HeapAlloc`, `WriteFile`, `CreateFileA`, `ReadFile`, `GetCommandLineA`, `ExitProcess`, `SetFilePointer`, `FlushFileBuffers`, `CloseHandle`, `GetStdHandle`), mapping them to `kernel32.dll` and constructing `IMAGE_IMPORT_DESCRIPTOR` structures.

## Bare-Metal Flat Binary Mode (`link_bare`)

In addition to PE generation, the linker supports a bare-metal flat binary mode via `link_bare(sections, load_addr)`:

- **No PE headers** — raw code + data concatenation
- **No import section** — undefined symbols cause a hard error
- **Configurable load address** — used for absolute fixup resolution (e.g., 0x7C00 for bootsector)
- **Layout**: code starts at offset 0, data follows immediately after

CLI commands:
- `nova build-bare <file.nv> [load_addr_dec] [entry_label]` — compile `.nv` source to flat binary
- `nova assemble-bare <input.s> <output.bin> [load_addr_dec]` — assemble `.s` file to flat binary
