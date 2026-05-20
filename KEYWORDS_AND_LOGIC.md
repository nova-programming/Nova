# KEYWORDS & LOGIC ARCHITECTURE

Nova aims to simplify programming by blending high-level ease with low-level power. Here is the concise breakdown of the keywords, their backend mechanics, and short examples.

---

## High-Level Keywords

### `def`
**Use:** Defines functions/methods.
**Logic:** Compiles to a bytecode block. The VM creates a local `Frame` for isolated variables.
```nova
def add(a, b) { return a + b }
print(add(2, 3)) # Output: 5
```

### `class`
**Use:** Defines an OOP blueprint.
**Logic:** Creates a metadata definition. Calling `ClassName()` executes a `NEW` opcode, allocating a dictionary-backed Virtual Machine `Instance`. If `__init__` is defined, the VM automatically executes it immediately.
```nova
class Dog {
    name
    def __init__(n) { self.name = n }
}
d = Dog("Rex")
```

### `self`
**Use:** Refers to the current class instance.
**Logic:** During a method call, the VM attaches the parent object to the `Frame`. `LOAD_SELF` pushes this context instance onto the stack for fast property access.
```nova
# See 'class' example above. `self.name` modifies the active instance.
```

### `import`
**Use:** Loads external Nova modules or native C libraries (FFI).
**Logic:** Compiles additional Nova files. When used with strings (`import "c" as libc`), it triggers the VM to use Python's `ctypes` to dynamically load the `.so` or `.dll` library natively.
```nova
@raw {
    import "c" as libc
    libc.puts("Hello OS!") # Output: Hello OS!
}
```

### `if`, `else`, `while`, `for`
**Use:** Control flow logic.
**Logic:** Evaluates conditions and uses `JUMP` and `JUMP_IF_FALSE` opcodes to skip bytecode blocks.
```nova
for i = 1 to 2 step 1 { print(i) }
# Output:
# 1
# 2
```

### `print`
**Use:** Outputs to standard console.
**Logic:** Evaluates a specific opcode that natively bridges to the console out stream.
```nova
print("Nova") # Output: Nova
```

---

## Low-Level Keywords (`@raw` block)

### `@raw`
**Use:** Enters the unsafe, high-performance low-level mode.
**Logic:** A directive that suspends high-level constraints. Conceptually grants the developer direct CPU/memory logic control for bottlenecks.
```nova
@raw {
    # memory management unlocked
}
```

### `@export`
**Use:** Bridges `@raw` variables/functions to high-level code.
**Logic:** Exposes C-linkage pointers or structures out to the safe ARC memory space to be managed as global singletons.

### `alloc(size)`
**Use:** Allocates raw contiguous bytes in memory.
**Logic:** Evaluates `ALLOC`. The VM shifts its `heap_ptr` across a simulated 1MB `bytearray` heap, returning an integer pointer.
```nova
@raw { ptr = alloc(4) }
```

### `free(ptr)`
**Use:** Deallocates raw bytes.
**Logic:** Erases the pointer from the active allocations tracker in the VM, freeing the space natively.
```nova
@raw { free(ptr) }
```

### `data`
**Use:** Defines raw C-style memory structures.
**Logic:** Defines a contiguous block definition. ARC explicitly ignores struct internals for max speed.
```nova
data Point { x: int y: int }
@raw { p = Point() }
```

---

## Built-In Functions

### `sizeof(var)`
**Use:** Gets the memory size in bytes.
**Logic:** Evaluates a `SIZEOF` opcode. The VM checks if the variable is a tracked heap pointer (returns bytes), an integer (4), a string (length), or an object (property count * 4).
```nova
@raw { ptr = alloc(8); print(sizeof(ptr)) } # Output: 8
```

### `len(var)`
**Use:** Gets the logical element count.
**Logic:** Evaluates `LEN`. Determines the underlying representation length on the stack.
```nova
print(len("Cat")) # Output: 3
```
