# Nova Tokenizer Internals (`stdlib/tokenizer.nv`)

Lexical analysis: raw source string → list of `Token` structs.

## State

`TokenizerState` struct: `input`, `pos`, `length`, `line`, `col`.

## Token Types

- Identifiers & keywords
- Integers (base-10)
- String literals (`"..."` or `'...'`)
- Operators and punctuation: `{`, `}`, `(`, `)`, `[`, `]`, `+`, `-`, `*`, `/`, `=`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `->`, `,`, `:`, `.`, `&`, `<<`, `>>`

## Flow

1. Skip whitespace and comments (`//` and `#`)
2. Classify starting character via `_is_alpha`, `_is_digit`, `_is_space`
3. Enter specialized tokenization (number, identifier, string, operator)
4. Create `Token` with `kind` and `val`, append to list
