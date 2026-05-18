from llvmlite import ir
from nova.ast.nodes import *
from nova.runtime.types import *
from nova.runtime.values import TypedValue
from nova.runtime.builtins import BUILTIN_TYPES

class CodeGen:
    def __init__(self, diagnostics):
        self.array_metadata = {}
        self.builder = None
        self.classes = {} 
        self.class_types = {}
        self.class_fields = {}
        self.current_class_name = None
        self.data_structures = {}
        self.diagnostics = diagnostics
        self.exports = {}
        self.free_fn = None
        self.functions = {}
        self.free_fn = None
        self.instances = {}
        self.loop_stack = []
        self.malloc_fn = None
        self.module = ir.Module(name="nova_module")
        self.malloc_fn = None
        self.printf = None
        self.pointer_metadata = {}
        self.symbols_stack = [{}]
        self.variable_types_stack = [{}]
        self.var_class_map = {}   # tracks variable name -> class name at compile time
        self.method_map = {}      # tracks "ClassName.method" -> "ClassName_method"

    def error_value(self):
        return TypedValue(
            ir.Constant(ir.IntType(32), 0),
            INT,
            is_lvalue=False
        )

    def push_scope(self):
        self.symbols_stack.append({})
        self.variable_types_stack.append({})

    def pop_scope(self):
        self.symbols_stack.pop()
        self.variable_types_stack.pop()

    def set_symbol(self, name, ptr):
        self.symbols_stack[-1][name] = ptr
    
    def resolve_type(self, type_name):
        """
        Resolve Nova type to semantic type.
        """

        if type_name in BUILTIN_TYPES:
            return BUILTIN_TYPES[type_name]

        if type_name in self.class_types:
            return ClassType(
                type_name,
                self.class_types[type_name]
            )

        if type_name in self.data_structures:
            return StructType(
                type_name,
                self.data_structures[type_name]["llvm_type"]
            )

        
        self.diagnostics.report(
            "Semantic",
            f"Unknown variable type '{type_name}'"
        )

        return INT

    def get_symbol(self, name):
        for scope in reversed(self.symbols_stack):
            if name in scope:
                return scope[name]
        if name in self.exports:
            return self.exports[name]
        
        self.diagnostics.report(
            "Semantic",
            f"Undefined variable: '{name}'"
        )

        return self.error_value()

    def set_variable_type(self, name, var_type):
        print(
            "REGISTER TYPE:",
            name,
            var_type
        )
        """
        Register variable semantic type.
        """

        self.variable_types_stack[-1][name] = var_type


    def get_variable_type(self, name):
        print(
            "LOOKUP TYPE:",
            name,
            self.variable_types_stack
        )
        """
        Resolve variable semantic type.
        """

        for scope in reversed(
            self.variable_types_stack
        ):

            if name in scope:
                return scope[name]

        
        self.diagnostics.report(
            "Semantic",
            f"Unknown variable type: '{name}'"
        )

        return INT

    def load_if_pointer(self, value):
        """
        Load only true scalar lvalues.

        Class/data instances remain pointers.
        """

        if not isinstance(value, TypedValue):
            return value

        # ==========================================
        # NOT AN LVALUE
        # ==========================================

        if not value.is_lvalue:
            return value

        # ==========================================
        # CLASS INSTANCES
        # DO NOT LOAD
        # ==========================================

        if isinstance(value.type, ClassType):
            return value

        # ==========================================
        # STRUCT INSTANCES
        # DO NOT LOAD
        # ==========================================

        if isinstance(value.type, StructType):
            return value

        if isinstance(value.type, PointerType):
            return value

        # ==========================================
        # LOAD NORMAL VALUES
        # ==========================================

        loaded = self.builder.load(
            value.ir_value
        )

        return TypedValue(
            loaded,
            value.type,
            is_lvalue=False
        )

    def declare_runtime_functions(self):
        """
        Declare external runtime functions.
        """

        # =====================================================
        # malloc
        # =====================================================

        malloc_type = ir.FunctionType(
            ir.IntType(8).as_pointer(),
            [ir.IntType(32)]
        )

        self.malloc_fn = ir.Function(
            self.module,
            malloc_type,
            name="malloc"
        )

        # =====================================================
        # free
        # =====================================================

        free_type = ir.FunctionType(
            ir.VoidType(),
            [ir.IntType(8).as_pointer()]
        )

        self.free_fn = ir.Function(
            self.module,
            free_type,
            name="free"
        )

    def generate(self, statements):
        func_type = ir.FunctionType(ir.IntType(32), [])
        main_func = ir.Function(self.module, func_type, name="main")
        block = main_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)

        self.declare_runtime_functions()

        for stmt in statements:
            self.gen_stmt(stmt)

        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(ir.IntType(32), 0))

        if self.diagnostics.has_errors():
            self.diagnostics.print_all()
            return None

        return str(self.module)

    def gen_expr(self, node):
        if isinstance(node, Number):
            return TypedValue(
                ir.Constant(ir.IntType(32), node.value),
                INT,
                is_lvalue=False
            )
        
        if isinstance(node, String):
            return self.create_string(node.value)
        
        if isinstance(node, Boolean):
            return TypedValue(
                ir.Constant(ir.IntType(1), int(node.value)),
                BOOL,
                is_lvalue=False
            )
        
        if isinstance(node, Variable):

            ptr = self.get_symbol(node.name)
            if isinstance(ptr, TypedValue):
                return ptr
            var_type = self.get_variable_type(
                node.name
            )

            # ==========================================
            # REFERENCE TYPES
            # AUTOLOAD POINTER VALUE
            # ==========================================

            if isinstance(var_type, ClassType):

                loaded = self.builder.load(ptr)

                return TypedValue(
                    loaded,
                    var_type,
                    is_lvalue=False
                )

            if isinstance(var_type, StructType):

                loaded = self.builder.load(ptr)

                return TypedValue(
                    loaded,
                    var_type,
                    is_lvalue=False
                )

            # ==========================================
            # NORMAL SCALAR VARIABLES
            # ==========================================

            return TypedValue(
                ptr,
                var_type,
                is_lvalue=True
            )


        if isinstance(node, UnaryOp):
            value = self.load_if_pointer(
                self.gen_expr(node.value)
            )

            if node.op == "-":
                return TypedValue(
                    self.builder.neg(
                        value.ir_value
                    ),
                    value.type.llvm_type,
                    is_lvalue=False
                )

        if isinstance(node, SelfFieldAccess):
            return self.gen_self_field_access(node)
        
        if isinstance(node, BinOp):
            left = self.load_if_pointer(self.gen_expr(node.left))
            right = self.load_if_pointer(self.gen_expr(node.right))
            
            if node.op == "+":
                return TypedValue(
                    self.builder.add(
                        left.ir_value,
                        right.ir_value
                    ),
                    INT,
                    is_lvalue=False
                )
            if node.op == "-":
                return TypedValue(
                    self.builder.sub(
                        left.ir_value,
                        right.ir_value
                    ),
                    INT,
                    is_lvalue=False
                )
            if node.op == "*":
                return TypedValue(
                    self.builder.mul(
                        left.ir_value,
                        right.ir_value
                    ),
                    INT,
                    is_lvalue=False
                )
            if node.op == "/":
                return TypedValue(
                    self.builder.sdiv(
                        left.ir_value,
                        right.ir_value
                    ),
                    INT,
                    is_lvalue=False
                )
            if node.op == "%":
                return TypedValue(
                    self.builder.srem(
                        left.ir_value,
                        right.ir_value
                    ),
                    INT,
                    is_lvalue=False
                )
        
        if isinstance(node, Compare):
            left = self.load_if_pointer(
                self.gen_expr(node.left)
            )

            right = self.load_if_pointer(
                self.gen_expr(node.right)
            )

            pred_map = {
                "<": "<",
                ">": ">",
                "==": "==",
                "!=": "!=",
                "<=": "<=",
                ">=": ">="
            }

            pred = pred_map.get(node.op)

            if pred:
                return TypedValue(
                    self.builder.icmp_signed(
                        pred,
                        left.ir_value,
                        right.ir_value
                    ),
                    BOOL,
                    is_lvalue=False
                )
        
        if isinstance(node, Call):
            return self.gen_call(node)
        
        if isinstance(node, Alloc):
            return self.gen_alloc(node)
        
        if isinstance(node, PointerProperty):
            return self.gen_pointer_property(node)
        
        if isinstance(node, ArrayIndex):
            return self.gen_array_index(node)
        
        if isinstance(node, DataInstance):
            return self.gen_data_instance(node)

        if isinstance(node, DataFieldAccess):
            return self.gen_data_field_access(node)
        
        if isinstance(node, ArrayLiteral):
            return self.gen_array_literal(node)

        if isinstance(node, ArrayGet):
            return self.gen_array_get(node)

        if isinstance(node, ArrayLen):
            return self.gen_array_len(node)

        if isinstance(node, ClassInstance):
            return self.gen_class_instance(node)

        if isinstance(node, ClassMethodCall):
            return self.gen_class_method_call(node)
        
        
        self.diagnostics.report(
            "Semantic",
            f"Unknown expression: '{type(node)}'"
        )

        return self.error_value()


    def gen_stmt(self, node):
        if isinstance(node, Assignment):
            value = self.load_if_pointer(
                self.gen_expr(node.value)
            )

            # Track which variable holds which class instance (compile-time)
            if isinstance(node.value, ClassInstance):
                self.var_class_map[node.name] = node.value.class_name

            existing = None
            for scope in reversed(self.symbols_stack):
                if node.name in scope:
                    existing = scope[node.name]
                    break
            
            if existing:
                self.builder.store(value.ir_value, existing)
            else:
                ptr = self.builder.alloca(value.type.llvm_type, name=node.name)
                self.set_symbol(node.name, ptr)
                self.set_variable_type(
                    node.name,
                    value.type
                )
                self.builder.store(
                    value.ir_value,
                    ptr
                )
        
        elif isinstance(node, PointerAssign):
            self.gen_pointer_assign(node)

        elif isinstance(node, SelfFieldAssign):
            self.gen_self_field_assign(node)        
        
        elif isinstance(node, ArrayIndexAssign):
            self.gen_array_index_assign(node)

        elif isinstance(node, Class):
            self.gen_class(node)

        elif isinstance(node, ClassInstance):
            self.gen_class_instance(node)

        elif isinstance(node, ClassMethodCall):
            self.gen_class_method_call(node)
        
        elif isinstance(node, Data):
            self.gen_data(node)

        elif isinstance(node, DataFieldAssign):
            self.gen_data_field_assign(node)
        
        elif isinstance(node, Print):
            self.gen_print(node)
        
        elif isinstance(node, RawBlock):
            self.gen_raw(node)
        
        elif isinstance(node, Function):
            self.gen_function(node)
        
        elif isinstance(node, Return):
            val = self.load_if_pointer(
                self.gen_expr(node.value)
            )
            if val.type.llvm_type == ir.IntType(1):
                val = self.builder.zext(val, ir.IntType(32))
            self.builder.ret(val.ir_value)
        
        elif isinstance(node, IfElse):
            self.gen_ifelse(node)
        
        elif isinstance(node, While):
            self.gen_while(node)
        
        elif isinstance(node, Break):
            if self.loop_stack:
                self.builder.branch(self.loop_stack[-1][1])
        
        elif isinstance(node, Continue):
            if self.loop_stack:
                self.builder.branch(self.loop_stack[-1][0])
        
        elif isinstance(node, Free):
            self.gen_free(node)
        
        elif isinstance(node, ForLoop):
            self.gen_for(node)
        
        elif isinstance(node, ArraySet):
            self.gen_array_set(node)

        elif isinstance(node, ArrayAppend):
            self.gen_array_append(node)

    # ========== MEMORY MANAGEMENT ==========

    def gen_alloc(self, node):
        """
        alloc(size)
        """

        size = self.load_if_pointer(
            self.gen_expr(node.size)
        )

        ptr_void = self.builder.call(
            self.malloc_fn,
            [size.ir_value]
        )

        ptr = self.builder.bitcast(
            ptr_void,
            ir.IntType(32).as_pointer()
        )

        # ==========================================
        # STORE POINTER METADATA
        # ==========================================

        self.pointer_metadata[ptr] = (
            size.ir_value
        )

        return TypedValue(
            ptr,
            PointerType(INT),
            is_lvalue=False
        )

    def gen_free(self, node):
        ptr_var = self.gen_expr(node.ptr)
        ptr = self.builder.load(ptr_var)
        ptr_void = self.builder.bitcast(ptr, ir.IntType(8).as_pointer())
        
        if not self.free_fn:
            free_type = ir.FunctionType(ir.VoidType(), [ir.IntType(8).as_pointer()])
            self.free_fn = ir.Function(self.module, free_type, name="free")
        
        self.builder.call(self.free_fn, [ptr_void])
        
        if ptr_var in self.pointer_metadata:
            del self.pointer_metadata[ptr_var]

    def get_self_pointer(self):
        return self.get_symbol("self")


    def get_self_field_ptr(self, field_name):
        """
        Returns pointer to self.field
        """

        # self symbol is stored as %Player**
        self_ptr_ptr = self.get_symbol("self")

        # load actual %Player*
        self_ptr = self.builder.load(self_ptr_ptr)

        class_name = self.current_class_name

        if class_name not in self.class_fields:
            
            self.diagnostics.report(
                "Semantic",
                f"Unknown class: '{class_name}'"
            )

            return INT

        field_map = self.class_fields[class_name]

        if field_name not in field_map:
            self.diagnostics.report(
                "Semantic",
                f"Unknown field: '{field_name}' in class: '{class_name}'"
            )

            return INT

        field_index = field_map[field_name]

        field_ptr = self.builder.gep(
            self_ptr,
            [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), field_index)
            ]
        )

        return field_ptr


    def gen_self_field_access(self, node):
        field_ptr = self.get_self_field_ptr(
            node.field_name
        )

        return TypedValue(
            field_ptr,
            INT,
            is_lvalue=True
        )

    def gen_self_field_assign(self, node):
        """
        self.field = value
        """

        field_ptr = self.get_self_field_ptr(
            node.field_name
        )

        value = self.load_if_pointer(
            self.gen_expr(node.value)
        )

        self.builder.store(
            value.ir_value,
            field_ptr
        )

        return value

    # ========== POINTER OPERATIONS ==========

    def gen_pointer_property(self, node):
        """
        Handle pointer properties:

        ptr.value
        ptr.addr
        ptr.isValid
        ptr.isNull
        ptr.bytes
        """

        ptr_value = self.load_if_pointer(
            self.gen_expr(node.ptr)
        )

        ptr = ptr_value.ir_value

        # =====================================================
        # ptr.value
        # =====================================================

        if node.property == "value":

            loaded = self.builder.load(ptr)

            return TypedValue(
                loaded,
                INT,
                is_lvalue=False
            )

        # =====================================================
        # ptr.addr
        # =====================================================

        elif node.property == "addr":

            addr = self.builder.ptrtoint(
                ptr,
                ir.IntType(64)
            )

            return TypedValue(
                addr,
                INT,
                is_lvalue=False
            )

        # =====================================================
        # ptr.isValid
        # =====================================================

        elif node.property == "isValid":

            null_ptr = ir.Constant(
                ptr.type.llvm_type,
                None
            )

            result = self.builder.icmp_signed(
                "!=",
                ptr,
                null_ptr
            )

            return TypedValue(
                result,
                BOOL,
                is_lvalue=False
            )

        # =====================================================
        # ptr.isNull
        # =====================================================

        elif node.property == "isNull":

            null_ptr = ir.Constant(
                ptr.type.llvm_type,
                None
            )

            result = self.builder.icmp_signed(
                "==",
                ptr,
                null_ptr
            )

            return TypedValue(
                result,
                BOOL,
                is_lvalue=False
            )

        # =====================================================
        # ptr.bytes
        # =====================================================

        elif node.property == "bytes":

            if ptr in self.pointer_metadata:

                return TypedValue(
                    self.pointer_metadata[ptr],
                    INT,
                    is_lvalue=False
                )

            return TypedValue(
                ir.Constant(ir.IntType(32), 0),
                INT,
                is_lvalue=False
            )

        
        self.diagnostics.report(
            "Semantic",
            f"Unknown pointer property: '{node.property}'"
        )

        return INT

    def gen_pointer_assign(self, node):
        ptr_var = self.gen_expr(node.ptr)
        ptr = self.builder.load(ptr_var)
        value = self.load_if_pointer(
            self.gen_expr(node.value)
        )
        
        if node.property == "value":
            self.builder.store(
                value.ir_value,
                ptr
            )
        else:
            self.diagnostics.report(
                "Semantic",
                f"Can't assign to property: '{node.property}'"
            )

            return INT

    def gen_array_index(self, node):
        ptr_var = self.gen_expr(node.base)
        ptr = self.builder.load(ptr_var)
        index = self.gen_expr(node.index)
        
        element_ptr = self.builder.gep(ptr, [index.ir_value])
        
        return TypedValue(
            element_ptr,
            INT,
            is_lvalue=True
        )

    def gen_array_index_assign(self, node):
        ptr_var = self.gen_expr(node.base)
        ptr = self.builder.load(ptr_var)
        index = self.gen_expr(node.index)
        value = self.load_if_pointer(
            self.gen_expr(node.value)
        )
        
        element_ptr = self.builder.gep(ptr, [index.ir_value])
        
        self.builder.store(value.ir_value, element_ptr)
        return value

    # ========== CLASSES ==========

    def gen_class(self, node):
        self.classes[node.name] = node

        llvm_fields = []
        field_map = {}

        for index, (field_name, field_type) in enumerate(node.fields):
            field_map[field_name] = index

            if field_type == "int":
                llvm_fields.append(ir.IntType(32))

            elif field_type == "bool":
                llvm_fields.append(ir.IntType(1))

            else:
                llvm_fields.append(ir.IntType(32))

        struct_type = ir.LiteralStructType(llvm_fields)

        self.class_types[node.name] = struct_type
        self.class_fields[node.name] = field_map

        # generate methods
        for method in node.methods:
            func_name = f"{node.name}_{method.name}"

            params = method.params

            func_node = Function(
                func_name,
                params,
                method.body,
                is_method=True
            )

            self.gen_function(func_node)

            self.method_map[
                f"{node.name}.{method.name}"
            ] = func_name

    def gen_class_instance(self, node):
        if node.class_name not in self.class_types:
            self.diagnostics.report(
            "Semantic",
            f"Unknown Class: '{node.class_name}'"
        )

        return INT

        struct_ty = self.class_types[node.class_name]

        ptr = self.builder.alloca(
            struct_ty,
            name=f"{node.class_name.lower()}_obj"
        )

        init_name = f"{node.class_name}_init"

        if init_name in self.functions:
            init_func = self.functions[init_name]

            self.builder.call(
                init_func,
                [ptr]
            )

        return TypedValue(
            ptr,
            ClassType(
                node.class_name,
                self.class_types[node.class_name]
            ),
            is_lvalue=False
        )

    def gen_class_method_call(self, node):
        """
        Generate class method call.
        """

        # =====================================================
        # INSTANCE
        # =====================================================

        instance = self.load_if_pointer(
            self.gen_expr(node.instance)
        )

        class_name = instance.type.name

        method_name = f"{class_name}_{node.method_name}"

        if method_name not in self.module.globals:
            self.diagnostics.report(
                "Semantic",
                f"Unkown method: '{method_name}'"
            )

            return INT

        func = self.module.globals[method_name]

        # =====================================================
        # BUILD LLVM ARG LIST
        # =====================================================

        llvm_args = []

        # self pointer
        llvm_args.append(instance.ir_value)

        # normal args
        for arg in node.args:

            value = self.load_if_pointer(
                self.gen_expr(arg)
            )

            llvm_args.append(
                value.ir_value
            )

        # =====================================================
        # CALL
        # =====================================================

        result = self.builder.call(
            func,
            llvm_args
        )

        return TypedValue(
            result,
            INT,
            is_lvalue=False
        )


    # ========== DATA STRUCTURES ==========

    def gen_data(self, node):
        total_size = 0
        field_offsets = {}
        
        for field_name, field_type in node.fields:
            field_offsets[field_name] = total_size
            total_size += 4
        
        self.data_structures[node.name] = {
            "size": total_size,
            "offsets": field_offsets,
            "fields": node.fields
        }
        
        return None

    def gen_data_instance(self, node):
        if node.data_name not in self.data_structures:
            self.diagnostics.report(
                "Semantic",
                f"Unknown data structure: '{node.data_name}'"
            )

            return INT
        
        data_info = self.data_structures[node.data_name]
        size = data_info["size"]
        
        if not self.malloc_fn:
            malloc_type = ir.FunctionType(ir.IntType(8).as_pointer(), [ir.IntType(32)])
            self.malloc_fn = ir.Function(self.module, malloc_type, name="malloc")
        
        ptr_void = self.builder.call(self.malloc_fn, [ir.Constant(ir.IntType(32), size)])
        ptr = self.builder.bitcast(ptr_void, ir.IntType(8).as_pointer())
        
        ptr_var = self.builder.alloca(ptr.type.llvm_type, name=node.data_name.lower())
        self.builder.store(ptr, ptr_var)
        
        return ptr_var

    def get_data_field_ptr(self, node):

        instance = self.load_if_pointer(
            self.gen_expr(node.instance)
        )

        instance_ptr = instance.ir_value

        # -------------------------------------------------
        # LOAD POINTER IF NEEDED
        # -------------------------------------------------

        if (
            isinstance(instance_ptr.type, ir.PointerType)
            and isinstance(
                instance_ptr.type.pointee,
                ir.PointerType
            )
        ):
            instance_ptr = self.builder.load(
                instance_ptr
            )
        else:
            instance_ptr = instance_ptr

        field_name = node.field_name

        # =================================================
        # CLASS FIELD LOOKUP
        # =================================================

        for class_name, field_map in self.class_fields.items():

            if field_name in field_map:

                field_index = field_map[field_name]

                field_ptr = self.builder.gep(
                    instance_ptr,
                    [
                        ir.Constant(ir.IntType(32), 0),
                        ir.Constant(ir.IntType(32), field_index)
                    ]
                )

                return field_ptr

        # =================================================
        # DATA STRUCT LOOKUP
        # =================================================

        for struct_name, info in self.data_structures.items():

            if field_name in info["offsets"]:

                offset = info["offsets"][field_name]

                byte_ptr = self.builder.gep(
                    instance_ptr,
                    [ir.Constant(ir.IntType(32), offset)]
                )

                field_ptr = self.builder.bitcast(
                    byte_ptr,
                    ir.IntType(32).as_pointer()
                )

                return field_ptr

        # =================================================
        # FAILURE
        # =================================================

        self.diagnostics.report(
            "Semantic",
            f"Unkown field: '{field_name}'"
        )

        return self.error_value()

    def gen_data_field_access(self, node):
        field_ptr = self.get_data_field_ptr(node)

        return TypedValue(
                    field_ptr,
                    INT,
                    is_lvalue=True
                )

    def gen_data_field_assign(self, node):
        field_ptr = self.get_data_field_ptr(node)

        value = self.load_if_pointer(
            self.gen_expr(node.value)
        )

        self.builder.store(value.ir_value, field_ptr)

        return value

    # ========== PRINT ==========

    def gen_print(self, node):

        value = self.load_if_pointer(
            self.gen_expr(node.value)
        )

        printf = self.get_printf()

        llvm_value = value.ir_value

        # ==========================================
        # BOOL
        # ==========================================

        if llvm_value.type == ir.IntType(1):

            llvm_value = self.builder.zext(
                llvm_value,
                ir.IntType(32)
            )

            fmt = self.create_string("%d\n")

        # ==========================================
        # 64 BIT
        # ==========================================

        elif llvm_value.type == ir.IntType(64):

            fmt = self.create_string("%lld\n")

        # ==========================================
        # POINTER
        # ==========================================

        elif isinstance(
            llvm_value.type,
            ir.PointerType
        ):

            fmt = self.create_string("%p\n")

            llvm_value = self.builder.ptrtoint(
                llvm_value,
                ir.IntType(64)
            )

        # ==========================================
        # NORMAL INT
        # ==========================================

        else:

            fmt = self.create_string("%d\n")

        fmt_ptr = self.builder.bitcast(
            fmt.ir_value,
            ir.IntType(8).as_pointer()
        )

        self.builder.call(
            printf,
            [
                fmt_ptr,
                llvm_value
            ]
        )


    # ========== CONTROL FLOW ==========

    def gen_ifelse(self, node):
        cond = self.load_if_pointer(
            self.gen_expr(node.condition)
        )
        if cond.type.llvm_type != ir.IntType(1):
            zero = ir.Constant(cond.type.llvm_type, 0)
            cond = self.builder.icmp_signed("!=", cond, zero)
        
        func = self.builder.function
        then_bb = func.append_basic_block("if.then")
        else_bb = func.append_basic_block("if.else")
        end_bb = func.append_basic_block("if.end")
        
        self.builder.cbranch(cond, then_bb, else_bb)
        
        self.builder.position_at_start(then_bb)
        for stmt in node.if_body:
            self.gen_stmt(stmt)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)
        
        self.builder.position_at_start(else_bb)
        for stmt in node.else_body:
            self.gen_stmt(stmt)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)
        
        self.builder.position_at_start(end_bb)

    def gen_while(self, node):
        func = self.builder.function
        cond_bb = func.append_basic_block("while.cond")
        body_bb = func.append_basic_block("while.body")
        end_bb = func.append_basic_block("while.end")
        
        self.loop_stack.append((cond_bb, end_bb))
        self.builder.branch(cond_bb)
        
        self.builder.position_at_start(cond_bb)
        cond = self.load_if_pointer(
            self.gen_expr(node.condition)
        )
        if cond.type.llvm_type != ir.IntType(1):
            zero = ir.Constant(cond.type.llvm_type, 0)
            cond = self.builder.icmp_signed("!=", cond, zero)
        self.builder.cbranch(cond, body_bb, end_bb)
        
        self.builder.position_at_start(body_bb)
        for stmt in node.body:
            self.gen_stmt(stmt)
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_bb)
        
        self.loop_stack.pop()
        self.builder.position_at_start(end_bb)

    # ========== FUNCTIONS ==========

    def gen_function(self, node):
        """
        Generate LLVM function.

        Supports:
        - normal functions
        - class methods
        - real self pointers
        """

        # =====================================================
        # SAVE OLD STATE
        # =====================================================

        old_builder = self.builder
        old_symbols = self.symbols_stack
        old_class_name = self.current_class_name

        # =====================================================
        # PARAM TYPES
        # =====================================================

        param_types = []

        # -----------------------------------------------------
        # METHODS
        # -----------------------------------------------------

        if node.is_method:
            class_name = node.name.split("_")[0]

            self.current_class_name = class_name

            if class_name not in self.class_types:
                self.diagnostics.report(
                    "Semantic",
                    f"Unknown Class type: '{class_name}'"
                )

                return INT

            class_ptr_type = self.class_types[
                class_name
            ].as_pointer()

            # self parameter
            param_types.append(class_ptr_type)

            # remaining params
            for _ in node.params[1:]:
                param_types.append(ir.IntType(32))

        # -----------------------------------------------------
        # NORMAL FUNCTIONS
        # -----------------------------------------------------

        else:
            param_types = [
                ir.IntType(32)
                for _ in node.params
            ]

        # =====================================================
        # CREATE FUNCTION
        # =====================================================

        func_type = ir.FunctionType(
            ir.IntType(32),
            param_types
        )

        func = ir.Function(
            self.module,
            func_type,
            name=node.name
        )

        # =====================================================
        # FUNCTION BODY
        # =====================================================

        self.symbols_stack.append({})
        self.variable_types_stack.append({})

        entry_block = func.append_basic_block(
            name="entry"
        )

        self.builder = ir.IRBuilder(entry_block)

        # =====================================================
        # STORE PARAMETERS
        # =====================================================

        for i, arg in enumerate(func.args):

            param_name = node.params[i]

            arg.name = param_name

            # =================================================
            # DETERMINE PARAM TYPE
            # =================================================

            if node.is_method and i == 0:

                semantic_type = ClassType(
                    self.current_class_name,
                    self.class_types[
                        self.current_class_name
                    ]
                )

            else:

                semantic_type = INT

            # =================================================
            # ALLOCATE PARAM STORAGE
            # =================================================

            ptr = self.builder.alloca(
                arg.type,
                name=param_name
            )

            self.builder.store(arg, ptr)

            # =================================================
            # REGISTER SYMBOL
            # =================================================

            self.set_symbol(param_name, ptr)

            # =================================================
            # REGISTER SEMANTIC TYPE
            # =================================================

            self.set_variable_type(
                param_name,
                semantic_type
            )

        # ==========================================
        # REGISTER PARAM TYPE
        # ==========================================

        self.set_variable_type(
            param_name,
            INT
        )
        

        # =====================================================
        # GENERATE BODY
        # =====================================================

        for stmt in node.body:
            self.gen_stmt(stmt)

        # =====================================================
        # DEFAULT RETURN
        # =====================================================

        if not self.builder.block.is_terminated:
            self.builder.ret(
                ir.Constant(ir.IntType(32), 0)
            )

        # =====================================================
        # RESTORE OLD STATE
        # =====================================================
        self.symbols_stack.pop()
        self.variable_types_stack.pop()
        self.builder = old_builder
        self.symbols_stack = old_symbols
        self.current_class_name = old_class_name

        # =====================================================
        # REGISTER FUNCTION
        # =====================================================

        self.functions[node.name] = func

        return func


    # gen_call is a top-level method (was accidentally indented inside gen_function before)
    def gen_call(self, node):
        if node.name in self.functions:
            func = self.functions[node.name]
        elif node.name in self.module.globals:
            func = self.module.globals[node.name]
        else:
            self.diagnostics.report(
                "Semantic",
                f"Undefined function: '{node.name}'"
            )

            return self.error_value()
        
        args = [
            self.load_if_pointer(
                self.gen_expr(arg)
            )
            for arg in node.args
        ]
        llvm_args = [
            arg.ir_value
            for arg in args
        ]
        return TypedValue(
            self.builder.call(func, llvm_args),
            INT,
            is_lvalue=False
        )

    # ========== RAW BLOCKS ==========

    def gen_raw(self, node):

        self.push_scope()

        try:

            for stmt in node.body:
                print(type(stmt))
                # ==================================
                # EXPORT HANDLING
                # ==================================

                if isinstance(stmt, Export):

                    for name in stmt.names:

                        symbol = self.get_symbol(name)

                        var_type = self.get_variable_type(name)

                        # parent scopes
                        outer_symbols = (
                            self.symbols_stack[-2]
                        )

                        outer_types = (
                            self.variable_types_stack[-2]
                        )

                        # export symbol
                        outer_symbols[name] = symbol

                        # export type
                        outer_types[name] = var_type

                else:

                    self.gen_stmt(stmt)

        finally:

            self.pop_scope()

    # ========== UTILITIES ==========

    def create_string(self, text):
        text_bytes = bytearray(text.encode("utf8")) + b"\0"
        string_type = ir.ArrayType(ir.IntType(8), len(text_bytes))
        global_str = ir.GlobalVariable(
            self.module, string_type, 
            name=f".str{len(list(self.module.global_values))}"
        )
        global_str.global_constant = True
        global_str.initializer = ir.Constant(string_type, text_bytes)
        return TypedValue(
                    global_str,
                    STRING,
                    is_lvalue=False
                )

    def get_printf(self):
        if self.printf:
            return self.printf
        func_type = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer()], var_arg=True)
        self.printf = ir.Function(self.module, func_type, name="printf")
        return self.printf
    
    def gen_for(self, node):
        start_val = self.gen_expr(node.start)
        end_val = self.gen_expr(node.end)
        step_val = self.gen_expr(node.step)
        
        var_ptr = self.builder.alloca(ir.IntType(32), name=node.var_name)
        self.set_symbol(node.var_name, var_ptr)
        self.builder.store(start_val, var_ptr)
        
        func = self.builder.function
        
        cond_bb = func.append_basic_block("for.cond")
        body_bb = func.append_basic_block("for.body")
        step_bb = func.append_basic_block("for.step")
        end_bb = func.append_basic_block("for.end")
        
        self.loop_stack.append((step_bb, end_bb))
        self.builder.branch(cond_bb)
        
        self.builder.position_at_start(cond_bb)
        current_var = self.builder.load(var_ptr)
        
        if node.is_downto:
            cond = self.builder.icmp_signed(">=", current_var, end_val)
        else:
            cond = self.builder.icmp_signed("<=", current_var, end_val)
        
        self.builder.cbranch(cond, body_bb, end_bb)
        
        self.builder.position_at_start(body_bb)
        for stmt in node.body:
            self.gen_stmt(stmt)
        
        if not self.builder.block.is_terminated:
            self.builder.branch(step_bb)
        
        self.builder.position_at_start(step_bb)
        current = self.builder.load(var_ptr)
        
        if node.is_downto:
            new_val = self.builder.sub(current, step_val)
        else:
            new_val = self.builder.add(current, step_val)
        
        self.builder.store(new_val, var_ptr)
        self.builder.branch(cond_bb)
        
        self.loop_stack.pop()
        self.builder.position_at_start(end_bb)

    def gen_array_literal(self, node):
        count = len(node.elements)
        array_size = count * 4

        if not self.malloc_fn:
            malloc_type = ir.FunctionType(ir.IntType(8).as_pointer(), [ir.IntType(32)])
            self.malloc_fn = ir.Function(self.module, malloc_type, name="malloc")
        
        array_ptr = self.builder.call(self.malloc_fn, [ir.Constant(ir.IntType(32), array_size)])
        array_ptr_int = self.builder.bitcast(array_ptr.ir_value, ir.IntType(32).as_pointer())
        
        for i, elem in enumerate(node.elements):
            val = self.gen_expr(elem)
            offset = ir.Constant(ir.IntType(32), i * 4)
            elem_ptr = self.builder.gep(array_ptr_int, [offset])
            self.builder.store(val, elem_ptr)
        
        ptr_var = self.builder.alloca(array_ptr_int.type, name="array")
        self.builder.store(array_ptr_int, ptr_var)
        
        self.array_metadata[ptr_var] = {"size": count, "ptr": array_ptr_int}
        
        return ptr_var


    def gen_array_get(self, node):

        array_var = self.gen_expr(node.array)

        # load actual pointer if variable storage
        if array_var.is_lvalue:
            array_ptr = self.builder.load(
                array_var.ir_value
            )
        else:
            array_ptr = array_var.ir_value

        index = self.load_if_pointer(
            self.gen_expr(node.index)
        )

        element_ptr = self.builder.gep(
            array_ptr,
            [index.ir_value]
        )

        loaded = self.builder.load(
            element_ptr
        )

        return TypedValue(
            loaded,
            INT,
            is_lvalue=False
        )


    def gen_array_set(self, node):

        array_var = self.gen_expr(node.array)

        # load actual pointer if needed
        if array_var.is_lvalue:
            array_ptr = self.builder.load(
                array_var.ir_value
            )
        else:
            array_ptr = array_var.ir_value

        index = self.load_if_pointer(
            self.gen_expr(node.index)
        )

        value = self.load_if_pointer(
            self.gen_expr(node.value)
        )

        element_ptr = self.builder.gep(
            array_ptr,
            [index.ir_value]
        )

        self.builder.store(
            value.ir_value,
            element_ptr
        )

        return value


    def gen_array_len(self, node):
        return ir.Constant(ir.IntType(32), 0)

    def gen_array_append(self, node):
        return self.gen_expr(node.value)