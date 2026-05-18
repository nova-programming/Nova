"""Abstract Syntax Tree node definitions"""

class Number:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"Number({self.value})"

class String:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"String({self.value})"

class Boolean:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"Boolean({self.value})"

class Variable:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"Variable({self.name})"

class UnaryOp:
    def __init__(self, op, value):
        self.op = op
        self.value = value
    def __repr__(self):
        return f"UnaryOp('{self.op}', {self.value})"

class BinOp:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"BinOp({self.left}, '{self.op}', {self.right})"

class Compare:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"Compare({self.left}, '{self.op}', {self.right})"

class Assignment:
    def __init__(self, name, value):
        self.name = name
        self.value = value
    def __repr__(self):
        return f"Assignment('{self.name}', {self.value})"

class Print:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"Print({self.value})"

# OOP Nodes
class Class:
    def __init__(self, name, parent, methods):
        self.name = name
        self.parent = parent  # For inheritance
        self.methods = methods  # List of Function nodes
    def __repr__(self):
        return f"Class('{self.name}', {self.parent}, {self.methods})"

class Function:
    def __init__(self, name, params, body, is_method=False):
        self.name = name
        self.params = params
        self.body = body
        self.is_method = is_method
    def __repr__(self):
        return f"Function('{self.name}', {self.params}, {self.body})"

class Call:
    def __init__(self, name, args, obj=None):
        self.name = name
        self.args = args
        self.obj = obj  # For method calls: obj.method()
    def __repr__(self):
        return f"Call('{self.name}', {self.args})"

class Attribute:
    def __init__(self, obj, attr):
        self.obj = obj
        self.attr = attr
    def __repr__(self):
        return f"Attribute({self.obj}, '{self.attr}')"

class Return:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"Return({self.value})"

class IfElse:
    def __init__(self, condition, if_body, else_body):
        self.condition = condition
        self.if_body = if_body
        self.else_body = else_body
    def __repr__(self):
        return f"IfElse({self.condition}, {self.if_body}, {self.else_body})"

class While:
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body
    def __repr__(self):
        return f"While({self.condition}, {self.body})"

class Break:
    def __repr__(self):
        return "Break()"

class Continue:
    def __repr__(self):
        return "Continue()"

# Low-level nodes
class RawBlock:
    def __init__(self, body, exports=None, mode="raw"):
        self.body = body
        self.exports = exports or []
        self.mode = mode
    def __repr__(self):
        return f"RawBlock({self.body}, {self.exports})"

class Export:
    def __init__(self, names):
        self.names = names
    def __repr__(self):
        return f"Export({self.names})"

class Import:
    def __init__(self, module, items=None, alias=None):
        self.module = module
        self.items = items or []
        self.alias = alias
    def __repr__(self):
        return f"Import('{self.module}', {self.items})"

# Data structure (low-level procedural)
class Data:
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields  # List of (name, type) tuples
    def __repr__(self):
        return f"Data('{self.name}', {self.fields})"

# Pointer nodes
class Alloc:
    def __init__(self, size, type_hint=None):
        self.size = size
        self.type_hint = type_hint
    def __repr__(self):
        return f"Alloc({self.size})"

class Free:
    def __init__(self, ptr):
        self.ptr = ptr
    def __repr__(self):
        return f"Free({self.ptr})"

class PointerProperty:
    def __init__(self, ptr, property_name):
        self.ptr = ptr
        self.property = property_name
    def __repr__(self):
        return f"PointerProperty({self.ptr}, '{self.property}')"

class PointerAssign:
    def __init__(self, ptr, property_name, value):
        self.ptr = ptr
        self.property = property_name
        self.value = value
    def __repr__(self):
        return f"PointerAssign({self.ptr}, '{self.property}', {self.value})"

class ArrayIndex:
    def __init__(self, base, index):
        self.base = base
        self.index = index
    def __repr__(self):
        return f"ArrayIndex({self.base}, {self.index})"

class ArrayIndexAssign:
    def __init__(self, base, index, value):
        self.base = base
        self.index = index
        self.value = value
    def __repr__(self):
        return f"ArrayIndexAssign({self.base}, {self.index}, {self.value})"

# Dynamic buffer nodes
class DynamicBuffer:
    def __init__(self, capacity):
        self.capacity = capacity
    def __repr__(self):
        return f"DynamicBuffer({self.capacity})"

class DynamicPush:
    def __init__(self, buffer, value):
        self.buffer = buffer
        self.value = value
    def __repr__(self):
        return f"DynamicPush({self.buffer}, {self.value})"

class DynamicProperty:
    def __init__(self, buffer, property_name):
        self.buffer = buffer
        self.property = property_name  # "used", "free", "capacity"
    def __repr__(self):
        return f"DynamicProperty({self.buffer}, '{self.property}')"

class NovaError(Exception):
    pass

def runtime_error(msg):
    raise NovaError(f"[Nova Runtime Error] {msg}")