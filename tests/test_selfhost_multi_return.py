"""Regression tests for multi-return / unpack-assign in the self-hosted compiler.

Self-hosted had zero support for `return a, b, c` (MultiReturn) or `a, b = f()`
(UnpackAssign) at all -- stdlib/parser.nv never parsed the grammar, so these were simply a
missing feature, not a bug. Added support across the whole pipeline (parser, type checker,
scan_vars/register-allocation, codegen) for x86_64; mirrored to ARM64 for policy ("both
codegens must stay in step", AGENTS.md) but the ARM64 side is unverified beyond compiling
cleanly through the self-hosting chain and cross-assembling with clang -- there is no way to
execute ARM64 output in this environment, and self-hosted's `-arch` flag cannot dynamically
pick a codegen backend at runtime (see codegen_native_arch's comment in
stdlib/backend/x86_64/codegen.nv), only at this compiler's own build time, so there is no
ARM64-targeting nova.exe to run these tests against either.

Mirrors bootstrap/compiler/backend/x86_64/codegen.py's existing MultiReturn/UnpackAssign
design: value[0] is the normal, ABI-compatible return value; values[1:] (up to 8) go through
a static `_nova_multi_ret` buffer. One deliberate difference from the Python-bootstrap
backend: self-hosted's MultiReturn runs deferred cleanups before returning (bootstrap's
x86_64 MultiReturn doesn't), to stay consistent with self-hosted's own Return case, which
already does.
"""


def test_two_values(selfhost_run):
    r, _ = selfhost_run(
        'def divmod(a, b) {\n'
        '    q = a / b\n'
        '    r = a % b\n'
        '    return q, r\n'
        '}\n'
        'q, r = divmod(17, 5)\n'
        'print(q)\n'
        'print(r)\n',
        "selfhost_mr_two",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["3", "2"]


def test_three_values(selfhost_run):
    r, _ = selfhost_run(
        'def three() {\n'
        '    return 10, 20, 30\n'
        '}\n'
        'a, b, c = three()\n'
        'print(a)\n'
        'print(b)\n'
        'print(c)\n',
        "selfhost_mr_three",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["10", "20", "30"]


def test_underscore_skips_a_target(selfhost_run):
    r, _ = selfhost_run(
        'def pair() {\n'
        '    return 7, 8\n'
        '}\n'
        'x, _ = pair()\n'
        'print(x)\n',
        "selfhost_mr_underscore",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "7"


def test_defer_runs_before_a_multi_return(selfhost_run):
    """Regression: a naive port of the Python-bootstrap x86_64 backend's MultiReturn (which
    never calls defer_emit_down_to) would make `defer` silently not fire for any function
    that uses `return a, b` -- inconsistent with the same function's single-value Return,
    which already runs defers. Checks the defer's side effect (the print) actually happens,
    and happens before the values it deferred around are read by the caller."""
    r, _ = selfhost_run(
        'def with_defer(n) {\n'
        '    defer { print("cleanup") }\n'
        '    return n, n * 2\n'
        '}\n'
        'x, y = with_defer(7)\n'
        'print(x)\n'
        'print(y)\n',
        "selfhost_mr_defer",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["cleanup", "7", "14"]
