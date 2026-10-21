"""Regression test: a self-hosted nova.exe used to silently emit the WRONG architecture's
assembly instead of failing when asked to cross-compile for one it wasn't built for.

Root cause: `import codegen` (stdlib/compiler.nv) resolves to exactly one of
stdlib/backend/{x86_64,arm64}/codegen.nv, chosen once, statically, at THIS nova.exe's own
build time -- Nova has no dynamic/conditional import, unlike the Python-bootstrap backend's
runtime `from compiler.backend.arm64.codegen import ...`. So an ordinary x86_64-targeting
nova.exe (the only kind this project ever actually builds) has no ARM64 codegen compiled into
it at all. Before this fix, passing it `-arch arm64` fell through to the one backend it has
and happily emitted plain x86_64 `.intel_syntax noprefix` assembly while printing
"Generated executable" -- i.e. producing a binary for the wrong architecture while claiming
success, discovered while adding ARM64 self-hosted multi-return support and trying to verify
it via `stage1.exe build foo.nv -arch arm64 --os macos`.

Fixed by codegen_native_arch() (one per backend, returning that backend's own architecture
name) and a check at the top of compile_file (stdlib/compiler.nv) that errors instead of
mis-compiling when the requested target_arch doesn't match.
"""
import subprocess


def test_mismatched_arch_fails_loudly_instead_of_silently_mis_targeting(selfhost, tmp_path):
    stage1, work, env = selfhost

    src = tmp_path / "trivial.nv"
    src.write_text("print(1)\n", encoding="utf-8")
    out = tmp_path / "trivial_arm64_out"

    r = subprocess.run(
        [str(stage1), "build", str(src), "-arch", "arm64", "--os", "macos", "-o", str(out)],
        capture_output=True, text=True, timeout=60, cwd=work, env=env,
    )
    assert r.returncode != 0, "expected the arch mismatch to fail the build, but it exited 0"
    assert "x86_64" in r.stdout and "arm64" in r.stdout, r.stdout + r.stderr
    assert not out.exists(), "compiler produced an output binary despite the arch mismatch"
    # The assertion that matters most: no .s file masquerading as arm64 output should be
    # produced by a binary that cannot actually generate arm64 instructions.
    generated_s = tmp_path / "trivial.nv.s"
    assert not generated_s.exists(), "compiler produced an .s file despite the arch mismatch"


def test_matching_arch_still_builds_normally(selfhost_run):
    r, _ = selfhost_run("print(42)\n", "selfhost_arch_guard_ok")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "42"
