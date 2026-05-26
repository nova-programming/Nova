# Nova Future Roadmap: The Path to "True" Self-Hosting

Nova is partway through the self-hosting journey. The Nova-written compiler pipeline can currently lex, parse, assemble, and link Nova source into a structured binary image, but the toolchain still depends on the Python host compiler, GCC for native executable output, and host-backed runtime services.

To make Nova **truly independent and robust**, we must systematically eliminate these dependencies. The roadmap below breaks down the five major phases required to achieve True Self-Hosting.

---

## ✅ Completed Milestones

The following language features are implemented in both the Python host compiler and the self-hosted Nova compiler:

| Feature | Description |
|---------|-------------|
| `elif` keyword | Replaces `else if` — single keyword conditional chaining |
| `has` operator | Runtime field-existence check for `data` structs |
| `&` bitwise AND | Integer bitwise AND operator |
| `<<` left shift | Integer left-shift operator |
| `>>` right shift | Integer right-shift operator |
| `const` keyword | Immutable variables; all variables are mutable by default |
| String slicing `s[i:j]` | Substring extraction in VM and native codegen |
| Native `_slice_string` | x86 assembly runtime helper for string slicing |
| Native `_concat_strings` | x86 assembly runtime helper for string concatenation |
| Self-hosted assembler | Nova assembler emits machine-code byte streams |
| Structured linker image | Nova linker packages code/data/metadata into a binary image |
| Syscall façade modules | `stdlib/os_win.nv` and `stdlib/os_linux.nv` exist for runtime abstraction |
| Dynamic struct sizing | `Data` struct field allocations computed dynamically based on the exact max offset footprint of the program |

| Native Class & OOP Support | Vtables and dynamic method dispatch in native codegen, plus dunder methods (`__init__`, `__str__`, etc.) |
| Advanced Built-in Types | Native dynamic string concatenation, comparison, and list (array) resizing |
| Boolean Operators | Complex boolean operations (`and`, `or`, `not`) with short-circuit evaluation in native assembly |
| Native PE Linker | Custom linker emits valid Windows PE executables (`.exe`) directly from byte streams without GCC |
| OS Subsystem Independence | PE linker handles Import Address Tables (IAT) for MSVCRT dynamic linkage directly |

---

## Phase 1: Raw Syscall Integration (C-Free)

Nova currently relies on MSVCRT (`printf`, `fopen`, `malloc`) for its runtime via dynamic linking. The next step is to replace those host-backed helpers with direct Win32/Linux syscalls where practical.

**Action Plan:**
1. **Syscall Abstraction Layer:**
   - Replace the façade internals with direct syscall-backed implementations for Windows and Linux.
   - Keep the platform split in `stdlib/os_win.nv` and `stdlib/os_linux.nv`.
2. **Native Memory Management (`malloc`/`free`):**
   - Replace the remaining host-managed allocation paths with a syscall-backed allocator that can request pages from the OS and sub-allocate them in Nova.
3. **Native I/O (`printf`, `fopen`):**
   - Keep formatting and file operations fully in Nova while routing output through direct OS write/open/read/close syscalls.
   - Remove remaining host file-object dependencies from the runtime layer.

---

## Phase 2: Self-Hosted Virtual Machine

The VM is still Python-based today. To unify the toolchain, the bytecode interpreter must be rewritten natively in Nova so the entire ecosystem (VM + Compiler + CLI) exists within a single native binary.

**Action Plan:**
1. **Bytecode Definition:**
   - Standardize the Nova bytecode specification. Create `enum`-like constants representing every opcode (e.g., `OP_ADD`, `OP_JUMP`, `OP_PRINT`).
2. **The Execution Loop:**
   - Write the core VM loop (`stdlib/vm.nv`) consisting of a massive `if/else` block (or computed goto) that fetches, decodes, and executes bytecode instructions.
3. **Native Memory & Stack Simulation:**
   - Implement the VM's operand stack and environment maps (for variable storage) natively. 
   - Bridge native pointers and memory manipulation into the VM environment using Nova's `@raw` system.
4. **CLI Integration:**
   - Replace `main.py` entirely. Write a `cli.nv` entry point that takes arguments (e.g., `dev` or `build`).
   - If `dev` is passed, the native CLI parses the file to an AST, generates bytecode, and feeds it into the Native VM. If `build` is passed, it feeds the AST to the Native Codegen.

---

## Phase 3: 64-bit x86_64 Support

Nova still targets 32-bit x86 assembly in the self-hosted pipeline. The final roadmap step is to move the compiler, runtime helpers, and linker path to x86_64.

**Action Plan:**
1. **64-bit Registers & Pointers:**
   - Update `stdlib/codegen.nv` to emit 64-bit registers (`rax`, `rbx`, `rcx`, `rsp`, `rbp` instead of `eax`, `ebx`, etc.).
   - Expand all memory pointer calculations and struct layouts to account for 8-byte pointer sizes instead of 4-byte.
2. **Calling Convention Update:**
   - 32-bit assembly relies heavily on pushing arguments to the stack (`push eax`). 
   - Update the codegen to comply with modern 64-bit calling conventions (e.g., System V AMD64 ABI passes the first 6 arguments in registers: `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`, and Windows x64 uses `rcx`, `rdx`, `r8`, `r9`).
3. **Stack Alignment Constraints:**
   - Implement strict 16-byte stack boundary alignment before making any function or system calls, which is mandatory in 64-bit execution environments.
