from ast.nodes import *


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.in_raw = False

    def parse_data(self):
        """Parse data structure definition"""
        self.eat("DATA")
        name = self.eat("IDENT")[1]
        
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
            
            # Optional semicolon or newline
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
        ops = {"GT", "LT", "GE", "LE", "EQEQ", "NOTEQ", "HAS"}
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
        while self.current() and self.current()[0] in ("STAR", "SLASH", "PERCENT", "AMPERSAND", "GTGT", "LTLT"):
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

        node = None

        if kind == "NUMBER":
            self.eat("NUMBER")
            node = Number(int(value))
        
        elif kind == "STRING":
            self.eat("STRING")
            node = String(value[1:-1])
        
        elif kind == "TRUE":
            self.eat("TRUE")
            node = Boolean(True)
        
        elif kind == "FALSE":
            self.eat("FALSE")
            node = Boolean(False)
        
        elif kind == "LPAREN":
            self.eat("LPAREN")
            node = self.parse_expr()
            self.eat("RPAREN")

        elif kind == "SIZEOF":
            self.eat("SIZEOF")
            self.eat("LPAREN")
            target = self.parse_expr()
            self.eat("RPAREN")
            node = SizeOf(target)

        elif kind == "LEN":
            self.eat("LEN")
            self.eat("LPAREN")
            target = self.parse_expr()
            self.eat("RPAREN")
            node = Len(target)

        elif kind == "STR":
            self.eat("STR")
            self.eat("LPAREN")
            target = self.parse_expr()
            self.eat("RPAREN")
            node = StrConvert(target)

        elif kind == "OPEN":
            self.eat("OPEN")
            self.eat("LPAREN")
            path = self.parse_expr()
            self.eat("COMMA")
            mode = self.parse_expr()
            self.eat("RPAREN")
            node = OpenFile(path, mode)

        elif kind == "READ":
            self.eat("READ")
            self.eat("LPAREN")
            fd = self.parse_expr()
            self.eat("RPAREN")
            node = ReadFile(fd)

        elif kind == "SELF":
            self.eat("SELF")
            node = Self()
        
        elif kind == "ALLOC":
            node = self.parse_alloc()
        
        elif kind == "LBRACK":
            self.eat("LBRACK")
            elements = []
            if self.current() and self.current()[0] != "RBRACK":
                elements.append(self.parse_expr())
                while self.current() and self.current()[0] == "COMMA":
                    self.eat("COMMA")
                    if self.current() and self.current()[0] != "RBRACK":
                        elements.append(self.parse_expr())
            self.eat("RBRACK")
            node = ListLiteral(elements)

        elif kind == "LBRACE":
            self.eat("LBRACE")
            keys = []
            values = []
            if self.current() and self.current()[0] != "RBRACE":
                keys.append(self.parse_expr())
                self.eat("COLON")
                values.append(self.parse_expr())
                while self.current() and self.current()[0] == "COMMA":
                    self.eat("COMMA")
                    if self.current() and self.current()[0] != "RBRACE":
                        keys.append(self.parse_expr())
                        self.eat("COLON")
                        values.append(self.parse_expr())
            self.eat("RBRACE")
            node = DictLiteral(keys, values)

        elif kind == "IDENT":
            name = self.eat("IDENT")[1]
            
            # Check for function call / class instantiation / data instantiation
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
                node = Call(name, args)
            else:
                node = Variable(name)
        else:
            raise SyntaxError(f"Unexpected token: {token}")

        # Now, parse trailing suffix operators (. and [) in a loop
        while True:
            if not self.current():
                break
            
            next_kind = self.current()[0]
            if next_kind == "DOT":
                self.eat("DOT")
                prop = self.eat("IDENT")[1]
                
                # Method call?
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
                    node = MethodCall(node, prop, args)
                    continue
                
                # Pointer property vs Data field
                pointer_properties = ["value", "addr", "isValid", "isNull", "bytes"]
                if prop in pointer_properties:
                    if self.current() and self.current()[0] == "EQUALS":
                        self.eat("EQUALS")
                        value = self.parse_expr()
                        return PointerAssign(node, prop, value)
                    node = PointerProperty(node, prop)
                else:
                    if self.current() and self.current()[0] == "EQUALS":
                        self.eat("EQUALS")
                        value = self.parse_expr()
                        return DataFieldAssign(node, prop, value)
                    node = DataFieldAccess(node, prop)
                continue
                
            elif next_kind == "LBRACK":
                self.eat("LBRACK")

                # Check for slice syntax [start:end] or [:end] or [start:]
                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    end_expr = self.parse_expr() if self.current() and self.current()[0] != "RBRACK" else None
                    self.eat("RBRACK")
                    node = Slice(node, None, end_expr)
                    continue

                index = self.parse_expr()
                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    end_expr = self.parse_expr() if self.current() and self.current()[0] != "RBRACK" else None
                    self.eat("RBRACK")
                    node = Slice(node, index, end_expr)
                    continue

                self.eat("RBRACK")
                if self.current() and self.current()[0] == "EQUALS":
                    self.eat("EQUALS")
                    value = self.parse_expr()
                    return ArrayIndexAssign(node, index, value)
                node = ArrayIndex(node, index)
                continue
                
            else:
                break
                
        return node

    def parse_alloc(self):
        self.eat("ALLOC")
        if not self.current() or self.current()[0] != "LPAREN":
            raise SyntaxError("Expected '(' after alloc")
        self.eat("LPAREN")
        size = self.parse_expr()
        self.eat("RPAREN")
        return Alloc(size)

    # ---------------- STATEMENTS ----------------

    def parse_class(self):
        self.eat("CLASS")
        name = self.eat("IDENT")[1]
        self.eat("LBRACE")
        methods = []
        fields = []
        while self.current() and self.current()[0] != "RBRACE":
            self.skip_newlines()
            if self.current()[0] == "RBRACE":
                break

            # Simple field vs method parsing
            if self.current()[0] == "DEF":
                methods.append(self.parse_function())
            else:
                field_name = self.eat("IDENT")[1]
                field_type = None

                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    if self.current()[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING"):
                        field_type = self.eat(self.current()[0])[1]
                    else:
                        field_type = self.eat("IDENT")[1]

                # Default assignments in class body not yet supported, just taking names
                if self.current() and self.current()[0] == "EQUALS":
                    self.eat("EQUALS")
                    self.parse_expr() # Skip initial values for now
                fields.append((field_name, field_type))
            self.skip_newlines()

        self.eat("RBRACE")
        return ClassDef(name, methods, fields)

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
        if kind == "FOR":
            return self.parse_for()
        if kind == "DEF":
            return self.parse_function()
        if kind == "PRINT":
            self.eat("PRINT")
            self.eat("LPAREN")
            value = self.parse_expr()
            self.eat("RPAREN")
            return Print(value)
        if kind == "WRITE":
            self.eat("WRITE")
            self.eat("LPAREN")
            fd = self.parse_expr()
            self.eat("COMMA")
            content = self.parse_expr()
            self.eat("RPAREN")
            return WriteFile(fd, content)
        if kind == "CLOSE":
            self.eat("CLOSE")
            self.eat("LPAREN")
            fd = self.parse_expr()
            self.eat("RPAREN")
            return CloseFile(fd)
        if kind == "IF":
            return self.parse_if()
        if kind == "WHILE":
            return self.parse_while()
        if kind == "RETURN":
            self.eat("RETURN")
            if self.current() and self.current()[0] in ('RBRACE', 'NEWLINE', 'EOF'):
                return Return(Number(0))
            return Return(self.parse_expr())
        if kind == "BREAK":
            self.eat("BREAK")
            return Break()
        if kind == "CONTINUE":
            self.eat("CONTINUE")
            return Continue()
        if kind == "FREE":
            return self.parse_free()
        if kind == "DATA":
            return self.parse_data()

        is_const = False
        type_name = None
        if kind == "CONST":
            self.eat("CONST")
            is_const = True
            token = self.current()
            kind = token[0]

        expr = self.parse_expr()

        if isinstance(expr, Variable) and self.current() and self.current()[0] == "COLON":
            self.eat("COLON")
            if self.current()[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING"):
                type_name = self.eat(self.current()[0])[1]
            else:
                type_name = self.eat("IDENT")[1]
            expr.type_name = type_name

        if self.current() and self.current()[0] == "EQUALS":
            self.eat("EQUALS")
            value = self.parse_expr()
            if isinstance(expr, Variable):
                return Assignment(expr.name, value, type_name=expr.type_name, is_const=is_const)
        return expr

    def parse_free(self):
        self.eat("FREE")
        if not self.current() or self.current()[0] != "LPAREN":
            raise SyntaxError("Expected '(' after free")
        self.eat("LPAREN")
        ptr = self.parse_expr()
        self.eat("RPAREN")
        return Free(ptr)

    def parse_function(self):
        self.eat("DEF")
        name = self.eat("IDENT")[1]
        self.eat("LPAREN")
        params = []
        if self.current() and self.current()[0] != "RPAREN":
            param_name = self.eat("IDENT")[1]
            param_type = None
            if self.current() and self.current()[0] == "COLON":
                self.eat("COLON")
                if self.current()[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING"):
                    param_type = self.eat(self.current()[0])[1]
                else:
                    param_type = self.eat("IDENT")[1]
            params.append((param_name, param_type))

            while self.current() and self.current()[0] == "COMMA":
                self.eat("COMMA")
                param_name = self.eat("IDENT")[1]
                param_type = None
                if self.current() and self.current()[0] == "COLON":
                    self.eat("COLON")
                    if self.current()[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING"):
                        param_type = self.eat(self.current()[0])[1]
                    else:
                        param_type = self.eat("IDENT")[1]
                params.append((param_name, param_type))
        self.eat("RPAREN")

        return_type = None
        if self.current() and self.current()[0] == "ARROW":
            self.eat("ARROW")
            if self.current()[0] in ("TYPE_INT", "TYPE_FLOAT", "TYPE_BOOL", "TYPE_STRING"):
                return_type = self.eat(self.current()[0])[1]
            else:
                return_type = self.eat("IDENT")[1]

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
        return Function(name, params, body, return_type=return_type)

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

        # Check if it's an FFI string import `import "c" as libc`
        if self.current() and self.current()[0] == "STRING":
            lib_path = self.eat("STRING")[1][1:-1] # Remove quotes
            self.eat("AS")
            alias = self.eat("IDENT")[1]
            return LoadLib(lib_path, alias)

        # Standard .nv module import `import math` or `import math as m`
        module_name = self.eat("IDENT")[1]
        alias = None
        if self.current() and self.current()[0] == "AS":
            self.eat("AS")
            alias = self.eat("IDENT")[1]
        return Import(module_name, alias=alias)

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
        else_body = self._parse_if_tail()
        return IfElse(cond, then, else_body)

    def _parse_if_tail(self):
        """Parse the optional else/elif tail of an if statement."""
        if not self.current():
            return []
        if self.current()[0] == "ELIF":
            self.eat("ELIF")
            elif_cond = self.parse_expr()
            elif_body = self.parse_block()
            tail = self._parse_if_tail()
            return [IfElse(elif_cond, elif_body, tail)]
        if self.current()[0] == "ELSE":
            self.eat("ELSE")
            return self.parse_block()
        return []

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

