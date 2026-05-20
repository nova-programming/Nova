"""Token definitions for the Nova lexer"""

import re

TOKEN_SPEC = [
    # Literals
    ("NUMBER",   r"\d+"),
    ("FLOAT",    r"\d+\.\d+"),
    ("STRING",   r'"[^"]*"'),
    ("TRUE",     r"true\b"),
    ("FALSE",    r"false\b"),
    ("NULL",     r"null\b"),

    # Keywords
    ("PRINT",    r"print\b"),
    ("DEF",      r"def\b"),
    ("DATA",     r"data\b"),
    ("CLASS",    r"class\b"),
    ("SELF",     r"self\b"),
    ("SIZEOF",   r"sizeof\b"),
    ("LEN",      r"len\b"),
    ("RETURN",   r"return\b"),
    ("IF",       r"if\b"),
    ("ELSE",     r"else\b"),
    ("WHILE",    r"while\b"),
    ("FOR",      r"for\b"),
    ("TO",       r"to\b"),
    ("DOWNTO",   r"downto\b"),
    ("STEP",     r"step\b"),
    ("AND",      r"and\b"),
    ("OR",       r"or\b"),
    ("NOT",      r"not\b"),
    ("BREAK",    r"break\b"),
    ("CONTINUE", r"continue\b"),
    ("IMPORT",   r"import\b"),
    ("AS",       r"as\b"),
    ("ALLOC",    r"alloc\b"),
    ("FREE",     r"free\b"),

    # Directives
    ("RAW",      r"@raw"),
    ("EXPORT",   r"@export"),

    # Type keywords
    ("TYPE_INT",    r"int\b"),
    ("TYPE_FLOAT",  r"float\b"),
    ("TYPE_BOOL",   r"bool\b"),
    ("TYPE_STRING", r"string\b"),
    ("MUT",         r"mut\b"),

    # Identifiers
    ("IDENT",    r"[a-zA-Z_][a-zA-Z0-9_]*"),

    # Comparison Operators
    ("EQEQ",     r"=="),
    ("NOTEQ",    r"!="),
    ("GE",       r">="),
    ("LE",       r"<="),
    ("GT",       r">"),
    ("LT",       r"<"),

    # Arithmetic & Assignment Operators
    ("PLUS",     r"\+"),
    ("ARROW",    r"->"),
    ("MINUS",    r"-"),
    ("STAR",     r"\*"),
    ("SLASH",    r"/"),
    ("PERCENT",  r"%"),
    ("EQUALS",   r"="),

    # Delimiters
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("LBRACE",   r"\{"),
    ("RBRACE",   r"\}"),
    ("LBRACK",   r"\["),
    ("RBRACK",   r"\]"),
    ("COMMA",    r","),
    ("DOT",      r"\."),
    ("COLON",    r":"),
    ("SEMICOLON", r";"),

    # Formatting & Metadata
    ("NEWLINE",  r"\n"),
    ("COMMENT",  r"\#.*"),
    ("SKIP",     r"[ \t]+"),
    ("MISMATCH", r"."),
]

TOKEN_REGEX = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))