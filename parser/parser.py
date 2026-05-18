from nova.ast.nodes import *


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.in_raw = False
        self.data_structures = []
        self.classes = []

    def parse_data(self):
        """Parse data structure definition"""
        self.eat("DATA")
        name = self.eat("IDENT")[1]
        self.data_structures.append(name)
        
        self.eat("LBRACE")
        fields = []
        
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            
            field_name = self.eat("IDENT")[1]
            self.eat("COLON")
            
            # Handle type keywords
            type_token = self.current()
            if type_token[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING"):
                type_name = self.eat(type_token[0])[1]
            else:
                type_name = self.eat("IDENT")[1]
            
            fields.append((field_name, type_name))
            
            # Skip newline or semicolon
            if self.current() and self.current()[0] in ("NEWLINE", "SEMICOLON"):
                self.eat(self.current()[0])
        
        self.eat("RBRACE")
        return Data(name, fields)

    def parse_data_instance(self, data_name):
        """Parse data instance creation: Point()"""
        self.eat("LPAREN")
        self.eat("RPAREN")
        return DataInstance(data_name)

    def parse_for(self):
        """Parse for loop: for i = 0 to 10 { body }"""
        self.eat("FOR")
        var_name = self.eat("IDENT")[1]
        self.eat("EQUALS")
        start = self.parse_expr()
        
        # Check direction
        is_downto = False
        if self.current() and self.current()[0] == "TO":
            self.eat("TO")
            is_downto = False
        elif self.current() and self.current()[0] == "DOWNTO":
            self.eat("DOWNTO")
            is_downto = True
        else:
            raise SyntaxError("Expected 'to' or 'downto' in for loop")
        
        end = self.parse_expr()
        
        # Optional step
        step = None
        if self.current() and self.current()[0] == "STEP":
            self.eat("STEP")
            step = self.parse_expr()
        
        body = self.parse_block()
        
        # Default step is 1
        if step is None:
            step = Number(1)
        
        return ForLoop(var_name, start, end, step, body, is_downto)

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def eat(self, kind):
        token = self.current()
        if token and token[0] == kind:
            self.pos += 1
            return token
        raise SyntaxError(f"Expected {kind}, got {token}")

    def skip_newlines(self):
        while self.current() and self.current()[0] == "NEWLINE":
            self.eat("NEWLINE")

    def parse_array_literal(self):
        """Parse array literal: [1, 2, 3]"""
        self.eat("LBRACK")
        elements = []
        
        if self.current() and self.current()[0] != "RBRACK":
            elements.append(self.parse_expr())
            while self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
                if self.current() and self.current()[0] != "RBRACK":
                    elements.append(self.parse_expr())
        
        self.eat("RBRACK")
        return ArrayLiteral(elements)

    # ---------------- EXPRESSIONS ----------------

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
        while self.current() and self.current()[0] in ("STAR", "SLASH", "PERCENT"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_unary()
            left = BinOp(left, op, right)
        return left

    def parse_unary(self):
        if self.current() and self.current()[0] in ("MINUS", "NOT"):
            op = self.eat(self.current()[0])[1]
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
        
        if kind == "LBRACK":
            return self.parse_array_literal()
        
        if kind == "ALLOC":
            return self.parse_alloc()
        
        if kind == "IDENT":
            name = self.eat("IDENT")[1]
            
            # Check for class instantiation: Player()
            if self.current() and self.current()[0] == "LPAREN":
                self.eat("LPAREN")
                # Check if there are any arguments
                if self.current() and self.current()[0] == "RPAREN":
                    # Check if it's a known class
                    if name in self.classes:
                        self.eat("RPAREN")
                        return ClassInstance(name)
                    # Check if it's a known data structure
                    elif name in self.data_structures:
                        self.eat("RPAREN")
                        return DataInstance(name)
                else:
                    # Function call with arguments
                    args = []
                    args.append(self.parse_expr())
                    while self.current() and self.current()[0] == "COMMA":
                        self.eat("COMMA")
                        if self.current() and self.current()[0] != "RPAREN":
                            args.append(self.parse_expr())
                    self.eat("RPAREN")
                    return Call(name, args)
            
            # Check for method call on instance: obj.method()
            if self.current() and self.current()[0] == "DOT":
                self.eat("DOT")
                method_name = self.eat("IDENT")[1]
                var = Variable(name)
                
                # Check if it's a method call with parentheses
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
                    return ClassMethodCall(var, method_name, args)
                
                # Regular attribute access
                pointer_props = ["value", "addr", "isValid", "isNull", "bytes"]
                if method_name in pointer_props:
                    if self.current() and self.current()[0] == "EQUALS":
                        self.eat("EQUALS")
                        value = self.parse_expr()
                        return PointerAssign(var, method_name, value)
                    return PointerProperty(var, method_name)
                else:
                    if self.current() and self.current()[0] == "EQUALS":
                        self.eat("EQUALS")
                        value = self.parse_expr()
                        return DataFieldAssign(var, method_name, value)
                    return DataFieldAccess(var, method_name)
            
            # Regular variable
            var = Variable(name)
            
            # Handle array indexing
            if self.current() and self.current()[0] == "LBRACK":
                self.eat("LBRACK")
                index = self.parse_expr()
                self.eat("RBRACK")
                if self.current() and self.current()[0] == "EQUALS":
                    self.eat("EQUALS")
                    value = self.parse_expr()
                    return ArraySet(var, index, value)
                return ArrayGet(var, index)
            
            return var
        
        raise SyntaxError(f"Unexpected token: {token}")


    def parse_alloc(self):
        self.eat("ALLOC")
        if not self.current() or self.current()[0] != "LPAREN":
            raise SyntaxError("Expected '(' after alloc")
        self.eat("LPAREN")
        size = self.parse_expr()
        self.eat("RPAREN")
        return Alloc(size)

    # ---------------- STATEMENTS ----------------

    def parse_statement(self):
        self.skip_newlines()
        token = self.current()
        if not token:
            return None
        kind = token[0]

        if kind == "CLASS":
            return self.parse_class()
        if kind == "IMPORT":
            return self.parse_import()
        if kind == "RAW":
            return self.parse_raw()
        if kind == "DEF":
            return self.parse_function()
        if kind == "DATA":  # ONLY call parse_data if we see DATA keyword
            return self.parse_data()
        if kind == "PRINT":
            self.eat("PRINT")
            self.eat("LPAREN")
            value = self.parse_expr()
            self.eat("RPAREN")
            return Print(value)
        if kind == "IF":
            return self.parse_if()
        if kind == "WHILE":
            return self.parse_while()
        if kind == "FOR":
            return self.parse_for()
        if kind == "RETURN":
            self.eat("RETURN")
            return Return(self.parse_expr())
        if kind == "BREAK":
            self.eat("BREAK")
            return Break()
        if kind == "CONTINUE":
            self.eat("CONTINUE")
            return Continue()
        if kind == "FREE":
            return self.parse_free()

        # Parse expression (assignment, function call, etc.)
        expr = self.parse_expr()
        
        # Check if this is an assignment
        if self.current() and self.current()[0] == "EQUALS":
            self.eat("EQUALS")
            value = self.parse_expr()
            
            if isinstance(expr, Variable):
                return Assignment(expr.name, value)
        
        return expr

    def parse_class(self):
        """Parse class definition"""
        self.eat("CLASS")
        name = self.eat("IDENT")[1]
        self.classes.append(name)
        
        # Check for inheritance
        parent = None
        if self.current() and self.current()[0] == "LPAREN":
            self.eat("LPAREN")
            parent = self.eat("IDENT")[1]
            self.eat("RPAREN")
        
        self.eat("LBRACE")
        methods = []
        
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            
            if self.current()[0] == "DEF":
                method = self.parse_function(is_method=True)
                methods.append(method)
            
            self.skip_newlines()
        
        self.eat("RBRACE")
        return Class(name, parent, methods)

    def parse_free(self):
        self.eat("FREE")
        if not self.current() or self.current()[0] != "LPAREN":
            raise SyntaxError("Expected '(' after free")
        self.eat("LPAREN")
        ptr = self.parse_expr()
        self.eat("RPAREN")
        return Free(ptr)

    def parse_function(self, is_method=False):
        """Parse function definition"""
        self.eat("DEF")
        name = self.eat("IDENT")[1]
        
        self.eat("LPAREN")
        params = []
        
        if self.current() and self.current()[0] != "RPAREN":
            params.append(self.eat("IDENT")[1])
            while self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
                params.append(self.eat("IDENT")[1])
        
        self.eat("RPAREN")
        self.eat("LBRACE")
        
        body = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            stmt = self.parse_statement()
            if stmt:
                body.append(stmt)
            self.skip_newlines()
        
        self.eat("RBRACE")
        return Function(name, params, body, is_method)

    def parse_block(self):
        self.eat("LBRACE")
        body = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            stmt = self.parse_statement()
            if stmt:
                body.append(stmt)
            self.skip_newlines()
        self.eat("RBRACE")
        return body

    def parse_import(self):
        self.eat("IMPORT")
        module_name = self.eat("IDENT")[1]
        return Import(module_name)

    def parse_raw(self):
        self.eat("RAW")
        self.eat("LBRACE")
        self.in_raw = True
        body = []
        exports = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break
            if self.current()[0] == "EXPORT":
                exp = self.parse_export()
                exports.extend(exp.names)
            else:
                stmt = self.parse_statement()
                if stmt:
                    body.append(stmt)
            self.skip_newlines()
        self.eat("RBRACE")
        self.in_raw = False
        return RawBlock(body, exports)

    def parse_export(self):
        self.eat("EXPORT")
        self.eat("LBRACE")
        items = []
        while self.current() and self.current()[0] != "RBRACE":
            items.append(self.eat("IDENT")[1])
            if self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
        self.eat("RBRACE")
        return Export(items)

    def parse_if(self):
        self.eat("IF")
        cond = self.parse_expr()
        then = self.parse_block()
        else_body = []
        if self.current() and self.current()[0] == "ELSE":
            self.eat("ELSE")
            else_body = self.parse_block()
        return IfElse(cond, then, else_body)

    def parse_while(self):
        self.eat("WHILE")
        cond = self.parse_expr()
        body = self.parse_block()
        return While(cond, body)

    def parse(self):
        program = []
        while self.current():
            self.skip_newlines()
            if not self.current():
                break
            stmt = self.parse_statement()
            if stmt:
                program.append(stmt)
        return program

