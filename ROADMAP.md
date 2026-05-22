# Nova Future Roadmap: The Path to "True" Self-Hosting

Nova has achieved a self-hosting fixed point, meaning the native compiler can compile its own source code and generate an identical compiler. While this is a monumental milestone, the compiler still relies on a few external crutches (like `gcc`, Python, and the C Standard Library). 

To make Nova **truly independent and robust**, we must systematically eliminate these dependencies. The roadmap below breaks down the five major phases required to achieve True Self-Hosting.

---

## ✅ Completed Milestones

The following features have been implemented in both the Python host compiler and the self-hosted Nova compiler:

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

---

## Phase 1: Full Feature Parity in Native Codegen

The self-hosted codegen (`stdlib/codegen.nv`) currently relies on hardcoded struct sizes for bootstrapping and lacks dynamic string, list, and class implementations. We must port the advanced Python `codegen_x86.py` logic directly into `stdlib/codegen.nv`.

**Action Plan:**
1. **Dynamic Data Struct Sizing:** 
   - Parse `Data` declarations during the compilation pass to dynamically calculate the sizes of structs instead of relying on hardcoded heap allocations.
   - Maintain a symbol table for structs and their field byte-offsets to allow dynamic field access.
2. **Native Class & OOP Support:** 
   - Implement vtables or dynamic method dispatch in the native codegen to support classes.
   - Port `__init__` constructor wrapping and dunder method (`__str__`, `__len__`, etc.) logic from the Python compiler into `codegen.nv`.
3. **Advanced Built-in Types:** 
   - Write native assembly routines for dynamic string concatenation (`+`) and comparison (`==`).
   - Re-implement native dynamic array (list) scaling, allowing lists to grow gracefully when they exceed their initial capacity instead of crashing.
4. **Boolean Operators:** 
   - Fully support complex boolean operations (`and`, `or`, `not`) with short-circuit evaluation in the native assembly logic.

---

## Phase 2: Native Assembler & Linker (Dropping GCC)

Currently, Nova outputs `.s` assembly text and invokes `gcc` to assemble it and link it into an `.exe`. We need to write an Assembler & Linker natively in Nova that emits executable binaries directly (e.g., PE files for Windows or ELF files for Linux).

**Action Plan:**
1. **Instruction Encoding (Assembler):**
   - Write a module (`stdlib/assembler.nv`) that translates x86 text instructions (like `mov eax, 1` or `push ebx`) into their raw hexadecimal opcode counterparts (machine code).
   - Resolve internal jump labels to relative memory addresses during an assembler pass.
2. **Binary Header Generation (Linker):**
   - Study the PE (Portable Executable) format for Windows and the ELF (Executable and Linkable Format) for Linux.
   - Write a linker module (`stdlib/linker.nv`) that wraps the machine code inside the appropriate binary headers (DOS stub, PE headers, Section headers, etc.).
3. **Standalone Executable Output:**
   - Integrate the Assembler and Linker into `stdlib/compiler.nv`.
   - Instead of writing a `.s` file and invoking a shell command for GCC, write raw binary bytes to `output.exe` directly.

---

## Phase 3: Raw Syscall Integration (C-Free)

Nova still relies on the C Standard Library (imported via `extern _printf`, `_malloc`, `_fopen`, etc.) to interface with the operating system. We need to bypass the C runtime entirely by issuing OS-level syscalls directly via assembly.

**Action Plan:**
1. **Syscall Abstraction Layer:**
   - Identify the core Syscall numbers for Windows (e.g., `NtWriteFile`, `NtAllocateVirtualMemory`) and Linux (e.g., `sys_write`, `sys_mmap`).
   - Create a platform-specific OS interface file (e.g., `stdlib/os_win.nv` or `stdlib/os_linux.nv`).
2. **Native Memory Management (`malloc`/`free`):**
   - Replace C's `malloc` and `free`. Write a custom memory allocator in Nova that requests bulk memory pages from the OS using raw syscalls and sub-allocates them to the application.
3. **Native I/O (`printf`, `fopen`):**
   - Replace `printf` by formatting strings in memory natively and passing the resulting string buffer directly to the OS `sys_write` / `WriteFile` syscall.
   - Replace `fopen`/`read`/`write`/`close` with their direct OS file handler syscall equivalents.

---

## Phase 4: Self-Hosted Virtual Machine

Right now, running `nova dev file.nv` uses the Python VM. To unify the toolchain, we need to write the bytecode interpreter natively in Nova so the entire ecosystem (VM + Compiler + CLI) exists within a single native binary.

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

## Phase 5: 64-bit x86_64 Support

Nova currently generates 32-bit x86 assembly. Modern operating systems and architectures are strictly 64-bit, meaning Nova must eventually adopt x86_64 machine code.

**Action Plan:**
1. **64-bit Registers & Pointers:**
   - Update `stdlib/codegen.nv` to emit 64-bit registers (`rax`, `rbx`, `rcx`, `rsp`, `rbp` instead of `eax`, `ebx`, etc.).
   - Expand all memory pointer calculations and struct layouts to account for 8-byte pointer sizes instead of 4-byte.
2. **Calling Convention Update:**
   - 32-bit assembly relies heavily on pushing arguments to the stack (`push eax`). 
   - Update the codegen to comply with modern 64-bit calling conventions (e.g., System V AMD64 ABI passes the first 6 arguments in registers: `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`, and Windows x64 uses `rcx`, `rdx`, `r8`, `r9`).
3. **Stack Alignment Constraints:**
   - Implement strict 16-byte stack boundary alignment before making any function or system calls, which is mandatory in 64-bit execution environments.
