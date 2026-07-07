# Nova Library Development Guide

This guide covers how to create, test, and contribute libraries for the Nova
programming language — both **in-built (stdlib)** libraries and **external**
packages distributed via Galaxy.

---

## 1. Library Types

| Type | Location | Import Syntax | Distribution |
|------|----------|---------------|--------------|
| **In-built (stdlib)** | `stdlib/*.nv` | `import system` | Bundled with compiler |
| **OS backend** | `stdlib/backend/<arch>/os_*.nv` | `import os_impl` | Platform-resolved |
| **Codegen backend** | `stdlib/backend/<arch>/` | `import codegen` | Architecture-resolved |
| **External (Galaxy)** | `galaxy_modules/<pkg>/` | `import <pkg>` | Galaxy registry |

## 2. Stdlib Library Structure

Standard libraries live in `stdlib/` and are plain Nova files (`.nv`).

### Directory Layout

```
stdlib/
  system.nv           # Cross-platform OS abstractions
  errors.nv           # Error/warning printer
  lexer.nv            # Self-hosted tokenizer
  parser.nv           # Self-hosted parser
  types.nv            # Type system
  type_checker.nv     # Type inference
  compiler.nv         # Compiler pipeline
  vm.nv               # Nova VM
  peephole.nv         # Assembly peephole optimizer
  codegen_common.nv   # Shared externs + data strings
  backend/
    x86_64/
      os_windows.nv   # Windows OS HAL
      os_unix.nv      # Unix OS HAL
      codegen.nv      # x86_64 code generation
      ...
    arm64/
      os_windows.nv   # Windows OS HAL (ARM64)
      os_unix.nv      # Unix OS HAL (ARM64)
      codegen.nv      # ARM64 code generation
      ...
```

### Creating a New Stdlib Library

1. Create `stdlib/my_library.nv`:

```nova
# stdlib/my_library.nv
# My utility library

import system

def my_func(x: int) -> int {
    return x * 2
}
```

2. Import it from any Nova program:

```nova
import my_library
print(my_library.my_func(5))   # 10
```

### Using the Import System

Nova resolves imports in this order:

1. **Current directory** (relative to the importing file)
2. **`stdlib/`** (in-built libraries)
3. **`stdlib/backend/<target_arch>/`** (architecture-specific)
4. **`galaxy_modules/<name>/`** (installed packages)

**Example resolution** for `import os_impl` on x86_64 Windows:
```
os_impl.nv  →  stdlib/backend/x86_64/os_windows.nv
```

## 3. Creating an External Library (Galaxy Package)

Use the `galaxy init library` command to scaffold a new library:

```bash
galaxy init library my-lib
cd my-lib
```

This creates:

```
my-lib/
  galaxy.json           # Package manifest
  README.md             # Documentation
  src/
    main.nv             # Library entry point
    types.nv            # Data type definitions
  tests/
    test_main.nv        # Tests
    test_types.nv       # Tests for types
  examples/
    demo.nv             # Usage example
```

### Writing Your Library Code

Edit `src/main.nv` with your public API:

```nova
# src/main.nv
import system

export my_func
export MyStruct

def my_func(x: int) -> int {
    return x * 2
}

data MyStruct {
    name: string
    value: int
}
```

## 4. Testing

### Running Tests

From your library directory:

```bash
# Run all tests (compiles to native — slower but comprehensive)
galaxy test

# Run tests in VM mode (faster for iteration)
galaxy test --vm

# Run a specific test
galaxy test --vm test_types
```

### Writing Tests

Test files go in `tests/` and end with `.nv`. They are regular Nova programs
that import your library and check behavior:

```nova
# tests/test_main.nv
import main as lib

# Test my_func
result = lib.my_func(5)
if result == 10 {
    system.file_write(2, "PASS: my_func\n")
} else {
    system.file_write(2, "FAIL: my_func got " + str(result) + "\n")
}
```

Tests run as standalone programs. **Exit code 0 = PASS**, non-zero = FAIL.
Write diagnostics to stderr (`system.file_write(2, ...)`) to keep them
visible in the test runner output.

### Testing Stdlib Libraries

For in-built stdlib libraries, use the existing Python test framework:

```bash
# Run all tests
python -m unittest discover tests -v

# Run a specific test file
python -m unittest tests.test_codegen_x86_64 -v

# Test a library via VM
python bootstrap/main.py dev tests/test_my_library.nv
```

## 5. The OS Abstraction Pattern

The system library (`stdlib/system.nv`) uses a **virtual import** pattern for
cross-platform support:

```nova
# stdlib/system.nv
import os_impl                        # Resolved at compile time

def file_open(path, mode) {
    return os_impl.sys_open(path, mode)
}
```

The `os_impl` import is special-cased in the compiler to resolve to:
- `stdlib/backend/<arch>/os_windows.nv` on Windows
- `stdlib/backend/<arch>/os_unix.nv` on Linux/macOS

To add a new OS-level function:

1. Add the C implementation to `runtime.c`
2. Add the `.extern` declaration in `stdlib/codegen_common.nv`
3. Add the wrapper function in all 4 `os_*.nv` files
4. Expose it through `stdlib/system.nv`

## 6. The Codegen Backend Pattern

Each architecture backend provides the same API surface:

| File | Purpose |
|------|---------|
| `codegen.nv` | Entry point, function compilation, data section |
| `codegen_expr.nv` | Expression → assembly |
| `codegen_stmt.nv` | Statement → assembly |
| `assembler.nv` | Assembly parser (imports sub-modules) |
| `assembler_parse.nv` | Line/operand parsing |
| `assembler_encode.nv` | Instruction encoding |
| `assembler_pass.nv` | Label resolution + fixups |
| `linker.nv` | PE executable generation |
| `os_windows.nv` | Windows OS HAL |
| `os_unix.nv` | Unix OS HAL |

Shared code lives in `stdlib/codegen_common.nv` (used by all backends):

```nova
# stdlib/codegen_common.nv
def get_externs() -> list {
    # Add new external symbols here
}
def get_data_strings() -> list {
    # Add new data section strings here
}
```

## 7. Performance Guidelines

### DO
- Use `system.file_write(2, msg)` for test/diagnostic output instead of
  `print()` (avoids stdout pollution in CI)
- Prefer `import system` over calling runtime C functions directly
- Keep library functions focused and well-documented
- Use data types (`data StructName { ... }`) for structured data

### DON'T
- Don't use `@raw` assembly blocks in library code (reserved for backends)
- Don't hardcode platform-specific logic — use the `os_impl` pattern
- Don't create circular imports (A imports B imports A)
- Don't use `str()` in hot paths in the compiler itself (prefer if-elif chains)

## 8. Contributing Back

### For Stdlib Libraries

1. Create your `.nv` file in `stdlib/`
2. Add tests in `tests/` (either `.nv` or Python-based)
3. Update `AGENTS.md` with your changes
4. Create a PR

### For External Galaxy Packages

1. `galaxy init library my-lib`
2. Write your code and tests
3. `galaxy test` — ensure all tests pass
4. `galaxy publish` — submits a GitHub Issue to the registry

## 9. Quick Reference

```bash
# Scaffold a new library
galaxy init library my-lib

# Run tests
galaxy test              # Native compilation
galaxy test --vm         # VM mode (faster)

# Run a .nv file directly
python bootstrap/main.py dev my_file.nv          # VM
python bootstrap/main.py build my_file.nv        # Native

# Run Python-based tests
python -m unittest tests.test_codegen_x86_64 -v

# Build the self-hosted compiler (full test)
python bootstrap/main.py build nova.nv
./nova --version
```
