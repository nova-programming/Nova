# Nova Optimization Plan

## Goal: Match C/C++ performance

## Benchmark Baseline

| Benchmark | Nova | C (-O3) | Gap |
|---|---|---|---|
| fib(30) recursive | ~0.025s | 0.001s | 25× |
| sum_to(100k) loop | <0.001s | <0.0005s | ~2× |
| primes(10000) | <0.001s | <0.0005s | ~2× |
| float chain(100k) | <0.001s | <0.0005s | ~2× |

The 25× gap on fib is the target — it represents unoptimized function call overhead and stack-spilling codegen. The other tests are already within ~2×.

---

## Phase 1: Peephole Optimizer (Week 1)
**Impact: ~1.5–2× on all code. Effort: low (~50 lines per codegen).**

A post-pass over the emitted assembly before writing it out. Pattern-match adjacent lines:

| Pattern | Replace with | Saves |
|---|---|---|
| `push eax`<br>`pop ebx` | `mov ebx, eax` | 1 mem op |
| `push N`<br>`pop eax` | `mov eax, N` | 1 mem op |
| `push [ebp±N]`<br>`pop eax` | `mov eax, [ebp±N]` | 1 mem op |
| `push 0`<br>`pop eax` | `xor eax, eax` | 1 mem op + smaller |
| `push eax`<br>`...`<br>`pop eax` | (eliminate pair) | 2 mem ops |

**Implementation:**
- Add `peephole(state)` function in `stdlib/codegen.nv` and `compiler/codegen_x86.py`
- Called once after all code is emitted, before assembly output
- Iterates `asm_lines`, applies patterns, writes optimized lines

**Files:**
- New: `stdlib/peephole.nv` (Nova), `compiler/peephole.py` (Python)
- Modify: `stdlib/codegen.nv` (call peephole before output), `compiler/codegen_x86.py`

**Verification:** fib(30) should drop from ~0.025s to ~0.015s.

---

## Phase 2: Smarter BinOp Emission (Week 2–3)
**Impact: ~2–3× on arithmetic-heavy code. Effort: medium (~100 lines per codegen).**

Current pattern for `a + b`:
```
mov eax, [ebp-a]   # load a
push eax
mov eax, [ebp-b]   # load b
push eax
pop ebx
pop eax
add eax, ebx
push eax           # result back to stack
```

The redundancy: every sub-expression result goes to the stack, then right back into a register.

**New approach:** For leaf expressions (Variable, Number), compile directly into a target register instead of pushing.

Change `compile_expr` to accept an optional `target_reg` parameter:
- If target is `"eax"` and node is Variable: `mov eax, [ebp-offset]` (no push)
- If target is `"ebx"` and node is Number: `mov ebx, N` (no push)
- If target is not specified or expression is complex: existing behavior (push to stack)

For `left + right`:
1. Compile left into eax
2. Compile right into ebx (if simple leaf)
3. `add eax, ebx` (result in eax, no push unless needed by parent)

This eliminates ~50% of push/pop pairs in arithmetic chains.

**Nested expressions** (`a + b + c`):
- Old: `push a; push b; pop ebx; pop eax; add; push eax; push c; pop ebx; pop eax; add; push eax` (14 instr)
- New: `mov eax, a; mov ebx, b; add eax, ebx; mov ebx, c; add eax, ebx; push eax` (6 instr)

**Float handling:** Same approach but with x87: `fld [ebp-a]; fld [ebp-b]; faddp; fstp [esp]`

**Files:**
- Modify: `stdlib/codegen_expr.nv`, `compiler/codegen_x86.py`

**Verification:** fib(30) should drop from ~0.015s to ~0.005s. Simple arithmetic loops should see 2–3× speedup.

---

## Phase 3: Variable-to-Register Promotion (Week 3–4) - ✅ DONE
**Impact: ~2–3× on variable-heavy code. Effort: high (~200 lines per codegen).**

Currently every variable access goes through `[ebp ± N]` — even hot loop counters.

**Approach:** Identify "hot" local variables in each function and assign them to callee-saved registers (`ebx`, `esi`, `edi`). 

**Heuristic:** Variables that are:
- Written and read within the same loop
- Used as loop counters (`i` in `while i < n`)
- Accumulators (`s` in `s = s + i`)

**Implementation:**
1. Add `reg_vars: list` to `CodegenState` mapping variable names to registers
2. In `scan_vars` (or a new `analyze_vars` pass), identify variables that would benefit from register assignment
3. In `compile_function`, add save/restore for the chosen callee-saved registers in prologue/epilogue
4. In Variable read/write: if variable is in a register, emit register ops instead of `[ebp±N]`
5. Fall back to stack for all other variables

