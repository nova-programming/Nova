# Nova Windows OS Internals (`stdlib/os_win.nv`)

Platform-specific HAL for Windows native compilation. All standard OS functions are natively injected and compiled into every executable (no import statement is required).

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
- **`sys_get_tick_count()`**: Returns system tick count in milliseconds via `GetTickCount` (kernel32)

## Implementation Details

Uses `@raw` blocks for inline assembly to:
- Call Windows API functions via FFI thunks
- Dereference `GetCommandLineA()` result byte-by-byte via `.value_byte`
- Perform raw memory allocation and byte copying for argument extraction

### Argument Quote Stripping

`_sys_extract_arg()` detects and strips surrounding double quote (`"`) characters from argument strings before returning them. This allows `fopen` to receive clean, unwrapped file paths when the command line contains quoted paths (e.g., `nova build "C:\path\to\file.nv"`).
