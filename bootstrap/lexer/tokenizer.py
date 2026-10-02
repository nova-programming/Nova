"""Fast char-by-char lexer for Nova source code."""

SINGLE_CHAR = {
    '+': "PLUS", '-': "MINUS", '*': "STAR", '/': "SLASH", '%': "PERCENT",
    '=': "EQUALS", '&': "AMPERSAND", '|': "PIPE", '^': "CARET", '~': "TILDE",
    '(': "LPAREN", ')': "RPAREN", '{': "LBRACE", '}': "RBRACE",
    '[': "LBRACK", ']': "RBRACK", ',': "COMMA", '.': "DOT",
    ':': "COLON", ';': "SEMICOLON", '<': "LT", '>': "GT",
}

TWO_CHAR = {
    "==": "EQEQ", "!=": "NOTEQ", "<=": "LE", ">=": "GE",
    "->": "ARROW", ">>": "GTGT", "<<": "LTLT",
    "+=": "PLUSEQ", "-=": "MINUSEQ", "*=": "STAREQ",
    "/=": "SLASHEQ", "%=": "PERCENTEQ",
}

KEYWORDS = {
    "true": "TRUE", "false": "FALSE", "null": "NULL",
    "class": "CLASS", "printd": "PRINTD", "print": "PRINT",
    "def": "DEF", "data": "DATA", "self": "SELF",
    "sizeof": "SIZEOF", "openf": "OPENF", "api": "API",
    "len": "LEN", "open": "OPEN", "read": "READ",
    "write": "WRITE", "close": "CLOSE", "return": "RETURN",
    "if": "IF", "else": "ELSE", "while": "WHILE",
    "for": "FOR", "in": "IN", "to": "TO", "downto": "DOWNTO",
    "step": "STEP", "and": "AND", "or": "OR", "not": "NOT",
    "break": "BREAK", "continue": "CONTINUE", "from": "FROM",
    "import": "IMPORT", "as": "AS", "alloc": "ALLOC",
    "free": "FREE", "has": "HAS", "elif": "ELIF",
    "switch": "SWITCH", "case": "CASE", "try": "TRY",
    "catch": "CATCH", "throw": "THROW",
    "int": "TYPE_INT", "float": "TYPE_FLOAT", "bool": "TYPE_BOOL",
    "string": "TYPE_STRING", "byte": "TYPE_BYTE", "void": "TYPE_VOID", "const": "CONST", "enum": "ENUM",
    "comptime": "COMPTIME",
    "str": "STR",
    "defer": "DEFER",
    "extern": "EXTERN",
    "@raw": "RAW", "@export": "EXPORT", "@entry": "ENTRY", "@noinline": "NOINLINE",
}

ESCAPE_MAP = {
    "n": "\n", "t": "\t", "r": "\r", "\\": "\\",
    '"': '"', "0": "\0", "b": "\b", "a": "\a", "f": "\f", "v": "\v",
}


def process_escapes(s):
    result = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == '\\' and i + 1 < n:
            esc = ESCAPE_MAP.get(s[i+1])
            if esc is not None:
                result.append(esc)
                i += 2
                continue
        result.append(s[i])
        i += 1
    return "".join(result)


def _protect_braces(text):
    """Turn an escaped brace (backslash-open or backslash-close) into a sentinel so it is never
    mistaken for string interpolation; a doubled backslash is not an escape."""
    out = []
    k = 0
    n = len(text)
    while k < n:
        if text[k] == '\\' and k + 1 < n:
            nxt = text[k + 1]
            if nxt == "{":
                out.append("\x01")
            elif nxt == "}":
                out.append("\x02")
            else:
                out.append(text[k] + nxt)
            k += 2
        else:
            out.append(text[k])
            k += 1
    return "".join(out)


def _restore_braces(tok):
    if tok[0] == "STRING" and ("\x01" in tok[1] or "\x02" in tok[1]):
        return (tok[0], tok[1].replace("\x01", "{").replace("\x02", "}")) + tuple(tok[2:])
    return tok


