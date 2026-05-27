# Nova Parser Internals (`stdlib/parser.nv`)

Consumes a `Token` list from the tokenizer and builds an `AstNode` AST.

## State

`ParserState` struct with `tokens`, `pos`, `length`. Uses `peek()`, `advance()`, `expect()`, `match()`.

## Node Hierarchy

Every AST element is an `AstNode` with a `kind` string tag. Common properties:
- `kind` — node type (`"Program"`, `"FunctionDef"`, `"IfElse"`, `"BinOp"`, `"Variable"`, etc.)
- `val_str` / `val_int` — literal values
- `body`, `if_body`, `else_body` — child node lists
- `left` / `right` — binary operation operands
- `params` — function parameters (as child nodes)
- `target` — assignment target

## Recursive Descent Flow

1. **Top-Level (`parse`)**: Loops over tokens, parsing `def`, `data`, `class`, or statement nodes
2. **Statements (`parse_stmt`)**: Dispatches on token kind — `def` → function, `if` → if/elif/else, `while` → loop, `for` → range-loop, `@raw` → raw block, `return` → return, otherwise → expression + optional assignment
3. **Expressions**: Precedence-climbing via `parse_primary → parse_unary → parse_mul → parse_add → parse_compare → parse_logic → parse_expr`
4. **Primary**: Handles literals, variables, parenthesized expressions, list literals, and suffix chains (`.field`, `[index]`, `(args)`)
