# Nova Windows OS Internals (`stdlib/os_win.nv`)

The `os_win.nv` module serves as the platform-specific HAL (Hardware Abstraction Layer) for Windows environments natively compiled via the MinGW GCC toolchain. It provides file system interactions, process introspection (command-line arguments), and system-level operations using standard C libraries (`msvcrt.dll`) and Windows APIs (`kernel32.dll`).

## Command-Line Argument Parsing (`sys_get_args`)

Since a standard `main(int argc, char** argv)` is not easily accessible via our custom compiler entry point sequence without modifying the `.s` prologue wrapper, Nova directly interfaces with the Windows PEB (Process Environment Block) to fetch arguments.

1. **`GetCommandLineA()` FFI:** 
   The Windows API function is called natively to return a pointer to the raw ANSI string buffer containing the execution command (e.g., `"nova.exe" build script.nv`).
2. **Raw Memory Traversal (`@raw` blocks):**
   Nova uses `@raw` blocks combined with `.value_byte` pointer dereferencing to iterate over the `GetCommandLineA()` buffer byte-by-byte natively.
3. **Quotation Tracking:**
   Windows command-line arguments can contain spaces if wrapped in `"quotes"`. The parser manually tracks `in_quotes = 1` vs `in_quotes = 0` to identify logical argument boundaries.
4. **Extraction (`_sys_extract_arg`):**
   Once a contiguous argument is bounded, it allocates a native `malloc` buffer of exact size, copies the bytes from the pointer, appends a `\0` null terminator, and returns it dynamically cast as a Nova string.

## File System Interface (`read_file`)

`os.read_file(path)` is implemented differently depending on whether it is executed inside the Python VM or the Native compiled environment:

* **Python execution:** Falls back to Python's built-in `open().read()`.
* **Native execution:** 
  1. Compiles to an `OpenFile` and `ReadFile` AST sequence.
  2. The `Codegen` layer converts this to calling `fopen(path, "r")` via FFI.
  3. `malloc(65536)` dynamically allocates a 64KB read buffer.
  4. `fread()` pulls bytes directly into the buffer, appends a null terminator based on the exact read count returned in `eax`, and returns the raw C-string pointer.

## Design Philosophy

The `os_win.nv` library utilizes the `sys_platform()` function (which evaluates to `"windows"` natively) to safely separate platform-specific implementation details, ensuring that the same Nova script could theoretically run on Linux in the future (e.g., via a parallel `os_linux.nv` module referencing POSIX FFI).
