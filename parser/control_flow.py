"""Control flow parsing logic"""

from ast.nodes import Function, IfElse, While


class ControlFlowParser:
    """Parser for control flow structures"""
    
    def __init__(self, parser):
        self.parser = parser
        self.current = parser.current
        self.eat = parser.eat
        self.parse_block = parser.parse_block
        self.expr_parser = parser.expr_parser

    def parse_function(self):
        self.eat("FN")
        name = self.eat("IDENT")[1]
        self.eat("LPAREN")
        
        params = []
        if self.current() and self.current()[0] != "RPAREN":
            params.append(self.eat("IDENT")[1])
            while self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
                params.append(self.eat("IDENT")[1])
        
        self.eat("RPAREN")
        body = self.parse_block()
        
        return Function(name, params, body)

    def parse_if(self):
        self.eat("IF")
        cond = self.expr_parser.parse_expr()
        then = self.parse_block()

        else_body = []
        if self.current() and self.current()[0] == "ELSE":
            self.eat("ELSE")
            else_body = self.parse_block()

        return IfElse(cond, then, else_body)

    def parse_while(self):
        self.eat("WHILE")
        cond = self.expr_parser.parse_expr()
        body = self.parse_block()
        return While(cond, body)