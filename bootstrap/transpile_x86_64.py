import ast

def to_nova(node):
    if isinstance(node, ast.Module):
        return "\n".join(to_nova(stmt) for stmt in node.body if isinstance(stmt, (ast.FunctionDef, ast.ClassDef, ast.If)))
    elif isinstance(node, ast.ClassDef):
        return "\n".join(to_nova(stmt) for stmt in node.body)
    elif isinstance(node, ast.FunctionDef):
        if node.name.startswith("__"): return ""
        # Convert args
        args = ["state: CodegenState", "node: AstNode"]
        body = "\n".join(to_nova(stmt) for stmt in node.body)
        return f"def {node.name}({', '.join(args)}) {{\n{body}\n}}\n"
    elif isinstance(node, ast.If):
        test = to_nova(node.test)
        body = "\n".join(to_nova(stmt) for stmt in node.body)
        orelse = ""
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                orelse = f" elif {to_nova(node.orelse[0].test)} {{\n" + "\n".join(to_nova(s) for s in node.orelse[0].body) + "\n}"
                # Handle nested elifs manually or recursively
            else:
                orelse = " else {\n" + "\n".join(to_nova(stmt) for stmt in node.orelse) + "\n}"
        return f"if {test} {{\n{body}\n}}{orelse}"
    elif isinstance(node, ast.Call):
        func = to_nova(node.func)
        args = ", ".join(to_nova(arg) for arg in node.args)
        if func == "self.assembly.append":
            return f"emit(state, {args})"
        if func == "self.data_section.append":
            return f"emit_data(state, {args})"
        if func.startswith("self."):
            func = func.replace("self.", "")
            return f"{func}(state, {args})"
        if func == "isinstance":
            var = to_nova(node.args[0])
            type_name = node.args[1].id
            return f"{var}.kind == \"{type_name}\""
        return f"{func}({args})"
    elif isinstance(node, ast.Attribute):
        val = to_nova(node.value)
        if val == "self": return "state." + node.attr
        return f"{val}.{node.attr}"
    elif isinstance(node, ast.Name):
        if node.id == "self": return "state"
        if node.id == "True": return "1"
        if node.id == "False": return "0"
        return node.id
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return f'"{node.value}"'
        return str(node.value)
    elif isinstance(node, ast.JoinedStr):
        # Convert f-string to concatenation
        parts = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                parts.append(f'"{val.value}"')
            elif isinstance(val, ast.FormattedValue):
                expr = to_nova(val.value)
                parts.append(f"str({expr})" if "str(" not in expr else expr)
        return " + ".join(parts)
    elif isinstance(node, ast.Return):
        if node.value:
            return f"return {to_nova(node.value)}"
        return "return"
    elif isinstance(node, ast.Assign):
        targets = " = ".join(to_nova(t) for t in node.targets)
        return f"{targets} = {to_nova(node.value)}"
    elif isinstance(node, ast.Expr):
        return to_nova(node.value)
    return f"/* UNHANDLED: {type(node).__name__} */"

with open("compiler/backend/x86_64/codegen.py") as f:
    tree = ast.parse(f.read())
print(to_nova(tree))
