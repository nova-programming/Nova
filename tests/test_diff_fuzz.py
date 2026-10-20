"""Differential fuzzing: random Nova programs must print the same thing in the VM (reference semantics)
and in native builds made by the self-hosted compiler (stage 1 and stage 2).

This is the safety net for backend optimizations: it exercises register allocation (more locals than
registers), operand folding, branch fusion, leaf-function frames, calls with up to six arguments, list
indexing, and dict set/get/has over a small fixed key set (never anything depending on dict iteration
order, which the VM's Python dict and native's open-addressing table have no reason to agree on). Values
are kept in [0, 999] after every assignment and operands of - and * are reduced first, so VM (unbounded
ints, floor modulo) and native (64-bit, truncating modulo) cannot diverge on overflow or sign, and / and %
only ever see non-negative operands.

Seeds are fixed; set NOVA_FUZZ_SEED / NOVA_FUZZ_COUNT for a deeper local run.
"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_names import _vm_output  # noqa: E402

START = int(os.environ.get("NOVA_FUZZ_SEED", "1000"))
COUNT = int(os.environ.get("NOVA_FUZZ_COUNT", "14"))


class Gen:
    # Total weighted call "cost" allowed per generated program (see expr()'s "call" case).
    # Chosen generously enough to allow real call chains and loops, tight enough that the VM
    # finishes generating the reference output well within its subprocess timeout.
    CALL_BUDGET = 500

    def __init__(self, seed):
        self.r = random.Random(seed)
        self.funcs = []          # (name, nparams)
        self.lines = []
        self._uid = 0
        # A call's real runtime cost is the callee's own cost (which already accounts for
        # whatever it calls) times how many times this call site actually executes --
        # determined by the loop nesting it sits inside, not by how many times it appears in
        # the source text once. Without this, nothing stops fn5 calling fn3 inside a loop that
        # itself calls fn2 inside a loop that calls fn1/fn0 inside loops: every loop multiplies
        # the next, and the total call count explodes well past what's visible in the source
        # (seed 1079 in a 2026-10-20 run did exactly this and ran the VM reference-output step
        # past its 30s timeout, despite every individual loop bound being tiny and finite).
        self.func_cost = {}      # name -> this function's own total call weight
        self.total_weight = 0    # running weight for the function currently being generated

    def uid(self):
        self._uid += 1
        return self._uid

    # ---- expressions (always yield a value in [0, 999] when wrapped by wrap()) ----
    def atom(self, scope):
        if scope and self.r.random() < 0.7:
            return self.r.choice(scope)
        return str(self.r.randint(0, 50))

    def expr(self, scope, depth=0, mult=1):
        if depth >= 3 or self.r.random() < 0.25:
            return self.atom(scope)
        a = self.expr(scope, depth + 1, mult)
        b = self.expr(scope, depth + 1, mult)
        op = self.r.choice(["+", "-", "*", "&", "|", "^", "<<", ">>", "/", "%", "call"])
        if op == "-":
            return f"({a} + 1000 - ({b} % 1000))"
        if op == "*":
            return f"(({a} % 1000) * ({b} % 1000))"
        if op == "<<":
            return f"({a} << {self.r.randint(0, 3)})"
        if op == ">>":
            return f"({a} >> {self.r.randint(0, 3)})"
        if op in ("/", "%"):
            return f"({a} {op} {self.r.randint(1, 9)})"
        if op == "call" and self.funcs:
            name, n = self.r.choice(self.funcs)
            cost = (self.func_cost.get(name, 0) + 1) * mult
            if self.total_weight + cost > self.CALL_BUDGET:
                op = "+"
            else:
                self.total_weight += cost
                args = ", ".join(self.expr(scope, depth + 2, mult) for _ in range(n))
                return f"{name}({args})"
        if op == "call":
            op = "+"
        return f"({a} {op} {b})"

    def wrap(self, e):
        return f"(({e}) % 1000)"

    def cond(self, scope, depth=0, mult=1):
        a, b = self.atom(scope), self.expr(scope, 2, mult)
        c = f"{a} {self.r.choice(['<', '<=', '>', '>=', '==', '!='])} {b}"
        if depth < 2 and self.r.random() < 0.4:
            d = self.cond(scope, depth + 1, mult)
            joiner = self.r.choice(["and", "or"])
            c = f"({c}) {joiner} ({d})"
        if self.r.random() < 0.15:
            c = f"not ({c})"
        return c

    # ---- statements ----
    # `mult` estimates how many times code at this point actually executes at runtime, so
    # expr()'s call-budget check (see its comment) can tell a call inside a tight loop from
    # one that only ever runs once -- it's multiplied by each loop's own bound on the way in,
    # never divided back down on the way out (recursion naturally scopes that), same shape as
    # count_var_refs' loop-depth weighting in the x86_64 register allocator.
    def stmts(self, scope, locals_, indent, depth, budget, mult=1):
        out = []
        pad = "    " * indent
        for _ in range(budget):
            kind = self.r.random()
            target = self.r.choice(locals_)
            if kind < 0.38 or depth >= 2:
                out.append(f"{pad}{target} = {self.wrap(self.expr(scope, mult=mult))}")
            elif kind < 0.56:
                out.append(f"{pad}if {self.cond(scope, mult=mult)} {{")
                out += self.stmts(scope, locals_, indent + 1, depth + 1, 2, mult)
                if self.r.random() < 0.5:
                    out.append(f"{pad}}} elif {self.cond(scope, mult=mult)} {{")
                    out += self.stmts(scope, locals_, indent + 1, depth + 1, 1, mult)
                if self.r.random() < 0.5:
                    out.append(f"{pad}}} else {{")
                    out += self.stmts(scope, locals_, indent + 1, depth + 1, 1, mult)
                out.append(f"{pad}}}")
            elif kind < 0.68:
                counter = f"w{depth}_{self.uid()}"
                bound = self.r.randint(1, 5)
                out.append(f"{pad}{counter} = 0")
                out.append(f"{pad}while {counter} < {bound} {{")
                out += self.stmts(scope, locals_, indent + 1, depth + 1, 2, mult * bound)
                out.append(f"{pad}    {counter} = {counter} + 1")
                out.append(f"{pad}}}")
            elif kind < 0.76:
                counter = f"f{depth}_{self.uid()}"
                bound = self.r.randint(1, 4)
                out.append(f"{pad}for {counter} in range({bound}) {{")
                out += self.stmts(scope + [counter], locals_, indent + 1, depth + 1, 2, mult * bound)
                out.append(f"{pad}}}")
            elif kind < 0.82:
                # loop bound is len(list): hoistable only while the body cannot change the list's length
                counter = f"l{depth}_{self.uid()}"
                out.append(f"{pad}for {counter} in range(len(xs)) {{")
                out.append(f"{pad}    {target} = (xs[{counter}] + {self.wrap(self.expr(scope, 2, mult))}) % 1000")
                out += self.stmts(scope + [counter], locals_, indent + 1, depth + 1, 1, mult * 8)
                out.append(f"{pad}}}")
            elif kind < 0.87:
                # the body grows the list, so len(xs) must be re-evaluated every iteration
                counter = f"g{depth}_{self.uid()}"
                out.append(f"{pad}for {counter} in range(len(xs) - 6) {{")
                out.append(f"{pad}    if len(xs) < 11 {{")
                out.append(f"{pad}        xs.append({self.wrap(self.expr(scope, 2, mult))})")
                out.append(f"{pad}    }}")
                out.append(f"{pad}    {target} = (xs[{counter}] + {counter}) % 1000")
                out.append(f"{pad}}}")
            elif kind < 0.90:
                # string loop; the body may rebind the string, so its length must not be hoisted then
                counter = f"c{depth}_{self.uid()}"
                rebinds = self.r.random() < 0.5
                out.append(f"{pad}for {counter} in range(len(sv)) {{")
                out.append(f"{pad}    if sv[{counter}] == \"l\" {{ {target} = ({target} + {counter} + 1) % 1000 }}")
                if rebinds:
                    out.append(f"{pad}    if len(sv) < 9 {{ sv = sv + \"l\" }}")
                out.append(f"{pad}}}")
            elif kind < 0.97:
                # dict ops over a small fixed key set. Only .set/.get/.has with an explicit
                # key, never anything that reads key order (e.g. .keys()) -- the VM's Python
                # dict and native's open-addressing table have no reason to agree on
                # iteration order, only on what a given key maps to.
                key = self.r.choice(['"a"', '"b"', '"c"', '"d"', '"e"'])
                if self.r.random() < 0.5:
                    out.append(f"{pad}dv.set({key}, {self.wrap(self.expr(scope, 2, mult))})")
                else:
                    out.append(f"{pad}if dv.has({key}) == 1 {{ {target} = (dv.get({key}) + {self.atom(scope)}) % 1000 }}")
            else:
                idx = self.wrap(self.expr(scope, 2, mult))
                out.append(f"{pad}xs[{idx} % 8] = {self.wrap(self.expr(scope, mult=mult))}")
                out.append(f"{pad}{target} = (xs[{self.wrap(self.expr(scope, 2, mult))} % 8] + {self.atom(scope)}) % 1000")
        return out

    def function(self, index):
        nparams = self.r.randint(0, 6)
        params = [f"p{i}" for i in range(nparams)]
        nlocals = self.r.randint(2, 10)
        locals_ = [f"v{i}" for i in range(nlocals)]
        name = f"fn{index}"
        body = []
        scope = list(params)
        weight_before = self.total_weight
        for v in locals_:
            body.append(f"    {v} = {self.wrap(self.expr(scope))}")
            scope.append(v)
        body.append("    xs = [1, 2, 3, 4, 5, 6, 7, 8]")
        body.append("    sv = \"hello\"")
        body.append("    dv = {}")
        body += self.stmts(scope, locals_, 1, 0, self.r.randint(3, 7))
        ret = self.wrap(" + ".join(self.r.sample(scope, min(len(scope), 3))) if scope else "0")
        body.append(f"    return {ret}")
        # This function's own weight (including whatever it itself calls) is what callers
        # defined after it should be charged for calling it -- recorded before appending to
        # self.funcs so this function can't immediately call itself in its own body.
        self.func_cost[name] = self.total_weight - weight_before
        self.lines.append(f"def {name}({', '.join(params)}) {{")
        self.lines += body
        self.lines.append("}")
        self.funcs.append((name, nparams))

    def program(self):
        for i in range(self.r.randint(3, 6)):
            self.function(i)
        for name, n in self.funcs:
            for _ in range(3):
                args = ", ".join(str(self.r.randint(0, 999)) for _ in range(n))
                self.lines.append(f"print({name}({args}))")
        return "\n".join(self.lines) + "\n"


def generate(seed):
    return Gen(seed).program()


def test_generator_is_deterministic_and_valid():
    assert generate(1) == generate(1)
    assert generate(1) != generate(2)
    out = _vm_output(generate(7)).split()
    assert out and all(tok.lstrip("-").isdigit() for tok in out)


@pytest.mark.parametrize("seed", range(START, START + COUNT))
def test_native_matches_vm(seed, selfhost_run):
    program = generate(seed)
    expected = _vm_output(program).split()
    r, _ = selfhost_run(program, f"fuzz_{seed}")
    assert r.returncode == 0, f"native build crashed for seed {seed}\n{program}"
    assert r.stdout.split() == expected, f"seed {seed} differs\n{program}"


def test_stage2_matches_vm_on_a_sample(stage2):
    from test_stage2 import _run
    for seed in (START, START + 1, START + 2):
        program = generate(seed)
        assert _run(stage2, f"fuzz2_{seed}", program) == _vm_output(program).split(), f"seed {seed}\n{program}"
