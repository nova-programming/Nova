# Nova Roadmap

## Near-Term Goals

### 1. Cross-Platform Abstractions (`os_*.nv`)
Develop a unified OS-layer interface (`system.nv`) that automatically swaps out implementations based on whether the host is Windows (`os_win.nv`), Linux (`os_linux.nv`), or macOS (`os_mac.nv`), completely hiding specific configs from end-users.

### 2. Galaxy Package Manager (Implemented)
Galaxy is a fully functional package manager with a Git-backed registry website, standalone CLI (`galaxy`), three trust tiers (Core/Verified/Community), template system (`galaxy init`), GitHub Issues-based publishing workflow, and GitHub Actions automation for validation/quarantine/promotion. See the [Galaxy Registry](https://galaxy-registry.vercel.app) for documentation.

### 3. Small Function Inlining (Phase 4)
Implement advanced compiler optimizations to inline extremely short, non-recursive functions, entirely eliminating call/ret overhead for utility methods.

## Completed Milestones

### 64-bit x86_64 Support (June 2026)
The codegen has been fully ported to x86_64 with:
- 64-bit registers (`rax`/`rbx`/`rcx`/`rdi`/`rsi`/`rdx`/`r8`/`r9`)
- System V AMD64 calling convention (args in `rdi`/`rsi`/`rdx`/`rcx`/`r8`/`r9`, as used by MinGW GCC)
- 16-byte stack alignment for external calls
- Self-hosting verified end-to-end — `nova.exe build nova.nv` produces a working 64-bit compiler

### Self-Hosted VM
- Rewrite the Python bytecode VM in Nova
- `nova dev` mode runs entirely within native Nova binary
