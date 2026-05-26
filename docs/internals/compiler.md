# Nova Native Compiler Internals (`stdlib/compiler.nv` & `nova_main.nv`)

The compilation orchestration logic represents the overarching entry point of the entire self-hosting bootstrap pipeline. It takes the independent components (tokenizer, parser, codegen, linker) and ties them into a cohesive toolchain.

## Current Python Driver (`main.py`)
Historically, `main.py` parses command line arguments and either directs them to `vm.py` (for interpretation) or `codegen_x86.py` (for compilation via `gcc`). This allows Nova code to be tested while the native tools are still being built.

## Native Compiler Driver (`nova_main.nv`)
The ultimate goal of Nova is self-dependency. The native `nova.exe` CLI executable replaces `main.py`.

1. **Initialization:**
   It invokes `os.sys_get_args()` from `os_win.nv` to natively parse Windows command-line arguments.
2. **File I/O:**
   It uses `os.read_file()` to load the target `.nv` source code into a string buffer in memory.
3. **Lexical Analysis:**
   The source string is passed to `tokenizer.tokenize()`, creating a list of tokens.
4. **Syntax Analysis:**
   The tokens are passed to `parser.init_parser()` and `parser.parse()`, generating the AST (Abstract Syntax Tree).
5. **Code Generation:**
   The AST is fed to `codegen.generate_assembly()`. At present, this outputs NASM-compatible assembly strings, which are then passed to `gcc` via a `system()` shell call.
6. **Self-Hosting (Future):**
   Once `linker.nv` is fully integrated with `codegen.nv`, `codegen` will emit raw binary byte lists directly into `linker.link()`, bypassing NASM and GCC entirely.

## Modularity
Because all the logic resides natively inside Nova (`tokenizer.nv`, `parser.nv`, `codegen.nv`), any future improvements to the compiler (e.g., adding classes, enums, type-check passes) can be written purely in Nova itself, achieving a self-sustaining ecosystem without needing Python.
