"""Expression parsing logic"""

from ast.nodes import (
    Number, String, Boolean, Variable, BinOp, 
    Compare, UnaryOp, Call, Attribute
)


class ExpressionParser:
    """Parser for Nova expressions"""
    
    def __init__(self, parser):
        self.parser = parser
        self.current = parser.current
        self.eat = parser.eat

    def parse_expr(self):
        return self.parse_logic()

    def parse_logic(self):
        left = self.parse_compare()

        while self.current() and self.current()[0] in ("AND", "OR"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_compare()
            left = BinOp(left, op, right)

        return left

    def parse_compare(self):
        left = self.parse_add()
        ops = {"GT", "LT", "GE", "LE", "EQEQ", "NOTEQ"}

        while self.current() and self.current()[0] in ops:
            op = self.eat(self.current()[0])[1]
            right = self.parse_add()
            left = Compare(left, op, right)

        return left

    def parse_add(self):
        left = self.parse_mul()

        while self.current() and self.current()[0] in ("PLUS", "MINUS"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_mul()
            left = BinOp(left, op, right)

        return left

    def parse_mul(self):
        left = self.parse_unary()

        while self.current() and self.current()[0] in ("STAR", "SLASH"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_unary()
            left = BinOp(left, op, right)

        return left

    def parse_unary(self):
        if self.current() and self.current()[0] == "MINUS":
            op = self.eat("MINUS")[1]
            return UnaryOp(op, self.parse_unary())
        return self.parse_primary()

    def parse_primary(self):
        token = self.current()

        if not token:
            raise SyntaxError("Unexpected EOF")

        kind, value = token

        if kind == "NUMBER":
            self.eat("NUMBER")
            return Number(int(value))

        if kind == "STRING":
            self.eat("STRING")
            return String(value[1:-1])

        if kind == "TRUE":
            self.eat("TRUE")
            return Boolean(True)

        if kind == "FALSE":
            self.eat("FALSE")
            return Boolean(False)

        if kind == "LPAREN":
            self.eat("LPAREN")
            expr = self.parse_expr()
            self.eat("RPAREN")
            return expr

        if kind == "IDENT":
            name = self.eat("IDENT")[1]

            # Check for function call
            if self.current() and self.current()[0] == "LPAREN":
                self.eat("LPAREN")
                args = []
                
                if self.current() and self.current()[0] != "RPAREN":
                    args.append(self.parse_expr())
                    while self.current() and self.current()[0] == "COMMA":
                        self.eat("COMMA")
                        if self.current() and self.current()[0] != "RPAREN":
                            args.append(self.parse_expr())
                
                self.eat("RPAREN")
                return Call(name, args)

            # Check for attribute access
            if self.current() and self.current()[0] == "DOT":
                self.eat("DOT")
                attr = self.eat("IDENT")[1]
                return Attribute(Variable(name), attr)

            return Variable(name)

        raise SyntaxError(f"Unexpected token in expression: {token}")