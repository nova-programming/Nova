# Nova — agent guide

Mission: bridge the gap between Python-like readability/ease and C/C++-like performance/control,
**keeping Python-like syntax**. Judge every change by that: easier to read/use, faster, or more low-level
control — without making the surface syntax less Pythonic.

## Policy
- x86 (32-bit) is removed; only x86_64 and arm64 are maintained.
- The Python bootstrap (`bootstrap/`) is frozen for new features. Language features go into `stdlib/` (Nova);
  bootstrap gets only fixes needed for self-hosting. (Both codegens must stay in step for features that already exist.)
- Anything that changes value representation or the calling ABI needs a full Stage 1 → Stage 2 self-host + test cycle.
- Every fix ships with a regression test. VM-only features (e.g. `call()`) must be rejected by native builds.
- Galaxy installs must verify SHA-256 hashes; `GALAXY_ALLOW_UNVERIFIED=1` is an explicit opt-out. Direct
  `owner/repo` installs are unverified by definition.
- `alloc`/`free`/`.ptr`/`.as_list`/`@raw` cross between ARC-managed and manual memory. Read
  `docs/internals/ownership.md` before touching any of them or adding a new unsafe API.

## Commands
```bash
python -m pytest -q                      # full suite (pytest also runs unittest-style tests)
python bootstrap/main.py dev file.nv     # VM mode, no GCC
python bootstrap/main.py build file.nv   # native (needs 64-bit GCC; bundled one lives in %LOCALAPPDATA%\nova\gcc)
pip install -e .                         # dev install; gives `nova` and `galaxy`
```
On Windows a 32-bit `C:\MinGW` GCC on PATH cannot build `runtime.c`; use the 64-bit one.

## Where things are
See README "Project Structure". Design docs: `docs/features.md`, `docs/internals/`, `docs/optimization_plan.md`,
`ROADMAP.md`. Historical session notes: `docs/AGENT_LOG.md`.

## Windows (stdlib/ui.nv)
- One library for desktop and Nova OS: `import ui`. `ui_backend` resolves to `ui_host` (Win32 GDI) or `ui_os` (system calls)
  in `compiler.nv` (`resolve_imports`), like `os_impl`. The old `gui` widget tree and NSS were removed.
- Widgets are immediate mode (see KEYWORDS_AND_LOGIC.md section 9). New display-list ops must be added to BOTH renderers:
  `stdlib/ui_host.nv` and `baremetal_os/ui/clients.nv`.
- **Syntax Rules**: Nova list literals `[...]` do not support trailing commas before `]`. Fixed arity is strictly enforced on all function calls.

