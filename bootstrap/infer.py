"""Return-type inference for un-annotated functions (native builds).

Backends print and concatenate by the *declared* return type, so
``def f() { return "x" }`` used to print a pointer. This pass fills in a missing
``-> string`` from the function's own ``return`` expressions.

(Float returns are not inferred: native float returns are not reliable yet.)
It only ever adds an annotation, never changes an explicit one, and only when the
evidence is unambiguous: every return with a known type agrees, and at least one is
string/float. Unknown returns (parameters, recursive calls) do not vote. The stdlib
mirror lives in stdlib/infer.nv.
"""
from nova_ast.nodes import *

STRING_BUILTINS = {"str_sub", "sys_platform", "sys_read", "sys_read_c", "chr", "char_from_code"}
_ARITH = {"+", "-", "*", "/", "%"}


def _children(node):
    for value in vars(node).values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, tuple):
                    for sub in item:
                        if hasattr(sub, "__dict__"):
                            yield sub
                elif hasattr(item, "__dict__"):
                    yield item
        elif hasattr(value, "__dict__") and not isinstance(value, type):
            yield value


def _walk(node, skip_functions=True):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        for c in _children(n):
            if skip_functions and isinstance(c, (Function, ClassDef)):
                continue
            stack.append(c)


def _kind(node, env, returns):
    if isinstance(node, String):
        return "string"
    if isinstance(node, Number):
        return "float" if isinstance(node.value, float) else "int"
    if isinstance(node, StrConvert):
        return "string"
    if isinstance(node, (Len, Boolean, Compare)):
        return "int"
    if isinstance(node, Variable):
        return env.get(node.name)
    if isinstance(node, UnaryOp):
        return None if node.op == "not" else _kind(node.value, env, returns)
    if isinstance(node, BinOp):
        l, r = _kind(node.left, env, returns), _kind(node.right, env, returns)
        if node.op == "+" and "string" in (l, r):
            return "string"
        if node.op in _ARITH and "string" not in (l, r):
            if "float" in (l, r):
                return "float"
            if l == "int" and r == "int":
                return "int"
        return None
    if isinstance(node, Call):
        if node.name in STRING_BUILTINS:
            return "string"
        return returns.get(node.name)
    if isinstance(node, ArrayIndex):
        return "string" if _kind(node.base, env, returns) == "string" else None
    if isinstance(node, Slice):
        return "string" if _kind(node.base, env, returns) == "string" else None
    return None


def _local_env(fn, returns):
    env = {}
    for param in fn.params:
        name, ptype = param if isinstance(param, tuple) else (param, "")
        if ptype in ("string", "float", "int"):
            env[name] = ptype
    for _ in range(2):  # a second sweep lets locals defined from other locals settle
        for n in _walk_body(fn):
            if isinstance(n, Assignment) and isinstance(n.name, str):
                if n.type_name in ("string", "float", "int"):
                    env[n.name] = n.type_name
                else:
                    k = _kind(n.value, env, returns)
                    if k and n.name not in env:
                        env[n.name] = k
    return env


def _walk_body(fn):
    for stmt in fn.body:
        yield from _walk(stmt)


def infer_return_types(program):
    funcs = {n.name: n for n in program if isinstance(n, Function) and not n.is_extern}
    returns = {name: f.return_type for name, f in funcs.items() if f.return_type in ("string", "float", "int")}
    pending = [f for f in funcs.values() if not f.return_type]
    inferred = {}
    for _ in range(6):
        changed = False
        for fn in pending:
            if fn.name in inferred:
                continue
            env = _local_env(fn, returns)
            kinds = []
            for n in _walk_body(fn):
                if isinstance(n, Return) and n.value is not None:
                    k = _kind(n.value, env, returns)
                    if k:
                        kinds.append(k)
            known = set(kinds)
            if known <= {"string"} and "string" in known:
                result = "string"
            else:
                continue
            inferred[fn.name] = result
            returns[fn.name] = result
            changed = True
        if not changed:
            break
    for fn in pending:
        if fn.name in inferred:
            fn.return_type = inferred[fn.name]
    return inferred
