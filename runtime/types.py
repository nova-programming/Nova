from llvmlite import ir


class NovaType:
    """
    Semantic type representation.
    """

    def __init__(
        self,
        name,
        llvm_type,
        is_pointer=False,
        element_type=None
    ):
        self.name = name
        self.llvm_type = llvm_type
        self.is_pointer = is_pointer
        self.element_type = element_type

    def __repr__(self):
        return f"NovaType({self.name})"


# =====================================================
# BUILTIN TYPES
# =====================================================

INT = NovaType(
    "int",
    ir.IntType(32)
)

BOOL = NovaType(
    "bool",
    ir.IntType(1)
)

VOID = NovaType(
    "void",
    ir.VoidType()
)

STRING = NovaType(
    "string",
    ir.IntType(8).as_pointer(),
    is_pointer=True
)


# =====================================================
# POINTER TYPES
# =====================================================

class PointerType(NovaType):
    def __init__(self, base_type):
        super().__init__(
            f"{base_type.name}*",
            base_type.llvm_type.as_pointer(),
            is_pointer=True,
            element_type=base_type
        )


# =====================================================
# ARRAY TYPES
# =====================================================

class ArrayType(NovaType):
    def __init__(self, element_type):
        super().__init__(
            f"{element_type.name}[]",
            ir.IntType(8).as_pointer(),
            is_pointer=True,
            element_type=element_type
        )


# =====================================================
# CLASS TYPES
# =====================================================

class ClassType(NovaType):
    def __init__(self, name, llvm_type):
        super().__init__(
            name,
            llvm_type.as_pointer(),
            is_pointer=True
        )


# =====================================================
# STRUCT TYPES
# =====================================================

class StructType(NovaType):
    def __init__(self, name, llvm_type):
        super().__init__(
            name,
            llvm_type.as_pointer(),
            is_pointer=True
        )