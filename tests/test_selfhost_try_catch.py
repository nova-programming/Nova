"""Regression tests for try/catch in the self-hosted compiler.

Three independent bugs, found together while investigating why the self-hosted compiler
couldn't parse `catch e { ... }` at all (discovered exploring try/catch coverage for the
differential fuzzer -- see docs/AGENT_LOG.md):

1. stdlib/parser.nv's parse_try_block expected `catch(e) { ... }` (with parens around the
   catch variable), which no other part of the language or test suite ever used. Every real
   try/catch program failed with a syntax error ("expected LPAREN but got IDENT") before
   ever reaching codegen. Fixed by removing the LPAREN/RPAREN expectations, matching the
   Python bootstrap parser (bootstrap/parser/parser.py's parse_try) exactly.
2. stdlib/backend/x86_64/codegen.nv's scan_vars had no case for "TRY" at all, so the catch
   variable (Try.val_str, a plain string naming a new local) was never registered.
   compile_stmt's own TRY handler stores the caught value via
   find_var_offset(state, node.val_str), which returns 0 for an unregistered name -- not a
   safe no-op here, since offset 0 means "write to [rbp - 0]", directly over the saved frame
   pointer on the stack. Fixed by registering node.val_str and recursing into node.body/
   node.else_body, mirroring the identical fix already made to both Python-bootstrap
   backends for the same class of bug.
3. stdlib/type_checker.nv's TRY case (h == 12) read node.args/node.cond, but the parser
   actually sets node.body/node.else_body -- node.args/node.cond are always unset (null) for
   a TRY node, so len(node.args) segfaulted instead of returning 0 (the same "len() on an
   unset field" bug class fixed in the register-allocation work, just pre-existing and never
   exercised until bug #1 was fixed and a real TRY node could finally reach this code).

Fixing #1 alone immediately exposed #2 and #3 in turn -- each one only became reachable once
the previous one stopped blocking it.
"""
import pytest


def test_minimal_catch_value(selfhost_run):
    r, _ = selfhost_run(
        'try {\n'
        '    throw 42\n'
        '} catch e {\n'
        '    print(e)\n'
        '}\n',
        "selfhost_catch_minimal",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "42"


def test_no_throw_path_and_string_exception(selfhost_run):
    r, _ = selfhost_run(
        'try { throw("err") } catch e { print("caught") }\n'
        'try { print(1) } catch e { print(2) }\n',
        "selfhost_catch_paths",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["caught", "1"]


def test_try_inside_function_with_conditional_throw(selfhost_run):
    source = (
        'def f(n) {\n'
        '    try {\n'
        '        if n < 0 { throw 99 }\n'
        '        return n * 2\n'
        '    } catch e {\n'
        '        return e\n'
        '    }\n'
        '}\n'
        'print(f(5))\n'
        'print(f(-5))\n'
    )
    r, _ = selfhost_run(source, "selfhost_catch_fn")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.split() == ["10", "99"]
