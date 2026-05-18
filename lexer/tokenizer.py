"""Lexer for tokenizing Nova source code"""

from .tokens import TOKEN_REGEX


def tokenize(code):
    tokens = []
    for match in TOKEN_REGEX.finditer(code):
        kind = match.lastgroup
        value = match.group()

        if kind in {"SKIP", "COMMENT", "NEWLINE"}:
            continue
        
        elif kind == "MISMATCH":
            raise SyntaxError(f"Unexpected character: {value!r}")
        
        tokens.append((kind, value))
    
    return tokens