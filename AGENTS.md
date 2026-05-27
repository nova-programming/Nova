# Agent Session Summary

## Current Milestone
- **COMPLETED: Full MSVCRT removal! Nova compiler generates 100% standalone executables depending ONLY on kernel32.dll.**
- **COMPLETED: All bootstrap stages verified — Python→Gen1→Gen2→hello.exe all work without msvcrt.**

## What Was Accomplished

### Phase 1: String Indexing Fix & .byte Directive
1. **Fixed the 0xC0000005 crash**: Root cause was `malloc(2)` heap exhaustion from millions of `s[i]` character accesses during parsing of 54,000+ line assembly files.
2. **String indexing optimization**: Replaced dynamic `malloc` with static lookup table `char_strings` in `.data` section. Both Python and Nova codegens use pointer-offset calculation into this table.
3. **`.byte` directive support**: Added to `assembler_pass.nv` for emitting the `char_strings` static array.

### Phase 2: MSVCRT Dependency Removal
4. **Replaced all C stdlib functions** with Win32 API calls:
   - Memory: `malloc`/`free`/`realloc` → `HeapAlloc`/`HeapFree`/`HeapReAlloc`
   - Console I/O: `printf`/`puts` → `WriteFile` + custom int/char formatters
   - File I/O: `fopen`/`fread`/`fwrite`/`fputs`/`fputc`/`fclose`/`fseek`/`ftell`/`fflush` → `CreateFileA`/`ReadFile`/`WriteFile`/`SetFilePointer`/`FlushFileBuffers`/`CloseHandle`
   - String: `strlen`/`strcmp`/`strcpy`/`strcat`/`strstr`/`memset` → custom inline x86 assembly
   - Process: `exit`/`system` → `ExitProcess`/`WinExec`
   - Formatting: `sprintf` → custom `"%d"` handler
5. **Stack & register corruption fixes**:
   - `L_write_stdout`/`_malloc` had improper `add esp, N` cleanup with stdcall
   - Callee-saved registers (`ebx`, `edi`) corrupted by `_fputs`, `_concat_strings`, `_strlen`
   - `_CreateFileA` returns `INVALID_HANDLE_VALUE` (-1), not 0, on failure
   - `_fseek`/`_ftell` swapped `whence` into pointer parameter position
6. **Dual-path naming convention**:
   - `codegen_x86.py` (GCC target): emits `@N` decorated names (`_GetProcessHeap@0`) for MinGW compatibility
   - `stdlib/codegen.nv` (Nova PE linker target): emits bare names (`GetProcessHeap`) for native IAT binding
7. **Linker** (`stdlib/linker.nv`): Simplified to single `kernel32.dll` import table; removed all `msvcrt.dll` branching.

### Phase 3: Gen 1 Build Fix
8. **Underscore prefix mismatch**: Fixed `call _GetProcessHeap` → `call GetProcessHeap` in `codegen_x86.py` runtime section. The `.extern` declarations had been fixed but the `call` instructions still had the `_` prefix, causing GCC "undefined reference" errors.

## Full Verification Chain
- `python main.py build nova_main.nv` → `nova_main.exe` (Gen 1 via GCC) ✅
- `.\nova_main.exe build nova_main.nv` → self-hosts, exits 0 (Gen 2) ✅
- `.\nova_main.exe build tests\hello.nv` → `hello.exe` prints "Hello from Nova!" ✅

## Files Modified (this session)
- `compiler/codegen_x86.py`: Stripped `_` prefix from all Win32 API calls in `_emit_win32_runtime()`
- Various test files cleaned up, scratch directory emptied

## State
- **Status: COMPLETE** — Nova compiler is fully self-hosting with zero C runtime dependencies.
- GCC is only used for the Python→Gen 1 bootstrap step.
- Python is only needed for initial bootstrap on a clean machine.

## Remaining Dependencies
- `kernel32.dll` for standard Windows OS API operations
- *ZERO C runtime dependencies. `msvcrt.dll` is fully eliminated.*

## Key Files
- `nova_main.exe` — Gen 2+ self-hosted compiler
- `nova_main.nv` — compiler source
- `stdlib/` — standard library modules (assembler, linker, codegen)
- `tests/hello.nv` — test program
