"""Abstract Syntax Tree node definitions with pointer support"""

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

class Function:
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body
    def __repr__(self):
        return f"Function('{self.name}', {self.params}, {self.body})"

class Call:
    def __init__(self, name, args):
        self.name = name
        self.args = args
    def __repr__(self):
        return f"Call('{self.name}', {self.args})"

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

class RawBlock:
    def __init__(self, body, exports=None):
        self.body = body
        self.exports = exports or []
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

class Attribute:
    def __init__(self, obj, attr):
        self.obj = obj
        self.attr = attr
    def __repr__(self):
        return f"Attribute({self.obj}, '{self.attr}')"

# ========== NEW POINTER NODES ==========

class Alloc:
    def __init__(self, size):
        self.size = size
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
        self.property = property_name  # "value", "addr", "isValid", "isNull", "bytes"
    def __repr__(self):
        return f"PointerProperty({self.ptr}, '{self.property}')"

class PointerAssign:
    def __init__(self, ptr, property_name, value):
        self.ptr = ptr
        self.property = property_name
        self.value = value
    def __repr__(self):
        return f"PointerAssign({self.ptr}, '{self.property}', {self.value})"

class PointerOffset:
    def __init__(self, ptr, offset):
        self.ptr = ptr
        self.offset = offset
    def __repr__(self):
        return f"PointerOffset({self.ptr}, {self.offset})"

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

class NovaError(Exception):
    pass

def runtime_error(msg):
    raise NovaError(f"[Nova Runtime Error] {msg}")

# ========== DATA STRUCTURE NODES ==========

class Data:
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields  # List of (name, type) tuples
    def __repr__(self):
        return f"Data('{self.name}', {self.fields})"

class DataField:
    def __init__(self, name, type_name):
        self.name = name
        self.type_name = type_name
    def __repr__(self):
        return f"DataField('{self.name}', '{self.type_name}')"

class DataInstance:
    def __init__(self, data_name):
        self.data_name = data_name
    def __repr__(self):
        return f"DataInstance('{self.data_name}')"

class DataFieldAccess:
    def __init__(self, instance, field_name):
        self.instance = instance
        self.field_name = field_name
    def __repr__(self):
        return f"DataFieldAccess({self.instance}, '{self.field_name}')"

class DataFieldAssign:
    def __init__(self, instance, field_name, value):
        self.instance = instance
        self.field_name = field_name
        self.value = value
    def __repr__(self):
        return f"DataFieldAssign({self.instance}, '{self.field_name}', {self.value})"