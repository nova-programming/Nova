# Nova Tokenizer Internals (`stdlib/tokenizer.nv`)

The `tokenizer.nv` file is responsible for performing lexical analysis on a given raw Nova source code string. Its primary role is to break down a continuous stream of characters into a structured list of meaning-bearing tokens (e.g., identifiers, keywords, numbers, operators) that the parser can readily consume.

## Architecture & State Management

The tokenizer operates via a `TokenizerState` struct which tracks:
* `input`: The raw source code string.
* `pos`: The current byte index in the string.
* `length`: The total length of the string.
* `line`: The current line number (for error reporting).
* `col`: The current column number (for error reporting).

## Supported Tokens
The tokenizer identifies the following generic categories of tokens:
- **Identifiers & Keywords:** Standard alpha-numeric strings (e.g., `def`, `while`, `my_var`).
- **Numbers:** Integers (currently only standard base-10 numerical tokens are parsed into string chunks to be converted later).
- **Strings:** Literals wrapped in `"` or `'` marks.
- **Punctuation / Operators:** Single and multi-character symbols like `{`, `}`, `==`, `!=`, `<=`, `>=`, `->`, `+`, `-`, `=`, `.`, etc.

## Lexical Flow
1. **Skipping Whitespace & Comments:** 
   The tokenizer advances the pointer past spaces, tabs, and newlines. Single line comments starting with `//` or `#` skip all characters until a newline is reached.
2. **Character Classification:**
   The `_is_alpha`, `_is_digit`, and `_is_space` helper functions natively classify raw byte values to determine what token type starts at the current pointer.
3. **Token Construction:**
   Depending on the initial character, the tokenizer enters a specialized loop (e.g., `tokenize_number`, `tokenize_identifier`, `tokenize_string`).
   It extracts the bounded substring by matching logical termination conditions and creates a `Token` instance representing the chunk.
4. **Token Appending:**
   Tokens are appended to a dynamically resized `List` in Nova, which is then returned to the caller (`parser.nv`).
