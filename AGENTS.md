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
