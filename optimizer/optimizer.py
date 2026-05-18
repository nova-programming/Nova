from nova.ast.nodes import Number, BinOp, Compare, Alloc, Free


class Optimizer:
    def optimize(self, nodes):
        return [self.visit(n) for n in nodes if n is not None]

    def visit(self, node):
        if isinstance(node, BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            if isinstance(left, Number) and isinstance(right, Number):
                if node.op == "+":
                    return Number(left.value + right.value)
                if node.op == "-":
                    return Number(left.value - right.value)
                if node.op == "*":
                    return Number(left.value * right.value)
                if node.op == "/":
                    if right.value != 0:
                        return Number(left.value // right.value)
            return BinOp(left, node.op, right)
        
        if isinstance(node, Compare):
            left = self.visit(node.left)
            right = self.visit(node.right)
            if isinstance(left, Number) and isinstance(right, Number):
                if node.op == ">":
                    return Number(1 if left.value > right.value else 0)
                if node.op == "<":
                    return Number(1 if left.value < right.value else 0)
                if node.op == "==":
                    return Number(1 if left.value == right.value else 0)
                if node.op == "!=":
                    return Number(1 if left.value != right.value else 0)
                if node.op == ">=":
                    return Number(1 if left.value >= right.value else 0)
                if node.op == "<=":
                    return Number(1 if left.value <= right.value else 0)
            return Compare(left, node.op, right)
        
        if isinstance(node, Alloc):
            # Optimize constant size allocations
            size = self.visit(node.size)
            if isinstance(size, Number) and size.value <= 0:
                return None  # Remove zero-size allocations
            return Alloc(size, node.type_hint)
        
        if isinstance(node, list):
            return [self.visit(n) for n in node if n is not None]
        
        return node