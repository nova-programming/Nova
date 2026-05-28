# Nova Windows OS Internals (`stdlib/os_win.nv`)

Platform-specific HAL for Windows native compilation via MinGW GCC. Provides OS-level services using C library FFI and inline assembly.

## Functions

- **`sys_get_args()`**: Calls `sys_read_byte` on result of `GetCommandLineA()`, returns parsed argument list as Nova string array
- **`sys_open(path, mode)`**: Opens file, returns integer file descriptor
- **`sys_read(fd)`**: Reads entire file content into a buffer, returns as Nova string
- **`sys_write(fd, content)`**: Writes string to file descriptor
- **`sys_close(fd)`**: Closes file descriptor
- **`sys_system(cmd)`**: Executes shell command via `WinExec` (kernel32)
- **`sys_flush()`**: Flushes stdout via `FlushFileBuffers` (kernel32)
- **`sys_exit(code)`**: Terminates process via `ExitProcess` (kernel32)
- **`sys_platform()`**: Returns `"windows"`

## Implementation Details

Uses `@raw` blocks for inline assembly to:
- Call Windows API functions via FFI thunks
- Dereference `GetCommandLineA()` result byte-by-byte via `.value_byte`
- Perform raw memory allocation and byte copying for argument extraction
