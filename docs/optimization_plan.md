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
- Modify: `stdlib/backend/x86_64/codegen.nv`, `stdlib/backend/arm64/codegen.nv`
- Bootstrap: `bootstrap/compiler/backend/x86_64/codegen.py`, `bootstrap/compiler/backend/arm64/codegen.py`

**Verification:** `is_prime` inlining eliminates ~2M call/ret pairs in the primes benchmark. fib(30) unaffected (recursive).

---

## Phase 5: Frame Pointer Optimization (Week 5)
**Impact: ~1.2–1.5×. Effort: medium (~100 lines).**

Currently `rbp` is used exclusively as frame pointer. Free it by tracking stack offsets relative to `rsp`.

**Implementation:**
- Skip `push rbp; mov rbp, rsp` in prologue
- Track all local offsets as positive from `rsp`
- Adjust `[rbp ± N]` references to `[rsp + N]`
- Saves 2 instructions per function call + frees `rbp` as a GP register (add to Phase 3 pool)

**Files:**
- Modify: `stdlib/backend/x86_64/codegen.nv`, `stdlib/backend/x86_64/codegen_expr.nv`, `bootstrap/compiler/backend/x86_64/codegen.py`

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
3. Self-hosted compile: `.\nova.exe build tests/bench.nv` → run and verify same output
4. Bootstrap: `python main.py build nova.nv && .\nova.exe build nova.nv`
5. Commit: `.\nova.exe build nova.nv && .\nova.exe build tests/hello.nv`
