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

        # Compute column (0-indexed, within current line)
        line_start = code.rfind('\n', 0, pos) + 1
        col = pos - line_start

        if kind in {"SKIP", "COMMENT"}:
            continue
        
        if kind == "NEWLINE":
            line_num += 1
            last_pos = pos + len(value)
            continue
        
        elif kind == "MISMATCH":
            e = SyntaxError(f"Unexpected character: {value!r} at line {line_num}, col {col}")
            e.lineno = line_num
            e.offset = col + 1
            raise e
        
        # Treat hex and binary literals as regular numbers (int() handles both)
        if kind in ("HEX", "BIN"):
            kind = "NUMBER"

        # Process escape sequences in string literals
        if kind == "STRING":
            # value includes quotes, e.g. '"Hello\nWorld"'
            # Strip quotes, process escapes, re-add quotes
            inner = value[1:-1]
            inner = process_escapes(inner)

            if "{" in inner and "}" in inner:
                # String interpolation: "Hello {name}!" → "Hello " + name + "!"
                new_tokens = []
                i = 0
                while i < len(inner):
                    if inner[i] == '{':
                        depth = 1
                        j = i + 1
                        while j < len(inner) and depth > 0:
                            if inner[j] == '{': depth += 1
                            elif inner[j] == '}': depth -= 1
                            j += 1
                        
                        if depth > 0:
                            # Unmatched brace, treat as normal text up to end
                            text = inner[i:]
                            new_tokens.append(("STRING", '"' + text + '"', line_num, col))
                            break

                        expr_str = inner[i+1:j-1]
                        if not expr_str.strip():
                            # Empty {}, treat as normal text
                            text = inner[i:j]
                            new_tokens.append(("STRING", '"' + text + '"', line_num, col))
                        else:
                            expr_tokens = tokenize(expr_str)
                            new_tokens.append(("STR", "str", line_num, col))
                            new_tokens.append(("LPAREN", "(", line_num, col))
                            new_tokens.extend(expr_tokens)
                            new_tokens.append(("RPAREN", ")", line_num, col))
                        i = j
                    else:
                        start = i
                        while i < len(inner) and inner[i] != '{':
                            i += 1
                        text = inner[start:i]
                        new_tokens.append(("STRING", '"' + text + '"', line_num, col))
                    new_tokens.append(("PLUS", "+", line_num, col))
                if new_tokens:
                    new_tokens.pop()
                tokens.extend(new_tokens)
                continue

            value = '"' + inner + '"'
        
        tokens.append((kind, value, line_num, col))
    
    return tokens