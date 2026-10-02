"""Source tools for the public API names: old-spelling detection and migration.

Used by `nova lint` (STYLE003) and `nova fmt --write --modernize`.
"""
import re

import names

OLD_MEMBERS = {
    "as_list": "asList", "value_byte": "valueByte", "value_word": "valueWord",
    "value_dword": "valueDword", "value_qword": "valueQword",
}

_CALL_RE = re.compile(r"(?<![\w.])([a-z][a-z0-9_]*)(\s*\()")
_MEMBER_RE = re.compile(r"\.(as_list|value_byte|value_word|value_dword|value_qword)\b")
_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)


def old_api_map():
    """internal flat function name -> (module, member)."""
    table = {internal: (mod, member)
             for mod, funcs in names.MODULE_FUNCS.items()
             for member, internal in funcs.items()}
    table["path_join2"] = ("path", "join")
    return table


def code_segments(line):
    """Split a line into (is_code, text) pieces, so strings and # comments are never rewritten."""
    pieces, buf, i, n = [], [], 0, len(line)
    while i < n:
        c = line[i]
        if c == '"':
            if buf:
                pieces.append((True, "".join(buf)))
                buf = []
            j = i + 1
            while j < n and line[j] != '"':
                j += 2 if line[j] == "\\" else 1
            pieces.append((False, line[i:j + 1]))
            i = j + 1
        elif c == "#":
            if buf:
                pieces.append((True, "".join(buf)))
                buf = []
            pieces.append((False, line[i:]))
            i = n
        else:
            buf.append(c)
            i += 1
    if buf:
        pieces.append((True, "".join(buf)))
    return pieces


def defined_functions(source):
    return set(_DEF_RE.findall(source))


def old_spellings(line, defined):
    """Yield (old_name, 'module.member') for old API calls found in code on this line."""
    old = old_api_map()
    if re.match(r"\s*def\s", line):
        return
    for is_code, text in code_segments(line):
        if not is_code:
            continue
        for m in re.finditer(r"(?<![\w.])([a-z][a-z0-9_]*)\s*\(", text):
            name = m.group(1)
            if name in old and name not in defined:
                mod, member = old[name]
                yield name, f"{mod}.{member}"


def modernize_source(source):
    """Rewrite old flat API spellings to module-qualified / camelCase forms.

    fs_read(p) -> fs.read(p), path_join2(a, b) -> path.join(a, b), x.as_list(n) -> x.asList(n).
    Adds the needed `import` lines. Functions the file defines itself are left alone.
    """
    old = old_api_map()
    defined = defined_functions(source)
    used = set()

    def fix_call(m):
        name = m.group(1)
        if name in old and name not in defined:
            mod, member = old[name]
            used.add(mod)
            return f"{mod}.{member}{m.group(2)}"
        return m.group(0)

    out = []
    for line in source.split("\n"):
        if re.match(r"\s*def\s", line):
            out.append(line)
            continue
        parts = []
        for is_code, text in code_segments(line):
            if is_code:
                text = _CALL_RE.sub(fix_call, text)
                text = _MEMBER_RE.sub(lambda m: "." + OLD_MEMBERS[m.group(1)], text)
            parts.append(text)
        out.append("".join(parts))
    result = "\n".join(out)
    missing = sorted(m for m in used if not re.search(rf"^\s*import\s+{m}\b", result, re.M))
    if missing:
        lines = result.split("\n")
        last = max((i for i, l in enumerate(lines) if re.match(r"\s*import\s", l)), default=-1)
        lines[last + 1:last + 1] = [f"import {m}" for m in missing]
        result = "\n".join(lines)
    return result
