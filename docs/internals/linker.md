# Nova Linker Internals (`stdlib/linker.nv`)

The `linker.nv` module takes the raw x86 assembly instructions produced by `codegen.nv` and transforms them into a standalone, directly executable Windows PE (Portable Executable) binary (`.exe`). This eliminates the need for an external assembler (like NASM) and linker (like GCC) when bootstrapping.

## The Portable Executable (PE) Format

The linker manually constructs the standard PE32 header structures required by the Windows loader. It writes out exactly:
1. **DOS Header:** The standard MZ header and DOS stub.
2. **PE Header:** The `PE\0\0` signature, File Header (machine type `x86`, number of sections), and Optional Header (entry point, Image Base `0x00400000`, section alignment `4096`, file alignment `512`).
3. **Section Headers:** Metadata defining the virtual offsets and physical file offsets for `.text` (code), `.data` (static variables/strings), and `.idata` (imports).

## Resolution of Labels and Fixups

Because assembly generation is linear, forward jumps (like `if` statements or `while` loops) reference labels that haven't been resolved to memory addresses yet.
- **Labels:** The linker maintains a list of labels (e.g., `L_end_5`). When a label is defined, its exact byte offset in the `.text` section is recorded.
- **Fixups:** When a jump instruction references a label (e.g., `jmp L_end_5`), a placeholder is left in the raw bytes, and a `Fixup` record is created.
- **apply_relocs:** After the entire `.text` section is assembled, the linker iterates through the fixups, calculates the relative 32-bit distance (`target_offset - (instruction_offset + 4)`), and overwrites the placeholder bytes.

## The `.idata` Section (Imports)

The most complex task of the native linker is constructing the Import Address Table (IAT) so the executable can call Windows API and C standard library functions (FFI).

1. **Detection:** The linker scans the list of required external labels (e.g., `_printf`, `_GetCommandLineA`).
2. **Grouping:** It statically maps requested external functions to their parent DLLs (`msvcrt.dll` or `kernel32.dll`).
3. **Thunks:** It generates "thunk" code in the `.text` section for each imported function. When Nova code issues a `call _printf`, it jumps to this thunk, which then performs an indirect jump (`jmp [IAT_Entry]`) to the real address loaded by Windows.
4. **IMAGE_IMPORT_DESCRIPTOR:** It builds the structured import directory, containing ILT (Import Lookup Table) arrays, IAT arrays, and ASCII strings of the DLL/function names.

## Final Output

The final result is a contiguous `list` of raw bytes in Nova, which can be saved to disk as a complete `.exe` file.
