from ast.nodes import *

class StaticTypeError(Exception):
    pass

class TypeChecker:
    def __init__(self):
        self.env_stack = [{}]
        self.functions = {}
        self.current_function_return_type = None

    def push_env(self):
        self.env_stack.append({})

    def pop_env(self):
        self.env_stack.pop()

    def visit(self, node):
        if node is None:
            return "any"
        if hasattr(self, f"visit_{type(node).__name__}"):
            return getattr(self, f"visit_{type(node).__name__}")(node)
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
