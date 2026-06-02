# Nova Roadmap

## Near-Term Goals

### 1. Cross-Platform Abstractions (`os_*.nv`)
Develop a unified OS-layer interface (`system.nv`) that automatically swaps out implementations based on whether the host is Windows (`os_win.nv`), Linux (`os_linux.nv`), or macOS (`os_mac.nv`), completely hiding specific configs from end-users.

### 2. The "Galaxy" Package Manager
Design and architect a central repository and library manager (akin to `pip` or `cargo`) to allow developers to build, pull, and distribute pure Nova codebase packages effortlessly.

### 3. Small Function Inlining (Phase 4)
Implement advanced compiler optimizations to inline extremely short, non-recursive functions, entirely eliminating call/ret overhead for utility methods.

## Long-Term Goals

### 64-bit x86_64 Support
- Update codegen to emit 64-bit registers (`rax`/`rbx`/`rcx`)
- Adopt System V AMD64 or Windows x64 calling convention
- Implement 16-byte stack alignment for external calls

### Self-Hosted VM
- Rewrite the Python bytecode VM in Nova
- `nova dev` mode runs entirely within native Nova binary
