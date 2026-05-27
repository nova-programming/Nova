"""Lexer for tokenizing Nova source code"""

from .tokens import TOKEN_REGEX

# Escape sequence mapping for string literals
ESCAPE_MAP = {
    "\\n": "\n",
    "\\t": "\t",
    "\\r": "\r",
    "\\\\": "\\",
    '\\"': '"',
    "\\0": "\0",
    "\\b": "\b",
    "\\a": "\a",
    "\\f": "\f",
    "\\v": "\v",
}


def process_escapes(s):
    """Process escape sequences in a string literal value."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            two_char = s[i:i+2]
            if two_char in ESCAPE_MAP:
                result.append(ESCAPE_MAP[two_char])
                i += 2
                continue
        result.append(s[i])
        i += 1
    return "".join(result)


def tokenize(code):
    tokens = []
    line_num = 1
    last_pos = 0
    for match in TOKEN_REGEX.finditer(code):
        kind = match.lastgroup
        value = match.group()
        pos = match.start()

        # Count newlines between last_pos and current pos for accurate line tracking
        line_num += code.count('\n', last_pos, pos)
        last_pos = pos

        if kind in {"SKIP", "COMMENT"}:
            continue
        
        if kind == "NEWLINE":
            line_num += 1
            last_pos = pos + len(value)
            continue
        
        elif kind == "MISMATCH":
            raise SyntaxError(f"Unexpected character: {value!r} at line {line_num}")
        
        # Process escape sequences in string literals
        if kind == "STRING":
            # value includes quotes, e.g. '"Hello\nWorld"'
            # Strip quotes, process escapes, re-add quotes
            inner = value[1:-1]
            inner = process_escapes(inner)
            value = '"' + inner + '"'
        
        tokens.append((kind, value, line_num))
    
    return tokens