**Example for `sum_to(n)`:**
```
# Old:
    mov [ebp-4], 0      # s = 0 (stack)
    mov [ebp-8], 0      # i = 0 (stack)
loop:
    mov eax, [ebp-8]    # load i
    cmp eax, [ebp+8]    # compare with n
    jg end
    mov eax, [ebp-4]    # load s
    add eax, [ebp-8]    # add i
    mov [ebp-4], eax    # store s
    inc [ebp-8]         # or: mov eax,[ebp-8]; inc eax; mov [ebp-8],eax
    jmp loop

# New: s in esi, i in edi
    xor esi, esi        # s = 0 (in register)
    xor edi, edi        # i = 0 (in register)
loop:
    cmp edi, [ebp+8]    # compare with n
    jg end
    add esi, edi        # s += i
    inc edi             # i++
    jmp loop
end:
    mov eax, esi        # return s
```

From 13 instr (with memory ops) to 7 instr (all register). ~2× faster on loops.

**Files:**
- Modify: `stdlib/codegen.nv` (CodegenState, compile_function), `stdlib/codegen_expr.nv` (Variable read/write), `stdlib/codegen_stmt.nv` (Assignment)
- Modify: `compiler/codegen_x86.py` (same changes)

**Verification:** sum_to(100k) and primes(10000) should drop to near-zero time. fib(30) should improve as local var `n` stays in a register across calls.

---

## Phase 4: Small Function Inlining (Week 4–5)
**Impact: ~1.5× on call-heavy code. Effort: medium (~150 lines per codegen).**

Functions like `is_prime`, `abs`, `min` are called thousands of times with full call/ret overhead.

**Approach:** Inline functions that:
- Are < ~10 lines of AST nodes
- Have no recursion
- Are not exported/marked `@export`

**Implementation:**
1. In `compile_function`, when encountering a Call to an eligible function, emit the function body directly into the caller with replaced parameter references
2. Replace parameter variable accesses with stack-offset accesses to the caller's argument pushes
3. Rename labels to avoid collisions

**Files:**
- Modify: `stdlib/codegen.nv`, `compiler/codegen_x86.py`

**Verification:** `is_prime` inlining eliminates ~2M call/ret pairs in the primes benchmark. fib(30) unaffected (recursive).

---

## Phase 5: Frame Pointer Optimization (Week 5)
**Impact: ~1.2–1.5×. Effort: medium (~100 lines).**

Currently `ebp` is used exclusively as frame pointer. Free it by tracking stack offsets relative to `esp`.

**Implementation:**
- Skip `push ebp; mov ebp, esp` in prologue
- Track all local offsets as positive from `esp`
- Adjust `[ebp ± N]` references to `[esp + N]`
- Saves 2 instructions per function call + frees `ebp` as a GP register (add to Phase 3 pool)

**Files:**
- Modify: `stdlib/codegen.nv`, `stdlib/codegen_expr.nv`, `compiler/codegen_x86.py`

---

## Expected Results After All Phases

| Benchmark | Nova (current) | Nova (optimized) | C (-O3) | Gap |
|---|---|---|---|---|
| fib(30) | ~0.025s | ~0.003s | 0.001s | ~3× |
| sum_to(100k) | <0.001s | <0.0002s | <0.0005s | ~1× |
| primes(10000) | <0.001s | <0.0002s | <0.0005s | ~1× |
| float chain(100k) | <0.001s | <0.0002s | <0.0005s | ~1× |
| **Total** | **~0.030s** | **~0.004s** | **~0.002s** | **~2×** |

The remaining 2× gap vs C -O3 is from advanced optimizations Nova won't get:
- SSA form / GVN / PRE
- Auto-vectorization (SIMD)
- Instruction scheduling for pipelining
- Profile-guided optimization

But **within 2× of GCC -O3** is an excellent place for a self-hosted compiler.

---

## Bootstrap Integrity

Each phase MUST:
1. Both Python and Nova codegens updated (not one without the other)
2. Compile: `python main.py build tests/bench.nv` → run and verify output
3. Self-hosted compile: `.\nova_main.exe build tests/bench.nv` → run and verify same output
4. Bootstrap: `python main.py build nova_main.nv && .\nova_main.exe build nova_main.nv`
5. Commit: `.\nova_main.exe build nova_main.nv && .\nova_main.exe build tests/hello.nv`
