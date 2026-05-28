# Nova Linker Internals (`stdlib/linker.nv`)

The `linker.nv` module constructs a Windows PE (Portable Executable) binary from raw byte streams produced by the assembler. **Not yet integrated into the default compilation path** — the current pipeline emits `.s` assembly and uses GCC for linking.

## PE Format Construction

The linker manually builds:
1. **DOS Header** — MZ signature and DOS stub
2. **PE Header** — signature, file header (x86 machine), optional header (entry point, image base `0x00400000`, alignments)
3. **Section Headers** — `.text` (code), `.data` (static data), `.idata` (imports)
4. **`.text`** — assembled machine code bytes
5. **`.data`** — string literals and static data
6. **`.idata`** — Import Address Table for FFI to `kernel32.dll` (no C runtime dependencies)

## Label Resolution

Two-pass assembly:
- **Pass 1**: Record label positions, encode instructions with placeholder fixups
- **Pass 2 (apply_relocs)**: Calculate relative jump offsets and patch fixup entries

## Imports

Generates thunks and IAT entries for external functions (`GetProcessHeap`, `HeapAlloc`, `WriteFile`, `CreateFileA`, `ReadFile`, `GetCommandLineA`, `ExitProcess`, `WinExec`, `SetFilePointer`, `FlushFileBuffers`, `CloseHandle`, `GetStdHandle`), mapping them to `kernel32.dll` and constructing `IMAGE_IMPORT_DESCRIPTOR` structures.
