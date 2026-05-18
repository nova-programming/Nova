"""Statement parsing logic"""

from ast.nodes import (
    Assignment, Print, IfElse, While, Return, 
    Break, Continue, Function, Import, RawBlock, Export
)
from .expressions import ExpressionParser


class StatementParser:
    """Parser for Nova statements"""
    
    def __init__(self, parser):
        self.parser = parser
        self.current = parser.current
        self.eat = parser.eat
        self.skip_newlines = parser.skip_newlines
        self.parse_block = parser.parse_block
        self.parse_function = parser.parse_function
        self.parse_raw = parser.parse_raw
        self.parse_export = parser.parse_export
        self.parse_import = parser.parse_import
        self.parse_if = parser.parse_if
        self.parse_while = parser.parse_while
        
        self.expr_parser = ExpressionParser(parser)

    def parse_statement(self):
        self.skip_newlines()

        token = self.current()
        if not token:
            return None

        kind = token[0]

        if kind == "IMPORT":
            return self.parse_import()

        if kind == "RAW":
            return self.parse_raw()

        if kind == "PRINT":
            return self.parse_print()

        if kind == "IF":
            return self.parse_if()

        if kind == "WHILE":
            return self.parse_while()

        if kind == "RETURN":
            self.eat("RETURN")
            return Return(self.expr_parser.parse_expr())

        if kind == "BREAK":
            self.eat("BREAK")
            return Break()

        if kind == "CONTINUE":
            self.eat("CONTINUE")
            return Continue()

        if kind == "FN":
            return self.parse_function()

        # Handle expression statements
        if kind in ("IDENT", "NUMBER", "STRING", "TRUE", "FALSE", "LPAREN", "MINUS"):
            expr = self.expr_parser.parse_expr()
            
            # Check if this is an assignment
            if self.current() and self.current()[0] == "EQUALS":
                if isinstance(expr, Variable):
                    name = expr.name
                    self.eat("EQUALS")
                    value = self.expr_parser.parse_expr()
                    return Assignment(name, value)
                else:
                    raise SyntaxError("Invalid assignment target")
            
            return expr

        raise SyntaxError(f"Unknown statement: {token}")

    def parse_print(self):
        self.eat("PRINT")
        self.eat("LPAREN")
        value = self.expr_parser.parse_expr()
        self.eat("RPAREN")
        return Print(value)