# Nova Virtual Machine Optimizations

This document tracks the algorithmic optimizations implemented in the Nova compiler and bytecode Virtual Machine to ensure high performance without counter-negatives.

## 1. Stack Leak Prevention (`POP` Opcode)
**Feature:** Added a new `POP` opcode to the `OpCode` enum.
**Optimization:** Expressions like standalone function calls (`Call`) or method calls (`MethodCall`) that are executed for side-effects without their return values being used previously left unused values on the Virtual Machine stack. By emitting a `POP` opcode immediately after evaluating these standalone expressions, the unused return values are efficiently popped off the stack, preventing stack memory leaks during long-running iterations or loops.

## 2. Best-Fit Free List Memory Allocator
**Feature:** Enhanced the `ALLOC` and `FREE` opcodes within the Virtual Machine.
**Optimization:** Implemented a best-fit free list memory allocator to manage `@raw` block allocations. Instead of endlessly shifting the heap pointer, freed pointers are now tracked along with their allocation sizes in a `free_list`. During allocation, the `free_list` is searched to find the smallest previously freed block that meets or exceeds the required size. This heavily mitigates memory fragmentation and improves memory reuse without incurring significant algorithmic overhead, extending the effective lifecycle of the fixed-size `bytearray` simulated heap.

## 3. Safe Polymorphic Caching
**Feature:** Upgraded method resolution logic in the `CALL_METHOD` opcode.
**Optimization:** Instead of dynamically formatting strings (e.g., `f"{instance.class_name}.{method_name}"`) and querying the function table on every method call, the VM now uses an Inline Method Cache (`self.method_cache`). Method resolutions are cached using a `(instance.class_name, method_name)` tuple as the key, allowing subsequent invocations to retrieve the method's `func_meta` execution metadata in O(1) time. This bypasses string construction and secondary lookups, drastically speeding up Virtual Machine object-oriented execution speed.
