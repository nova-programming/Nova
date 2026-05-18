class TypedValue:
    """
    Semantic wrapper around LLVM values.

    This is one of the most important
    compiler structures in Nova.
    """

    def __init__(
        self,
        ir_value,
        nova_type,
        is_lvalue=False
    ):
        self.ir_value = ir_value
        self.type = nova_type
        self.is_lvalue = is_lvalue

    def __repr__(self):
        return (
            f"TypedValue("
            f"type={self.type}, "
            f"lvalue={self.is_lvalue})"
        )