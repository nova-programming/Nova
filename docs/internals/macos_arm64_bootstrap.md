# macOS ARM64 Self-Hosted Bootstrap Investigation

## Current Status
Nova compiles and runs on macOS ARM64 **via the Python bootstrap** (`python bootstrap/main.py build hello.nv`).
The **self-hosted bootstrap** (`./nova-stage1 build test.nv`) crashes with SIGSEGV/SIGBUS after type checking, during code generation.

## Key Findings

### What Works
- `./nova-stage1 --version` — prints "Nova v0.9.0", exits 0 (startup + arg parsing + print works)
- Full Python bootstrap pipeline (tokenize → parse → type-check → codegen → assemble → link)
- All 246+ tests pass on x86_64 (Windows/Linux) and ARM64 (macOS) via Python bootstrap

### What Crashes
- `./nova-stage1 build test.nv` — SIGSEGV (exit 139) at `CF:after_tc` marker
- Crash is **after type checking completes** but **before codegen finishes**
- Not deterministic: some CI runs crash during `--version` instead (heap layout sensitive)

### Debug Marker Trace (from CI Run #181)
```
CF:begin
CF:cache_path
CF:load_cache
CF:file_size
CF:cache_key
CF:before_open
CF:after_open
CF:after_read
CF:after_close
CF:after_tokenize
CF:after_parse
CF:after_imports
CF:after_tc
--- CRASH HERE ---
```

### Disassembly Analysis
- `_parse` at `0x1000154ac`, `_current_tok` at `0x100006e70`
- Both functions are structurally correct (proper prologue/epilogue, valid comparisons)
- `_current_tok`: loads `[x0]` (token struct ptr), then `[x0]` (pos), then `[x0, #8]` (data ptr), compares `pos < count`
- The crash is NOT in these functions — it's in the codegen phase

## Reproduction

### Locally (if you have macOS ARM64)
```bash
# Build stage1 using Python bootstrap
python3 bootstrap/main.py build nova.nv
mv ./nova ./nova-stage1

# Try to build a test program with stage1
./nova-stage1 build hello.nv
```

### Via CI
The `.github/workflows/ci.yml` has these debug steps for macOS:
- nm dump (first 30 symbols)
- otool -tV _main disassembly (first 30 lines)
- otool -tV _parse disassembly (first 80 lines)
- otool -tV _current_tok disassembly (first 40 lines)

To trigger: push to `main` branch. CI configuration uses `fail-fast: false` so all 3 OSes run independently.

## Debug Infrastructure

### Markers in `stdlib/compiler.nv`
The `compile_file` function has `system.file_write(2, "CF:...\n")` markers at each major phase.
To add more granular markers inside codegen, add `system.file_write(2, "CG:...\n")` calls to:
- `stdlib/backend/arm64/codegen.nv` — `generate_assembly()` function (line 478)
- `stdlib/backend/arm64/codegen_expr.nv` — individual expression handlers
- `stdlib/backend/arm64/codegen_stmt.nv` — individual statement handlers

### SIGSEGV Handler
`runtime.c` has a SIGSEGV handler that prints a backtrace:
```
SIGSEGV at IP=0x..., LR=0x...
```
IP = instruction that faulted, LR = return address (= call site of crashing function)

## Hypotheses

### Hypothesis 1 (Most Likely): Heap Corruption in Codegen
The `generate_assembly` function allocates a `CodegenState` struct and manipulates lists/dicts extensively.
A corrupted list header (count/capacity overflow) or dangling pointer could cause delayed SIGSEGV.
**Test**: Add markers inside `generate_assembly()` to narrow the crash to a specific AST node handler.

### Hypothesis 2: String Builder OOM
`str_sub()`, string concatenation, or `append()` on a string list could corrupt the heap if
the internal realloc produces a wrong new capacity.
**Test**: Check `_realloc` in runtime.c for ARM64-specific issues.

### Hypothesis 3: Inline Assembly Corruption
The ARM64 `@raw` blocks or `.rept`/`.endr` assembler directives in the generated assembly
could produce corrupt code that crashes at runtime rather than at assembly time.
**Test**: Compare `nova.s` from Python bootstrap vs what stage1 produces.

## Next Steps

### Immediate
1. Add `CG:` markers inside `generate_assembly()` in `stdlib/backend/arm64/codegen.nv`:
   - Before function compilation loop
   - After function compilation loop
   - Before/after key codegen sections (StructData, TopLevel, emit calls)

2. Add fine-grained markers in `compile_expr` and `compile_stmt` for the ARM64 backend

3. Push to CI and identify exact instruction that crashes

### If Hypothesis 1
4. Add markers around specific expression handlers (BinOp, Call, MethodCall, etc.)
5. Focus on the expression just before the crash

### If Hypothesis 2
6. Review `_realloc` and `_append` in `runtime.c` for ARM64 edge cases
7. Check `_str_sub` for off-by-one errors with 64-bit lengths

### If Hypothesis 3
8. Check `stdlib/assembler.nv` ARM64 encoding for correct instruction widths
9. Verify `.rept`/`.endr` expansion doesn't overflow internal buffers

## Key Files
| File | Purpose |
|------|---------|
| `stdlib/compiler.nv` | Pipeline orchestration, CF: markers here |
| `stdlib/backend/arm64/codegen.nv` | ARM64 codegen entry point, CodegenState |
| `stdlib/backend/arm64/codegen_expr.nv` | ARM64 expression codegen |
| `stdlib/backend/arm64/codegen_stmt.nv` | ARM64 statement codegen |
| `stdlib/codegen_common.nv` | Shared codegen utilities |
| `runtime.c` | C runtime (SysV ABI wrappers, heap, string ops) |
| `.github/workflows/ci.yml` | CI configuration with macOS debug steps |
| `bootstrap/compiler/backend/arm64/codegen.py` | Python bootstrap ARM64 codegen (reference implementation) |