def tokenize(code):
    tokens = []
    n = len(code)
    i = 0
    line_num = 1
    line_start = 0

    while i < n:
        c = code[i]

        # Whitespace
        if c in ' \t\r':
            i += 1
            continue

        # Newline
        if c == '\n':
            line_num += 1
            line_start = i + 1
            i += 1
            continue

        # Comment
        if c == '#':
            while i < n and code[i] != '\n':
                i += 1
            continue

        # Two-char operators
        if i + 1 < n:
            two = c + code[i+1]
            kind = TWO_CHAR.get(two)
            if kind is not None:
                tokens.append((kind, two, line_num, i - line_start))
                i += 2
                continue

        # Single-char operators / delimiters
        kind = SINGLE_CHAR.get(c)
        if kind is not None:
            tokens.append((kind, c, line_num, i - line_start))
            i += 1
            continue

        # String literal
        if c == '"':
            j = i + 1
            while j < n:
                if code[j] == '\\' and j + 1 < n:
                    j += 2
                elif code[j] == '"':
                    j += 1
                    break
                else:
                    j += 1
            value = code[i:j]
            inner = value[1:-1]
            inner = process_escapes(_protect_braces(inner))
            string_start = len(tokens)

            if "{" in inner and "}" in inner:
                new_tokens = []
                k = 0
                inner_len = len(inner)
                while k < inner_len:
                    if inner[k] == '{':
                        depth = 1
                        start_expr = k + 1
                        k += 1
                        while k < inner_len and depth > 0:
                            if inner[k] == '{': depth += 1
                            elif inner[k] == '}': depth -= 1
                            k += 1
                        if depth > 0:
                            new_tokens.append(("STRING", '"' + inner[start_expr-1:] + '"', line_num, i - line_start))
                            break
                        expr_str = inner[start_expr:k-1]
                        if not expr_str.strip():
                            new_tokens.append(("STRING", '"' + inner[start_expr-1:k-1] + '"', line_num, i - line_start))
                        else:
                            new_tokens.append(("STR", "str", line_num, i - line_start))
                            new_tokens.append(("LPAREN", "(", line_num, i - line_start))
                            new_tokens.extend(tokenize(expr_str))
                            new_tokens.append(("RPAREN", ")", line_num, i - line_start))
                    else:
                        text_start = k
                        while k < inner_len and inner[k] != '{':
                            k += 1
                        new_tokens.append(("STRING", '"' + inner[text_start:k] + '"', line_num, i - line_start))
                    new_tokens.append(("PLUS", "+", line_num, i - line_start))
                if new_tokens:
                    new_tokens.pop()
                tokens.extend(new_tokens)
            else:
                tokens.append(("STRING", '"' + inner + '"', line_num, i - line_start))
            tokens[string_start:] = [_restore_braces(t) for t in tokens[string_start:]]
            i = j
            continue

        # Number literal (including float, hex, binary)
        if c.isdigit() or (c == '.' and i + 1 < n and code[i+1].isdigit()):
            j = i
            # Hex or binary
            if c == '0' and i + 1 < n and code[i+1] in 'xXbB':
                is_hex = code[i+1] in 'xX'
                allowed = '0123456789abcdefABCDEF' if is_hex else '01'
                prefix_end = i + 2
                while prefix_end < n and code[prefix_end] in allowed:
                    prefix_end += 1
                tokens.append(("NUMBER", code[i:prefix_end], line_num, i - line_start))
                i = prefix_end
                continue

            # Decimal number, possibly float
            while j < n and code[j].isdigit():
                j += 1
            kind = "NUMBER"
            if j < n and code[j] == '.' and j + 1 < n and code[j + 1].isdigit():
                j += 1
                while j < n and code[j].isdigit():
                    j += 1
                kind = "FLOAT"
            tokens.append((kind, code[i:j], line_num, i - line_start))
            i = j
            continue

        # Identifier or keyword
        if c.isalpha() or c in '_@':
            j = i
            while j < n and (code[j].isalnum() or code[j] in '_@'):
                j += 1
            word = code[i:j]
            kind = KEYWORDS.get(word, "IDENT")
            tokens.append((kind, word, line_num, i - line_start))
            i = j
            continue

        # Unexpected character
        col = i - line_start
        e = SyntaxError(f"Unexpected character: {c!r} at line {line_num}, col {col}")
        e.lineno = line_num
        e.offset = col + 1
        raise e

    return _free_soft_keywords(tokens)


# Words that are built-in *functions*, not reserved syntax: they only act as keywords
# when called (``read(fd)``). Everywhere else they are ordinary identifiers, so
# ``write = 5``, ``def close()``, ``self.api`` and ``f.read()`` all work.
SOFT_KEYWORDS = {"READ", "WRITE", "CLOSE", "API", "OPENF"}


def _free_soft_keywords(tokens):
    defined = set()
    for i in range(len(tokens) - 1):
        if tokens[i][0] == "DEF" and tokens[i + 1][0] in SOFT_KEYWORDS:
            defined.add(tokens[i + 1][1])
    for i, tok in enumerate(tokens):
        if tok[0] == "DATA":
            # `data Name {` declares a struct; anywhere else `data` is a plain identifier
            is_decl = (i + 2 < len(tokens) and tokens[i + 1][0] == "IDENT"
                       and tokens[i + 2][0] == "LBRACE")
            if not is_decl:
                tokens[i] = ("IDENT",) + tuple(tok[1:])
            continue
        if tok[0] not in SOFT_KEYWORDS:
            continue
        prev_kind = tokens[i - 1][0] if i > 0 else None
        next_kind = tokens[i + 1][0] if i + 1 < len(tokens) else None
        if (next_kind != "LPAREN" or prev_kind in ("DOT", "DEF", "EXTERN")
                or tok[1] in defined):
            tokens[i] = ("IDENT",) + tuple(tok[1:])
    return tokens
