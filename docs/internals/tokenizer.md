# Nova Tokenizer Internals (`stdlib/tokenizer.nv`)

Lexical analysis: raw source string → list of `Token` structs.

## State

`TokenizerState` struct: `input`, `pos`, `length`, `line`, `col`.

## Token Types

- Identifiers & keywords (47 tokens: all Nova keywords including `switch`, `try`, `catch`, `throw`)
- Integers (base-10)
- String literals (`"..."` or `'...'`)
- Operators and punctuation: `{`, `}`, `(`, `)`, `[`, `]`, `+`, `-`, `*`, `/`, `=`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `->`, `,`, `:`, `.`, `&`, `<<`, `>>`

## Flow

1. Skip whitespace and comments (`//` and `#`); track `line_num` per token
2. Classify starting character via `_is_alpha`, `_is_digit`, `_is_space`
3. Enter specialized tokenization (number, identifier, string, operator)
4. Create `Token` with `kind`, `val`, and `line`, append to list

Each token carries a `line` field set to the current line number at the time of creation. This enables line-precise error messages from the parser and type checker.

## Lexer Refactoring

The lexer was refactored to use `switch` statements for performance and readability:

- **`match_keyword` → `switch`**: The 49-line if-chain matching all 44 Nova keywords was replaced with a single `switch` statement.
- **Two-char operators → `switch`**: `==`, `!=`, `<=`, `>=`, `->`, `>>`, `<<` matched via `switch` instead of 7 separate if-blocks.
- **Single-char operators → `switch`**: 22 operator characters (+, -, *, /, %, =, &, |, ^, ~, <, >, (, ), {, }, [, ], ,, :, ., ;) matched via `switch`.
