# Nova VS Code Extension

Official VS Code extension providing rich language support and native Language Server (`novalsp`) integration for the **Nova programming language**.

## Features

- **Zero External Dependencies**: Operates directly with the VS Code Extension API and standard Node.js runtime—no bulky `node_modules` or npm installations required.
- **Syntax Highlighting**: Comprehensive TextMate grammar covering:
  - Declarations: `def`, `class`, `data`
  - Flow control: `if`, `elif`, `else`, `while`, `return`, `defer`, `try`, `except`, `finally`
  - Types: `int`, `float`, `string`, `bool`, `list`, `dict`, `any`, `void`
  - Unsafe memory and low-level constructs: `@raw`, `alloc`, `free`
  - String interpolation: `{expression}` inside double-quoted strings
  - Numeric literals: Decimals, floating points, hex (`0x...`), and binary (`0b...`)
- **Native Diagnostics via `novalsp`**:
  - Syntax error reporting with pinpoint byte/character accuracy.
  - Import resolution diagnostics.
  - Static type warnings and type error checks.
  - Non-blocking syntax verification on buffer edits (`didChange`) and full type checking on save (`didSave`) and open (`didOpen`).

## Requirements

1. **`novalsp` Executable**:
   - The extension searches for `novalsp.exe` (or `novalsp` on POSIX) automatically in:
     - Configured setting: `nova.lsp.path`
     - Project root and `nova/` subdirectories
     - System `PATH`
   - To build `novalsp` from source:
     ```bash
     cd nova
     python bootstrap/main.py build lsp/server.nv -o novalsp.exe
     ```

## Extension Settings

This extension contributes the following settings:

* `nova.lsp.enable`: Enable or disable the native Nova Language Server (`true` by default).
* `nova.lsp.path`: Custom absolute path to the `novalsp` binary.
* `nova.lsp.trace`: Trace level for LSP JSON-RPC communication (`"off"`, `"messages"`, or `"verbose"`).

## Commands

* `Nova: Restart Language Server`: Restarts the native `novalsp` process and refreshes editor diagnostics.

