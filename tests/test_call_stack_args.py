"""Regression tests for stack arguments (the 7th and later) in the x86_64 backends.

Both x86_64 code generators pushed arguments 7+ onto the stack and then never popped them
again in the caller. Nothing crashed immediately, which is why this went unnoticed: the
leftover slot just shifted every later push/pop by 8 bytes. The visible damage happened at
a callee's epilogue, where `pop r15 / pop r14 / pop r13 / pop r12` then read the wrong
slots and returned garbage in the callee-saved registers. Any live value the caller had
parked in r12-r15 across a 7+ argument call was silently corrupted.

That is exactly what broke the language server: `errors.err` (6 params) called
`_diag_emit` (7 params), and on return the parser's `state` pointer in r12 had turned into
a stray value, so the first syntax error crashed `novalsp --check`.

The source below exercises, in one program:
  * a data struct (held in a callee-saved register) surviving 7/8/9/10-argument calls,
  * the six-argument-function-calls-a-seven-argument-function shape above,
  * mixed string/int stack arguments,
  * 20,000 iterations, so a caller that fails to pop stack arguments would also leak
    8-32 bytes of stack per call instead of corrupting a register.
"""

SRC = (
    "data Box {\n"
    "    a: int\n"
    "    b: int\n"
    "    c: string\n"
    "}\n"
    "\n"
    "def seven(a: int, b: int, c: int, d: int, e: int, f: int, g: int) -> int {\n"
    "    return a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 + g * 7\n"
    "}\n"
    "\n"
    "def eight(a: int, b: int, c: int, d: int, e: int, f: int, g: int, h: int) -> int {\n"
    "    return seven(a, b, c, d, e, f, g) + h\n"
    "}\n"
    "\n"
    "def nine(a: int, b: int, c: int, d: int, e: int, f: int, g: int, h: int, i: int) -> int {\n"
    "    return eight(a, b, c, d, e, f, g, h) + i\n"
    "}\n"
    "\n"
    "def ten(a: int, b: int, c: int, d: int, e: int, f: int, g: int, h: int, i: int, j: int) -> int {\n"
    "    return nine(a, b, c, d, e, f, g, h, i) + j\n"
    "}\n"
    "\n"
    "def six_then_seven(x: int, y: int, z: int, u: int, v: int, w: int) -> int {\n"
    "    return seven(x, y, z, u, v, w, x + y)\n"
    "}\n"
    "\n"
    "def mixed(a: string, b: int, c: string, d: int, e: string, f: int, g: string, h: int) -> string {\n"
    "    return a + str(b) + c + str(d) + e + str(f) + g + str(h)\n"
    "}\n"
    "\n"
    "def run() {\n"
    "    box = Box()\n"
    "    box.a = 4\n"
    "    box.b = 11\n"
    "    box.c = \"keep\"\n"
    "    total = 0\n"
    "    i = 0\n"
    "    while i < 20000 {\n"
    "        total = total + six_then_seven(i, 1, 2, 3, 4, 5) + ten(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)\n"
    "        i = i + 1\n"
    "    }\n"
    "    print(str(box.a) + \",\" + str(box.b) + \",\" + str(total))\n"
    "    print(mixed(\"a\", 1, \"b\", 2, \"c\", 3, \"d\", 4))\n"
    "}\n"
    "\n"
    "run()\n"
)


def _expected_total():
    # six_then_seven(i,1,2,3,4,5) == seven(i,1,2,3,4,5,i+1) == 8*i + 77
    # ten(1..10) == seven(1..7) + 8 + 9 + 10 == 140 + 27 == 167
    return sum(8 * i + 77 + 167 for i in range(20000))


EXPECTED = "4,11,{0}\na1b2c3d4".format(_expected_total())


def _check(result):
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == EXPECTED


def test_stack_args_survive_selfhost_codegen(selfhost_run):
    """stdlib/backend/x86_64/codegen.nv's emit_call must pop arguments past the sixth."""
    r, _ = selfhost_run(SRC, "stack_args_selfhost")
    _check(r)


def test_stack_args_survive_bootstrap_codegen(bootstrap_native_run):
    """bootstrap/compiler/backend/x86_64/codegen.py's Call emitter must pop them too --
    the self-hosted compiler is itself built by this backend."""
    r = bootstrap_native_run(SRC, "stack_args_bootstrap")
    _check(r)
