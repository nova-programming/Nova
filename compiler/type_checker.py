from ast.nodes import *


class StaticTypeError(Exception):
    pass


class TypeChecker:
    def __init__(self):
        self.env_stack = [{}]
        self.functions = {}
        self.current_function_return_type = None
        self.in_raw = False  # Track if we're inside a @raw block
        self.const_vars = set()  # Track const variable names

    def push_env(self):
        self.env_stack.append({})

    def pop_env(self):
        self.env_stack.pop()

    def visit(self, node):
        if node is None:
            return "any"
        if hasattr(self, f"visit_{type(node).__name__}"):
            t = getattr(self, f"visit_{type(node).__name__}")(node)
            node.inferred_type = t
            return t
        node.inferred_type = "any"
        return "any"

    def check(self, ast):
        # Pass 1: Register function signatures
        for stmt in ast:
            if isinstance(stmt, Function):
                self.functions[stmt.name] = {
                    "params": stmt.params,
                    "return_type": stmt.return_type
                }

        # Pass 2: Type check everything
        for stmt in ast:
            self.visit(stmt)

    def visit_Number(self, node):
        return "int" if isinstance(node.value, int) else "float"

    def visit_String(self, node):
        return "string"

    def visit_Boolean(self, node):
        return "bool"

    def visit_Assignment(self, node):
        t = self.visit(node.value)

        # Check for const reassignment
        if not node.is_const and not node.is_mut:
            if node.name in self.const_vars:
                raise StaticTypeError(f"Cannot reassign const variable '{node.name}'")

        # Track const variables
        if node.is_const:
            self.const_vars.add(node.name)

        if node.is_mut:
            self.env_stack[-1][node.name] = "dyn"
        else:
            found_env = None
            for env in reversed(self.env_stack):
                if node.name in env:
                    found_env = env
                    break

            if found_env is not None:
                if found_env[node.name] != "dyn" and found_env[node.name] != t and found_env[node.name] != "any" and t != "any":
                    raise StaticTypeError(f"Cannot assign {t} to variable of type {found_env[node.name]}")
            else:
                self.env_stack[-1][node.name] = node.type_name if node.type_name else t
        return t

    def visit_Variable(self, node):
        for env in reversed(self.env_stack):
            if node.name in env:
                return env[node.name]
        return "any"

    def visit_UnaryOp(self, node):
        return self.visit(node.value)

    def visit_BinOp(self, node):
        left_t = self.visit(node.left)
        right_t = self.visit(node.right)
        if left_t != right_t and left_t != "dyn" and right_t != "dyn" and left_t != "any" and right_t != "any":
            raise StaticTypeError(f"Type Error in binary operation: {left_t} {node.op} {right_t}")
        return left_t

    def visit_Function(self, node):
        self.push_env()
        prev_return_type = self.current_function_return_type
        self.current_function_return_type = node.return_type if node.return_type else "any"

        for param_name, param_type in node.params:
            self.env_stack[-1][param_name] = param_type if param_type else "any"

        for stmt in node.body:
            self.visit(stmt)

        self.current_function_return_type = prev_return_type
        self.pop_env()

    def visit_Return(self, node):
        t = self.visit(node.value)
        if self.current_function_return_type and self.current_function_return_type != "any":
            if t != "dyn" and t != "any" and t != self.current_function_return_type:
                raise StaticTypeError(f"Return type {t} does not match function signature {self.current_function_return_type}")
        return t

    def visit_Call(self, node):
        if node.name in self.functions:
            func_meta = self.functions[node.name]
            params = func_meta["params"]
            if len(node.args) != len(params):
                raise StaticTypeError(f"Function {node.name} expects {len(params)} args, got {len(node.args)}")

            for arg, (param_name, param_type) in zip(node.args, params):
                arg_t = self.visit(arg)
                if param_type and param_type != "any" and arg_t != "dyn" and arg_t != "any" and arg_t != param_type:
                    raise StaticTypeError(f"Argument type mismatch for {node.name}: expected {param_type}, got {arg_t}")

            return func_meta["return_type"] if func_meta["return_type"] else "any"

        # If not globally known (e.g., builtin or from FFI)
        for arg in node.args:
            self.visit(arg)
        return "any"

    def visit_IfElse(self, node):
        self.visit(node.condition)
        self.push_env()
        for stmt in node.if_body:
            self.visit(stmt)
        self.pop_env()

        self.push_env()
        for stmt in node.else_body:
            self.visit(stmt)
        self.pop_env()

    def visit_While(self, node):
        self.visit(node.condition)
        self.push_env()
        for stmt in node.body:
            self.visit(stmt)
        self.pop_env()

    def visit_ForLoop(self, node):
        self.push_env()
        start_t = self.visit(node.start)
        self.env_stack[-1][node.var_name] = start_t
        self.visit(node.end)
        self.visit(node.step)

        for stmt in node.body:
            self.visit(stmt)
        self.pop_env()

    def visit_ClassDef(self, node):
        # We can implement full OOP type checking, but for now we skip method bodies or just visit them
        for method in node.methods:
            self.visit(method)

    def visit_MethodCall(self, node):
        self.visit(node.instance)
        for arg in node.args:
            self.visit(arg)
        return "any"

    def visit_Print(self, node):
        self.visit(node.value)

    def visit_Import(self, node):
        # Import type checking is a no-op; the compiler handles resolution
        pass

    def visit_RawBlock(self, node):
        # Enter @raw context — unsafe operations allowed
        prev_raw = self.in_raw
        self.in_raw = True
        for stmt in node.body:
            self.visit(stmt)
        self.in_raw = prev_raw

    def visit_Export(self, node):
        # Export is handled inside @raw blocks
        pass

    def visit_Data(self, node):
        # Data struct definitions are type-checked passively
        pass

    def visit_Compare(self, node):
        self.visit(node.left)
        self.visit(node.right)
        return "bool"

    def visit_UnaryOp(self, node):
        return self.visit(node.value)

    def visit_DataFieldAssign(self, node):
        self.visit(node.instance)
        return self.visit(node.value)

    def visit_DataFieldAccess(self, node):
        self.visit(node.instance)
        return "any"

    def visit_LoadLib(self, node):
        pass

    def visit_Alloc(self, node):
        if not self.in_raw:
            raise StaticTypeError("alloc() is only available inside @raw blocks")
        self.visit(node.size)
        return "any"

    def visit_Free(self, node):
        if not self.in_raw:
            raise StaticTypeError("free() is only available inside @raw blocks")
        self.visit(node.ptr)

    def visit_PointerProperty(self, node):
        if not self.in_raw:
            raise StaticTypeError("Pointer operations are only available inside @raw blocks")
        self.visit(node.ptr)
        return "any"

    def visit_PointerAssign(self, node):
        if not self.in_raw:
            raise StaticTypeError("Pointer operations are only available inside @raw blocks")
        self.visit(node.ptr)
        self.visit(node.value)

    def visit_ArrayIndex(self, node):
        self.visit(node.base)
        self.visit(node.index)
        return "any"

    def visit_ArrayIndexAssign(self, node):
        self.visit(node.base)
        self.visit(node.index)
        self.visit(node.value)

    def visit_SizeOf(self, node):
        self.visit(node.target)
        return "int"

    def visit_Len(self, node):
        self.visit(node.target)
        return "int"

    def visit_StrConvert(self, node):
        self.visit(node.target)
        return "string"

    def visit_OpenFile(self, node):
        self.visit(node.path)
        self.visit(node.mode)
        return "int"

    def visit_ReadFile(self, node):
        self.visit(node.fd)
        return "string"

    def visit_WriteFile(self, node):
        self.visit(node.fd)
        self.visit(node.content)

    def visit_CloseFile(self, node):
        self.visit(node.fd)

    def visit_Self(self, node):
        return "any"

    def visit_Break(self, node):
        pass

    def visit_Continue(self, node):
        pass

    def visit_ListLiteral(self, node):
        for element in node.elements:
            self.visit(element)
        return "any"

    def visit_DictLiteral(self, node):
        for k, v in zip(node.keys, node.values):
            self.visit(k)
            self.visit(v)
        return "any"

    def visit_Assignment(self, node):
        return "any"

    def visit_DataInstance(self, node):
        return "any"
