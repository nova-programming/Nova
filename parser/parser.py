from nova.ast.nodes import *


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

        self.in_raw = False

        self.data_structures = []
        self.classes = []

    # =========================================================
    # BASIC HELPERS
    # =========================================================

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def match(self, kind):
        token = self.current()
        return token and token[0] == kind

    def eat(self, kind):
        token = self.current()

        if token and token[0] == kind:
            self.pos += 1
            return token

        raise SyntaxError(f"Expected {kind}, got {token}")

    def skip_newlines(self):
        while self.match("NEWLINE"):
            self.eat("NEWLINE")

    # =========================================================
    # EXPRESSIONS
    # =========================================================

    def parse_expr(self):
        return self.parse_logic()

    def parse_logic(self):
        left = self.parse_compare()

        while self.match("AND") or self.match("OR"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_compare()

            left = BinOp(left, op, right)

        return left

    def parse_compare(self):
        left = self.parse_add()

        compare_tokens = {
            "GT",
            "LT",
            "GE",
            "LE",
            "EQEQ",
            "NOTEQ"
        }

        while self.current() and self.current()[0] in compare_tokens:
            op = self.eat(self.current()[0])[1]
            right = self.parse_add()

            left = Compare(left, op, right)

        return left

    def parse_add(self):
        left = self.parse_mul()

        while self.match("PLUS") or self.match("MINUS"):
            op = self.eat(self.current()[0])[1]
            right = self.parse_mul()

            left = BinOp(left, op, right)

        return left

    def parse_mul(self):
        left = self.parse_unary()

        while (
            self.match("STAR")
            or self.match("SLASH")
            or self.match("PERCENT")
        ):
            op = self.eat(self.current()[0])[1]
            right = self.parse_unary()

            left = BinOp(left, op, right)

        return left

    def parse_unary(self):
        if self.match("MINUS") or self.match("NOT"):
            op = self.eat(self.current()[0])[1]
            return UnaryOp(op, self.parse_unary())

        return self.parse_primary()

    # =========================================================
    # PRIMARY EXPRESSIONS
    # =========================================================

    def parse_primary(self):
        token = self.current()

        if not token:
            raise SyntaxError("Unexpected EOF")

        kind, value = token

        # -----------------------------------------------------
        # NUMBERS
        # -----------------------------------------------------

        if kind == "NUMBER":
            self.eat("NUMBER")
            return Number(int(value))

        # -----------------------------------------------------
        # STRINGS
        # -----------------------------------------------------

        if kind == "STRING":
            self.eat("STRING")
            return String(value[1:-1])

        # -----------------------------------------------------
        # BOOLEANS
        # -----------------------------------------------------

        if kind == "TRUE":
            self.eat("TRUE")
            return Boolean(True)

        if kind == "FALSE":
            self.eat("FALSE")
            return Boolean(False)

        # -----------------------------------------------------
        # NULL
        # -----------------------------------------------------

        if kind == "NULL":
            self.eat("NULL")

            # null represented as integer zero
            return Number(0)

        # -----------------------------------------------------
        # GROUPED EXPRESSIONS
        # -----------------------------------------------------

        if kind == "LPAREN":
            self.eat("LPAREN")

            expr = self.parse_expr()

            self.eat("RPAREN")

            return expr

        # -----------------------------------------------------
        # ARRAY LITERALS
        # -----------------------------------------------------

        if kind == "LBRACK":
            return self.parse_array_literal()

        # -----------------------------------------------------
        # ALLOC
        # -----------------------------------------------------

        if kind == "ALLOC":
            return self.parse_alloc()

        # -----------------------------------------------------
        # IDENTIFIERS
        # -----------------------------------------------------

        if kind == "IDENT":
            return self.parse_identifier_chain()

        raise SyntaxError(f"Unexpected token: {token}")

    # =========================================================
    # IDENTIFIER / FIELD / METHOD CHAIN
    # =========================================================

    def parse_identifier_chain(self):
        name = self.eat("IDENT")[1]

        # -----------------------------------------------------
        # FUNCTION CALL / CONSTRUCTOR
        # -----------------------------------------------------

        if self.match("LPAREN"):
            return self.parse_call_or_constructor(name)

        # -----------------------------------------------------
        # BASE VARIABLE
        # -----------------------------------------------------

        node = Variable(name)

        # -----------------------------------------------------
        # CHAINED ACCESS
        # obj.field.method().x
        # -----------------------------------------------------

        while self.match("DOT"):
            self.eat("DOT")

            attr = self.eat("IDENT")[1]

            # METHOD CALL
            if self.match("LPAREN"):
                args = self.parse_argument_list()

                node = ClassMethodCall(
                    node,
                    attr,
                    args
                )

            # FIELD ACCESS
            else:
                if isinstance(node, Variable) and node.name == "self":
                    node = SelfFieldAccess(attr)
                else:
                    node = DataFieldAccess(node, attr)

        # -----------------------------------------------------
        # ARRAY INDEXING
        # -----------------------------------------------------

        while self.match("LBRACK"):
            self.eat("LBRACK")

            index = self.parse_expr()

            self.eat("RBRACK")

            node = ArrayGet(node, index)

        return node

    # =========================================================
    # FUNCTION CALLS / CONSTRUCTORS
    # =========================================================

    def parse_call_or_constructor(self, name):
        args = self.parse_argument_list()

        # class instance
        if name in self.classes:
            return ClassInstance(name)

        # data instance
        if name in self.data_structures:
            return DataInstance(name)

        return Call(name, args)

    def parse_argument_list(self):
        args = []

        self.eat("LPAREN")

        if not self.match("RPAREN"):
            args.append(self.parse_expr())

            while self.match("COMMA"):
                self.eat("COMMA")
                args.append(self.parse_expr())

        self.eat("RPAREN")

        return args

    # =========================================================
    # ARRAY LITERALS
    # =========================================================

    def parse_array_literal(self):
        self.eat("LBRACK")

        elements = []

        if not self.match("RBRACK"):
            elements.append(self.parse_expr())

            while self.match("COMMA"):
                self.eat("COMMA")
                elements.append(self.parse_expr())

        self.eat("RBRACK")

        return ArrayLiteral(elements)

    # =========================================================
    # ALLOC
    # =========================================================

    def parse_alloc(self):
        self.eat("ALLOC")

        self.eat("LPAREN")

        size = self.parse_expr()

        self.eat("RPAREN")

        return Alloc(size)

    # =========================================================
    # STATEMENTS
    # =========================================================

    def parse_statement(self):
        print("PARSE STATEMENT:", self.tokens[self.pos])

        if self.match("EXPORT"):
            return self.parse_export()

        self.skip_newlines()

        token = self.current()

        if self.pos >= len(self.tokens):
            return None

        kind = token[0]

        # -----------------------------------------------------
        # TOP LEVEL
        # -----------------------------------------------------

        if kind == "CLASS":
            return self.parse_class()


        if kind == "DATA":
            return self.parse_data()

        if kind == "DEF":
            return self.parse_function()

        if kind == "RAW":
            return self.parse_raw()

        if kind == "IMPORT":
            return self.parse_import()

        # -----------------------------------------------------
        # CONTROL FLOW
        # -----------------------------------------------------

        if kind == "IF":
            return self.parse_if()

        if kind == "WHILE":
            return self.parse_while()

        if kind == "FOR":
            return self.parse_for()

        # -----------------------------------------------------
        # LOOP CONTROL
        # -----------------------------------------------------

        if kind == "BREAK":
            self.eat("BREAK")
            return Break()

        if kind == "CONTINUE":
            self.eat("CONTINUE")
            return Continue()

        # -----------------------------------------------------
        # RETURN
        # -----------------------------------------------------

        if kind == "RETURN":
            self.eat("RETURN")
            return Return(self.parse_expr())

        # -----------------------------------------------------
        # PRINT
        # -----------------------------------------------------

        if kind == "PRINT":
            self.eat("PRINT")

            self.eat("LPAREN")

            value = self.parse_expr()

            self.eat("RPAREN")

            return Print(value)

        # -----------------------------------------------------
        # FREE
        # -----------------------------------------------------

        if kind == "FREE":
            return self.parse_free()

        # -----------------------------------------------------
        # GENERAL EXPRESSION
        # -----------------------------------------------------

        expr = self.parse_expr()

        # -----------------------------------------------------
        # ASSIGNMENT
        # -----------------------------------------------------

        if self.match("EQUALS"):
            self.eat("EQUALS")

            rhs = self.parse_expr()

            # variable assignment
            if isinstance(expr, Variable):
                return Assignment(expr.name, rhs)

            # self.field = value
            if isinstance(expr, SelfFieldAccess):
                return SelfFieldAssign(
                    expr.field_name,
                    rhs
                )

            # obj.field = value
            if isinstance(expr, DataFieldAccess):
                return DataFieldAssign(
                    expr.instance,
                    expr.field_name,
                    rhs
                )

            # arr[i] = value
            if isinstance(expr, ArrayGet):
                return ArraySet(
                    expr.array,
                    expr.index,
                    rhs
                )

        return expr

    # =========================================================
    # FREE
    # =========================================================

    def parse_free(self):
        self.eat("FREE")

        self.eat("LPAREN")

        ptr = self.parse_expr()

        self.eat("RPAREN")

        return Free(ptr)

    # =========================================================
    # DATA STRUCTURES
    # =========================================================

    def parse_export(self):

        self.eat("EXPORT")
        self.eat("LBRACE")

        names = []

        while not self.match("RBRACE"):

            if self.match("IDENT"):

                names.append(
                    self.eat("IDENT")[1]
                )

                if self.match("COMMA"):
                    self.eat("COMMA")

            else:
                raise Exception(
                    "Expected identifier in export block"
                )

        self.eat("RBRACE")

        return Export(names)


    def parse_data(self):
        self.eat("DATA")

        name = self.eat("IDENT")[1]

        self.data_structures.append(name)

        self.eat("LBRACE")

        fields = []

        while not self.match("RBRACE"):
            self.skip_newlines()

            if self.match("RBRACE"):
                break

            field_name = self.eat("IDENT")[1]

            self.eat("COLON")

            type_token = self.current()

            if type_token[0] in (
                "TYPE_INT",
                "TYPE_FLOAT",
                "TYPE_BOOL",
                "TYPE_STRING"
            ):
                type_name = self.eat(type_token[0])[1]
            else:
                type_name = self.eat("IDENT")[1]

            fields.append((field_name, type_name))

            if self.match("NEWLINE") or self.match("SEMICOLON"):
                self.eat(self.current()[0])

        self.eat("RBRACE")

        return Data(name, fields)

    # =========================================================
    # CLASSES
    # =========================================================

    def parse_class(self):
        self.eat("CLASS")

        name = self.eat("IDENT")[1]

        self.classes.append(name)

        parent = None

        if self.match("LPAREN"):
            self.eat("LPAREN")

            parent = self.eat("IDENT")[1]

            self.eat("RPAREN")

        self.eat("LBRACE")

        methods = []
        fields = []

        while not self.match("RBRACE"):
            self.skip_newlines()

            if self.match("RBRACE"):
                break

            if self.match("DEF"):
                method = self.parse_function(is_method=True)
                methods.append(method)

            elif self.match("IDENT"):
                field_name = self.eat("IDENT")[1]

                self.eat("COLON")

                type_token = self.current()

                if type_token[0] in (
                    "TYPE_INT",
                    "TYPE_FLOAT",
                    "TYPE_BOOL",
                    "TYPE_STRING"
                ):
                    field_type = self.eat(type_token[0])[1]
                else:
                    field_type = self.eat("IDENT")[1]

                fields.append((field_name, field_type))

            self.skip_newlines()

        self.eat("RBRACE")

        return Class(name, parent, fields, methods)

    # =========================================================
    # FUNCTIONS
    # =========================================================

    def parse_function(self, is_method=False):
        self.eat("DEF")

        name = self.eat("IDENT")[1]

        self.eat("LPAREN")

        params = []

        if not self.match("RPAREN"):
            params.append(self.eat("IDENT")[1])

            while self.match("COMMA"):
                self.eat("COMMA")
                params.append(self.eat("IDENT")[1])

        self.eat("RPAREN")

        # inject self for methods
        if is_method and (
            not params or params[0] != "self"
        ):
            params.insert(0, "self")

        body = self.parse_block()

        return Function(
            name,
            params,
            body,
            is_method
        )

    # =========================================================
    # BLOCKS
    # =========================================================

    def parse_block(self):
        self.eat("LBRACE")

        body = []

        while not self.match("RBRACE"):
            self.skip_newlines()

            if self.match("RBRACE"):
                break

            stmt = self.parse_statement()

            if stmt:
                body.append(stmt)

            self.skip_newlines()

        self.eat("RBRACE")

        return body

    # =========================================================
    # IMPORTS
    # =========================================================

    def parse_import(self):
        self.eat("IMPORT")

        module_name = self.eat("IDENT")[1]

        return Import(module_name)

    # =========================================================
    # RAW BLOCKS
    # =========================================================

    def parse_raw(self):

        self.eat("RAW")
        self.eat("LBRACE")

        body = []

        while not self.match("RBRACE"):

            stmt = self.parse_statement()

            if stmt is not None:
                body.append(stmt)

        self.eat("RBRACE")

        return RawBlock(body)

    # =========================================================
    # EXPORTS
    # =========================================================

    def parse_export(self):
        self.eat("EXPORT")

        self.eat("LBRACE")

        items = []

        while not self.match("RBRACE"):
            items.append(self.eat("IDENT")[1])

            if self.match("COMMA"):
                self.eat("COMMA")

        self.eat("RBRACE")

        return Export(items)

    # =========================================================
    # IF
    # =========================================================

    def parse_if(self):
        self.eat("IF")

        condition = self.parse_expr()

        if_body = self.parse_block()

        else_body = []

        if self.match("ELSE"):
            self.eat("ELSE")
            else_body = self.parse_block()

        return IfElse(
            condition,
            if_body,
            else_body
        )

    # =========================================================
    # WHILE
    # =========================================================

    def parse_while(self):
        self.eat("WHILE")

        condition = self.parse_expr()

        body = self.parse_block()

        return While(condition, body)

    # =========================================================
    # FOR
    # =========================================================

    def parse_for(self):
        self.eat("FOR")

        var_name = self.eat("IDENT")[1]

        self.eat("EQUALS")

        start = self.parse_expr()

        is_downto = False

        if self.match("TO"):
            self.eat("TO")

        elif self.match("DOWNTO"):
            self.eat("DOWNTO")
            is_downto = True

        else:
            raise SyntaxError(
                "Expected 'to' or 'downto'"
            )

        end = self.parse_expr()

        step = Number(1)

        if self.match("STEP"):
            self.eat("STEP")
            step = self.parse_expr()

        body = self.parse_block()

        return ForLoop(
            var_name,
            start,
            end,
            step,
            body,
            is_downto
        )

    # =========================================================
    # PROGRAM
    # =========================================================

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