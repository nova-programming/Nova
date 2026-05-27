# Agent Session Summary

## Current Milestone
- **COMPLETED: Diagnostics — Line-Number Error Messages in both Python and Nova pipelines.**
- **COMPLETED: PE crash (SIB byte) fix — Gen 2 standalone executables run flawlessly.**

## What Was Accomplished

### Phase 1: PE Crash Fix (SIB Byte Bug)
1. **Identified root cause of 0xC0000005 crash**: Not linker padding — PE was structurally perfect.
2. **Found SIB byte bug**: `encode_modrm_mem_reg` in `stdlib/assembler_encode.nv` omitted the required `0x24` SIB byte when encoding `[esp + disp]`.
3. **Instruction swallowing**: Missing SIB caused CPU to misinterpret the next instruction (`push eax` = `0x50`) as displacement for `lea`.
4. **Stack corruption cascading into WriteFile**: Shifted stack args caused OS to treat the call as Overlapped I/O, corrupting the stack frame and outputting `\x03\x01\x00\x00` garbage.
5. **Fix**: Append `36` (`0x24`) SIB byte when `mem_base == 4` (`esp`).

### Phase 2: Line-Number Error Messages
6. **Python tokenizer** (`lexer/tokenizer.py`): Added `line_num` tracking — increments on `\n`, sets `line_num` on every token tuple (3rd element).
7. **All AST nodes** (`ast/nodes.py`): Every constructor now accepts `line=0` default parameter and stores `self.line = line`.
8. **Python parser** (`parser/parser.py`):
   - Every `parse_*` method captures `line` from the current token and passes it to AST node constructors
   - `eat()` now raises: `[line N] Expected X, got Y ('val')` instead of raw token tuple
9. **Python codegen** (`compiler/codegen_x86.py`):
   - All 4 `raise Exception()` sites now include `[line N]` prefix via `getattr(node, 'line', '?')`
   - `compile_stmt()` emits `# line N` comments in generated assembly for debugging
10. **Nova lexer** (`stdlib/lexer.nv`): Added `line: int` field to `Token` struct; `line_num` tracked through tokenizer; `tok.line = line_num` on every token.
11. **Nova parser** (`stdlib/parser.nv`):
    - Added `line: int` field to `AstNode` struct
    - Added `filename: string` to `ParserState`
    - Error messages now show `Error [filename:line]: expected X but got Y`
12. **Nova compiler** (`stdlib/compiler.nv`): Passes filename to `parse()` for error reporting context.

### Phase 3: Bug Fixes Found During Work
13. **`_realloc` HeapReAlloc flags**: Changed `push 0` → `push 8` (HEAP_REALLOC_IN_PLACE_ONLY) — previous `HEAP_NONE` could move the pointer, breaking the caller's expectation.
14. **`_fopen` write mode**: Added `"w"` mode detection — read-only `GENERIC_READ + OPEN_EXISTING` was used for all opens; write mode now uses `GENERIC_WRITE + CREATE_ALWAYS`.

## Full Verification Chain
- `python main.py build nova_main.nv` → `nova_main.exe` (Gen 1 via GCC) ✅
- `.\nova_main.exe build nova_main.nv` → self-hosts (60k+ asm lines), exits 0 (Gen 2) ✅
- `.\nova_main.exe build tests\hello.nv` → `hello.exe` prints "Hello from Nova!" ✅

## State
- **Status: COMPLETE** — Full self-hosted bootstrap working, error messages include line numbers in both Python and Nova pipelines.
- Pre-existing: Gen 1 PE `.data` alignment issue (garbage bytes before output) — not affecting correctness.

## Key Files Modified
- `stdlib/assembler_encode.nv` — SIB byte fix
- `lexer/tokenizer.py` — line tracking
- `ast/nodes.py` — line field on all nodes
- `parser/parser.py` — line-aware errors
- `compiler/codegen_x86.py` — line in exceptions + asm comments
- `stdlib/lexer.nv` — line field on Token, line tracking
- `stdlib/parser.nv` — line field on AstNode, filename in state, line-aware errors
- `stdlib/codegen.nv` — `_realloc` flag fix, `_fopen` write mode
- `stdlib/compiler.nv` — filename passed to parse()

## Handover Command
```powershell
.\nova_main.exe build tests\hello.nv ; tests\hello.exe
```
