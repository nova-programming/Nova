"""Regression tests for the self-hosted x86_64 backend's frequency-weighted register
allocation (stdlib/backend/x86_64/codegen.nv's count_var_refs/top_register_candidates,
mirroring the same change in bootstrap/compiler/backend/x86_64/codegen.py).

Mirroring the Python-bootstrap fix into the self-hosted backend surfaced two real bugs that
the Python version's generic AST reflection never exposed:

1. count_var_refs's generic fallback called len(node.args)/len(node.else_body) on every
   node kind reaching it. AstNode (stdlib/parser.nv) is a tagged-union struct where those
   list-typed fields default to a bare 0 (not an empty list) for kinds that never populate
   them -- len(0) segfaults rather than returning 0. Fixed with explicit `!= 0` guards.
2. compile_function's parameter argument-copy step read state.local_var_regs[p] and
   state.local_vars[p] *positionally*, assuming parameters always occupy the first
   len(node.params) slots of those parallel arrays (true only because the original code
   always registered parameters before any other local). Claiming registers for hot
   non-param locals first breaks that assumption: a parameter and an unrelated hot local
   silently collided on the same physical register, corrupting both. Fixed by switching to
   the existing name-keyed find_var_reg/find_var_offset lookups instead.
"""
import pytest


def test_param_and_hot_locals_dont_collide_on_a_register(selfhost_run):
    """Regression (bug 2 above): a parameter (n) plus several locals declared before the
    hot loop (a, b, c, d) that are barely used, while total/x/y/z/i are the actual hot
    variables. Before the fix, work(5) computed 5380300355189866506 instead of 25 -- n and
    a hot local silently shared a register after the positional-index assumption broke."""
    src = (
        "def work(n) {\n"
        "    a = 1\n"
        "    b = 2\n"
        "    c = 3\n"
        "    d = 4\n"
        "    total = 0\n"
        "    x = 0\n"
        "    y = 0\n"
        "    z = 0\n"
        "    i = 0\n"
        "    while i < n {\n"
        "        x = x + i\n"
        "        y = y + x\n"
        "        z = y - x\n"
        "        total = total + z\n"
        "        i = i + 1\n"
        "    }\n"
        "    return total + a + b + c + d\n"
        "}\n"
        "print(work(5))\n"
    )
    r, _ = selfhost_run(src, "regalloc_param_collision")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "25"


def test_multiple_params_and_many_locals_stay_correct(selfhost_run):
    """A second shape of the same bug: several parameters (which used to always win the
    first registers in declaration order) competing with several hot locals for the same
    small register set, plus a nested loop so loop-depth weighting is also exercised."""
    src = (
        "def combo(p1, p2, p3) {\n"
        "    unused1 = 10\n"
        "    unused2 = 20\n"
        "    acc = 0\n"
        "    i = 0\n"
        "    while i < p1 {\n"
        "        j = 0\n"
        "        while j < p2 {\n"
        "            acc = acc + i * p3 + j\n"
        "            j = j + 1\n"
        "        }\n"
        "        i = i + 1\n"
        "    }\n"
        "    return acc + unused1 + unused2 + p1 + p2 + p3\n"
        "}\n"
        "print(combo(4, 3, 2))\n"
    )

    def expected(p1, p2, p3):
        acc = 0
        for i in range(p1):
            for j in range(p2):
                acc += i * p3 + j
        return acc + 10 + 20 + p1 + p2 + p3

    r, _ = selfhost_run(src, "regalloc_multi_param")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == str(expected(4, 3, 2))


def test_count_var_refs_does_not_crash_on_rich_expressions(selfhost_run):
    """Regression (bug 1 above): count_var_refs's generic fallback must not crash on node
    kinds whose .args/.else_body are unset (BinOp, Call, DataFieldAccess, ArrayIndex,
    MethodCall, nested calls, list/dict literals, if/elif/else). Exercises every kind listed
    in codegen_expr.nv's compile_expr dispatch that's reachable from ordinary syntax."""
    src = (
        "data Point { x: int y: int }\n"
        "def helper(a, b) { return a + b * 2 }\n"
        "def run(n) {\n"
        "    p = Point(x=1, y=2)\n"
        "    xs = [1, 2, 3]\n"
        "    d = {\"k\": 5}\n"
        "    total = 0\n"
        "    i = 0\n"
        "    while i < n {\n"
        "        if helper(xs[0], p.x) > 0 and d.get(\"k\") == 5 {\n"
        "            total = total + helper(i, p.y) + xs[i % 3]\n"
        "        } else {\n"
        "            total = total - 1\n"
        "        }\n"
        "        i = i + 1\n"
        "    }\n"
        "    return total\n"
        "}\n"
        "print(run(6))\n"
    )
    r, _ = selfhost_run(src, "regalloc_rich_exprs")
    assert r.returncode == 0, r.stdout + r.stderr
