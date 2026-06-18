# Nova Parser Internals (`stdlib/parser.nv`)

Consumes a `Token` list from the tokenizer and builds an `AstNode` AST.

## State

`ParserState` struct with `tokens`, `pos`, `length`. Uses `peek()`, `advance()`, `expect()`, `match()`.

## Node Hierarchy

Every AST element is an `AstNode` with a `kind` string tag. Common properties:
- `kind` — node type (`"Program"`, `"FunctionDef"`, `"IfElse"`, `"BinOp"`, `"Variable"`, `"Try"`, `"Throw"`, etc.)
- `val_str` / `val_int` — literal values
- `body`, `if_body`, `else_body` — child node lists
- `left` / `right` — binary operation operands
- `params` — function parameters (as child nodes)
- `target` — assignment target
- `catch_body`, `catch_var_name` — exception handler nodes (on `"Try"` nodes)

## Desugaring

Several high-level constructs desugar at parse time — no special AST nodes or codegen changes needed:

- **List comprehensions** `[expr for x in list if cond]`: Desugars to a `Block` containing a `ForIn` loop with an `If` guard and `ListAppend` on each iteration. Parse-time only; codegen sees standard AST nodes.
- **Switch/match** `switch expr { case val { body } else { body } }`: Desugars to an `IfElse`/`Elif` chain comparing the switch expression against each case value. No runtime switch instruction emitted.
- **Dict literals** `{"key": val}`: Parsed as a `DictLiteral` node with interleaved key-value pairs in the `args` list (positions 0,2,4,... = keys; 1,3,5,... = values).
- **Try/catch/throw**: Produces `Try` (with `body`, `catch_body`, `catch_var_name`) and `Throw` (with `value`) AST nodes. Not desugared — compiled to native via `_try_block`/`_throw_error`/`_catch_error` in codegen.

## Recursive Descent Flow

1. **Top-Level (`parse`)**: Loops over tokens, parsing `def`, `data`, `class`, or statement nodes
2. **Statements (`parse_stmt`)**: Dispatches on token kind — `def` → function, `if` → if/elif/else, `while` → loop, `for` → range-loop, `@raw` → raw block, `return` → return, `try` → try/catch, `throw` → throw, otherwise → expression + optional assignment
3. **Expressions**: Precedence-climbing via `parse_primary → parse_unary → parse_mul → parse_add → parse_compare → parse_logic → parse_expr`
4. **Primary**: Handles literals, variables, parenthesized expressions, list literals, dict literals, and suffix chains (`.field`, `[index]`, `(args)`). `parse_primary` was refactored from a deeply nested `if`/`else if` chain (200+ lines) into a flat `if/elif/else` chain — one branch per token type (NUMBER, STRING, TRUE, FALSE, LBRACK, LBRACE, LEN, STR, SIZEOF, OPENF, READ, WRITE, CLOSE, ALLOC, FREE, IDENT, LPAREN, SELF, RBRACE, COMMA).

### Constant Folding
In `parse_add` and `parse_mul`, when both operands are `Number` nodes, the operation is evaluated immediately. `1 + 2 * 3` collapses to `7` at parse time — no `BinOp` node created, no runtime instructions emitted.

### Type Annotation Parsing
`parse_type_annotation()` handles `int`, `float`, `bool`, `string`, `byte`, `void`, user-defined identifiers, and generic `list[T]` syntax (e.g., `list[int]`). Used for variable declarations, parameter types, return types, and struct fields.
