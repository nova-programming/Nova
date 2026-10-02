# Nova Optimization Plan

## Goal: Match C/C++ performance

## Measured Results (Oct 2026, x86_64 Windows, self-hosted compiler vs `gcc -O2`)

The older "25x on fib" figure was stale. Measured steady-state, best of 8:

| Benchmark | Before | After call fast path + peephole | C -O2 |
|---|---|---|---|
| fib(38) recursive | ~0.44-0.48s | ~0.32-0.35s | ~0.14-0.16s |
| `tests/bench_heavy.nv` (fib 35 + sum 10M + primes 50k) | ~0.21s | ~0.155s | n/a |

Compare-and-branch fusion (Oct 2026, same machine, loaded, interleaved best-of-8): fib(38)
0.576s -> 0.505s while `gcc -O2` ran 0.27-0.29s, i.e. the gap went from about 2.1x to 1.8x.
`if`/`while` conditions now compile to `cmp; jCC` instead of `cmp; setCC; movzx; cmp 0; jcc`
(peephole, restricted to if/while exit labels because `and`/`or` reuse the boolean in rax).
Leaf-function prologue elision was evaluated and deferred: it saves two instructions per call
only for functions that make no calls, which is a small win next to the stack-machine traffic.

Remaining fib gap is ~2.2-2.5x, dominated by the function prologue
(`push rbp; mov rbp,rsp; and rsp,-16; sub rsp,N; push r12`) and the stack-machine
expression evaluation. Done so far: Nova-to-Nova calls skip the C-interop frame
(`emit_internal_call`), and `stdlib/peephole.nv` is now wired into the x86_64 backend
(it was previously dead code). Next: leaf-function prologue elision, direct-register
argument passing, compare-and-branch fusion (`cmp; setle; movzx; cmp 0; je` -> `cmp; jg`).

---|---|---|---|
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


## Batch 7 — whole-language performance (zero surface change)

Benchmarks live in `tests/bench/*.nv` (C twins in `tests/bench/c/`); run `python tools/bench.py` (best of 3, stage-1
compiler built from the checkout, C = `gcc -O2`). Behavior is guarded by `tests/test_diff_fuzz.py` (random programs,
VM vs native) and the stage-2 tests.

Baseline before Batch 7 (same machine, quiet):

| benchmark | run (s) | C -O2 (s) | Nova/C |
|---|---|---|---|
| fib (fib(36)) | 0.137 | 0.071 | 1.93x |
| loops (60M iterations, mixed arithmetic) | 0.495 | 0.322 | 1.53x |
| primes (< 300000, trial division) | 0.095 | 0.088 | 1.09x |
| collatz (< 400000) | 0.453 | 0.127 | 3.58x |
| sieve (5M, lists) | 0.164 | - | - |
| bubble sort (3500) | 0.069 | - | - |
| matmul (130x130, flat lists) | 0.052 | - | - |
| dict counting (300k) | 0.075 | - | - |
| structs (20M field updates) | 0.183 | - | - |
| strings (40k appends) | 6.042 | - | - |

Standouts: `strings` (every `s = s + x` does four passes over both operands and the old string is never freed),
`collatz` (`% 2` and `/ 2` use `idiv`), `loops` (`%` by a constant uses `idiv`), and call-heavy `fib`.
