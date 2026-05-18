"""Abstract Syntax Tree node definitions for Nova"""

# =========================================================
# BASIC EXPRESSIONS
# =========================================================
class Node:
    pass

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


# =========================================================
# STATEMENTS
# =========================================================

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


class Return:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Return({self.value})"


class Call:
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def __repr__(self):
        return f"Call('{self.name}', {self.args})"


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


class ForLoop:
    def __init__(self, var_name, start, end, step, body, is_downto=False):
        self.var_name = var_name
        self.start = start
        self.end = end
        self.step = step
        self.body = body
        self.is_downto = is_downto

    def __repr__(self):
        return (
            f"ForLoop('{self.var_name}', "
            f"{self.start}, {self.end}, {self.step}, {self.body})"
        )


class Break:
    def __repr__(self):
        return "Break()"


class Continue:
    def __repr__(self):
        return "Continue()"


# =========================================================
# FUNCTIONS
# =========================================================

class Function:
    def __init__(self, name, params, body, is_method=False):
        self.name = name
        self.params = params
        self.body = body
        self.is_method = is_method

    def __repr__(self):
        return (
            f"Function('{self.name}', "
            f"{self.params}, {self.body}, "
            f"is_method={self.is_method})"
        )


# =========================================================
# IMPORTS / EXPORTS
# =========================================================

class Import:
    def __init__(self, module, items=None, alias=None):
        self.module = module
        self.items = items or []
        self.alias = alias

    def __repr__(self):
        return f"Import('{self.module}', {self.items})"


class Export:
    def __init__(self, names):
        self.names = names

    def __repr__(self):
        return f"Export({self.names})"


class RawBlock:
    def __init__(self, body, exports=None):
        self.body = body
        self.exports = exports or []

    def __repr__(self):
        return f"RawBlock({self.body}, {self.exports})"


# =========================================================
# POINTERS / MEMORY
# =========================================================

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
    """
    ptr.value
    ptr.addr
    ptr.isValid
    ptr.isNull
    ptr.bytes
    """

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
        return (
            f"PointerAssign("
            f"{self.ptr}, "
            f"'{self.property}', "
            f"{self.value})"
        )


class PointerOffset:
    def __init__(self, ptr, offset):
        self.ptr = ptr
        self.offset = offset

    def __repr__(self):
        return f"PointerOffset({self.ptr}, {self.offset})"


# =========================================================
# ARRAYS
# =========================================================

class ArrayLiteral:
    def __init__(self, elements):
        self.elements = elements

    def __repr__(self):
        return f"ArrayLiteral({self.elements})"


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
        return (
            f"ArrayIndexAssign("
            f"{self.base}, "
            f"{self.index}, "
            f"{self.value})"
        )


class ArrayGet:
    def __init__(self, array, index):
        self.array = array
        self.index = index

    def __repr__(self):
        return f"ArrayGet({self.array}, {self.index})"


class ArraySet:
    def __init__(self, array, index, value):
        self.array = array
        self.index = index
        self.value = value

    def __repr__(self):
        return (
            f"ArraySet("
            f"{self.array}, "
            f"{self.index}, "
            f"{self.value})"
        )


class ArrayAppend:
    def __init__(self, array, value):
        self.array = array
        self.value = value

    def __repr__(self):
        return f"ArrayAppend({self.array}, {self.value})"


class ArrayLen:
    def __init__(self, array):
        self.array = array

    def __repr__(self):
        return f"ArrayLen({self.array})"


# =========================================================
# DATA STRUCTURES
# =========================================================

class Data:
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields

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
    """
    obj.field
    """

    def __init__(self, instance, field_name):
        self.instance = instance
        self.field_name = field_name

    def __repr__(self):
        return (
            f"DataFieldAccess("
            f"{self.instance}, "
            f"'{self.field_name}')"
        )


class DataFieldAssign:
    """
    obj.field = value
    """

    def __init__(self, instance, field_name, value):
        self.instance = instance
        self.field_name = field_name
        self.value = value

    def __repr__(self):
        return (
            f"DataFieldAssign("
            f"{self.instance}, "
            f"'{self.field_name}', "
            f"{self.value})"
        )


# =========================================================
# CLASSES
# =========================================================

class Class:
    def __init__(self, name, parent, fields, methods):
        self.fields = fields
        self.name = name
        self.parent = parent
        self.methods = methods

    def __repr__(self):
        return (
            f"Class('{self.name}', "
            f"'{self.parent}', "
            f"{self.methods})"
        )


class ClassInstance:
    def __init__(self, class_name):
        self.class_name = class_name

    def __repr__(self):
        return f"ClassInstance('{self.class_name}')"


class ClassMethodCall:
    def __init__(self, instance, method_name, args):
        self.instance = instance
        self.method_name = method_name
        self.args = args

    def __repr__(self):
        return (
            f"ClassMethodCall("
            f"{self.instance}, "
            f"'{self.method_name}', "
            f"{self.args})"
        )


class SelfFieldAccess:
    """
    self.field
    """

    def __init__(self, field_name):
        self.field_name = field_name

    def __repr__(self):
        return f"SelfFieldAccess('{self.field_name}')"


class SelfFieldAssign:
    """
    self.field = value
    """

    def __init__(self, field_name, value):
        self.field_name = field_name
        self.value = value

    def __repr__(self):
        return f"SelfFieldAssign('{self.field_name}', {self.value})"


# =========================================================
# RUNTIME ERRORS
# =========================================================

class NovaError(Exception):
    pass


def runtime_error(msg):
    raise NovaError(f"[Nova Runtime Error] {msg}")

class Export(Node):

    def __init__(self, names):
        self.names = names