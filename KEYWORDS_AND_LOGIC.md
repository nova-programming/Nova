# KEYWORDS & LOGIC ARCHITECTURE

Nova aims to simplify programming by blending high-level ease with low-level power. Here is the concise breakdown of the keywords and their backend mechanics.

---

## High-Level Keywords

### `def`
**Use:** Defines functions/methods.
**Logic:** The compiler maps this to a `Function` or `ClassDef` method node. At runtime, the VM sets up a new local `Frame` and jumps the Instruction Pointer (IP) to the function's bytecode block.

### `class`
**Use:** Defines an OOP blueprint.
**Logic:** Creates a metadata definition in the compiler. At runtime, calling `ClassName()` evaluates a `NEW` OpCode, which instantiates a Virtual Machine `Instance` dictionary containing the class fields.

### `self`
**Use:** Refers to the current class instance.
**Logic:** When a method is called, the VM's frame captures the parent object. `LOAD_SELF` pushes this captured context instance to the stack so properties can be evaluated.

### `import`
**Use:** Loads external Nova modules or C libraries.
**Logic:**
1. `import module`: Compiles additional Nova files.
2. `import "lib" as alias`: Triggers FFI. Uses Python's `ctypes` in the VM to dynamically link the `.so`/`.dll` object into the runtime environment.

### `if`, `else`, `while`, `for`
**Use:** Control flow.
**Logic:** Compiles to `JUMP` and `JUMP_IF_FALSE` opcodes. The compiler tracks offsets to efficiently skip blocks of bytecode based on stack comparisons.

### `print`
**Use:** Outputs to console.
**Logic:** Pops the top value of the stack and writes to standard output natively.

---

## Low-Level Keywords (`@raw` block)

### `@raw`
**Use:** Enters the unsafe, high-performance low-level mode.
**Logic:** Suspends high-level safety constraints. Allows manual memory operations (`alloc`/`free`). Does not impact scoping, but conceptually grants the developer direct CPU/memory logic control.

### `@export`
**Use:** Bridges `@raw` elements out to high-level code.
**Logic:** While currently passively handled in the VM, in compiled static versions, it exposes C-linkage pointers/structs to the safe GC/ARC memory space.

### `alloc(size)`
**Use:** Allocates raw bytes.
**Logic:** Evaluates an `ALLOC` opcode. The VM shifts its `heap_ptr` across the simulated 1MB `bytearray` heap, returning the integer pointer address and tracking the allocation size.

### `free(ptr)`
**Use:** Deallocates raw bytes.
**Logic:** Erases the pointer from the active allocations tracker in the VM, simulating a native memory free. (In a true native compiler, maps directly to OS `free()`).

### `data`
**Use:** Defines raw C-style structs.
**Logic:** Defines a contiguous block definition. Calling `DataName()` evaluates a `NEW` struct instance on the stack. High-level ARC does *not* recursively manage struct internals natively, requiring careful memory design.

---

## Built-In Functions

### `sizeof(var)`
**Use:** Gets the memory size in bytes.
**Logic:** Evaluates a `SIZEOF` opcode. The VM checks if the variable is a tracked heap pointer (returning allocated bytes), an integer (returns 4), a string (returns length), or an object (returns property count * 4).

### `len(var)`
**Use:** Gets the logical element count.
**Logic:** Evaluates a `LEN` opcode. Determines the underlying Python-backed length of the string, list, or array representation on the stack.