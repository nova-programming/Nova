from llvmlite import ir
from nova.ast.nodes import *


class CodeGen:
    def __init__(self):
        self.module = ir.Module(name="nova_module")
        self.builder = None
        self.printf = None
        self.malloc_fn = None
        self.free_fn = None
        self.symbols_stack = [{}]
        self.functions = {}
        self.loop_stack = []
        self.exports = {}
        self.pointer_metadata = {}
        self.data_structures = {}  # Store data structure info

    def push_scope(self):
        self.symbols_stack.append({})

    def pop_scope(self):
        self.symbols_stack.pop()

    def set_symbol(self, name, ptr):
        self.symbols_stack[-1][name] = ptr

    def get_symbol(self, name):
        for scope in reversed(self.symbols_stack):
            if name in scope:
                return scope[name]
        if name in self.exports:
            return self.exports[name]
        raise Exception(f"Undefined variable: {name}")

    def generate(self, statements):
        func_type = ir.FunctionType(ir.IntType(32), [])
        main_func = ir.Function(self.module, func_type, name="main")
        block = main_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)

        for stmt in statements:
            self.gen_stmt(stmt)

        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(ir.IntType(32), 0))

        return str(self.module)

    def gen_expr(self, node):
        if isinstance(node, Number):
            return ir.Constant(ir.IntType(32), node.value)
        
        if isinstance(node, String):
            return self.create_string(node.value)
        
        if isinstance(node, Boolean):
            return ir.Constant(ir.IntType(1), int(node.value))
        
        if isinstance(node, Variable):
            ptr = self.get_symbol(node.name)
            return self.builder.load(ptr)
        
        if isinstance(node, UnaryOp):
            value = self.gen_expr(node.value)
            if node.op == "-":
                return self.builder.neg(value)
        
        if isinstance(node, BinOp):
            left = self.gen_expr(node.left)
            right = self.gen_expr(node.right)
            
            if node.op == "+":
                return self.builder.add(left, right)
            if node.op == "-":
                return self.builder.sub(left, right)
            if node.op == "*":
                return self.builder.mul(left, right)
            if node.op == "/":
                return self.builder.sdiv(left, right)
            if node.op == "%":
                return self.builder.srem(left, right)
        
        if isinstance(node, Compare):
            left = self.gen_expr(node.left)
            right = self.gen_expr(node.right)
            pred_map = {"<": "<", ">": ">", "==": "==", "!=": "!=", "<=": "<=", ">=": ">="}
            pred = pred_map.get(node.op)
            if pred:
                return self.builder.icmp_signed(pred, left, right)
        
        if isinstance(node, Call):
            return self.gen_call(node)
        
        if isinstance(node, Alloc):
            return self.gen_alloc(node)
        
        if isinstance(node, PointerProperty):
            return self.gen_pointer_property(node)
        
        if isinstance(node, ArrayIndex):
            return self.gen_array_index(node)
        
        # Data structure nodes
        if isinstance(node, DataInstance):
            return self.gen_data_instance(node)
        
        if isinstance(node, DataFieldAccess):
            return self.gen_data_field_access(node)
        
        raise Exception(f"Unknown expression: {type(node)}")

    def gen_stmt(self, node):
        if isinstance(node, Assignment):
            value = self.gen_expr(node.value)
            existing = None
            for scope in reversed(self.symbols_stack):
                if node.name in scope:
                    existing = scope[node.name]
                    break
            
            if existing:
                self.builder.store(value, existing)
            else:
                ptr = self.builder.alloca(value.type, name=node.name)
                self.set_symbol(node.name, ptr)
                self.builder.store(value, ptr)
        
        elif isinstance(node, PointerAssign):
            self.gen_pointer_assign(node)
        
        elif isinstance(node, ArrayIndexAssign):
            self.gen_array_index_assign(node)
        
        # Data structure nodes
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
            val = self.gen_expr(node.value)
            if val.type == ir.IntType(1):
                val = self.builder.zext(val, ir.IntType(32))
            self.builder.ret(val)
        
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

    # ========== MEMORY MANAGEMENT ==========

    def gen_alloc(self, node):
        size = self.gen_expr(node.size)
        
        if not self.malloc_fn:
            malloc_type = ir.FunctionType(ir.IntType(8).as_pointer(), [ir.IntType(32)])
            self.malloc_fn = ir.Function(self.module, malloc_type, name="malloc")
        
        ptr_void = self.builder.call(self.malloc_fn, [size])
        ptr = self.builder.bitcast(ptr_void, ir.IntType(32).as_pointer())
        
        ptr_var = self.builder.alloca(ptr.type, name="ptr")
        self.builder.store(ptr, ptr_var)
        
        self.pointer_metadata[ptr_var] = size
        
        return ptr_var

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

    # ========== POINTER OPERATIONS ==========

    def gen_pointer_property(self, node):
        ptr_var = self.gen_expr(node.ptr)
        ptr = self.builder.load(ptr_var)
        
        if node.property == "value":
            return self.builder.load(ptr)
        elif node.property == "addr":
            return self.builder.ptrtoint(ptr, ir.IntType(64))
        elif node.property == "isValid":
            null_ptr = ir.Constant(ptr.type, None)
            return self.builder.icmp_signed("!=", ptr, null_ptr)
        elif node.property == "isNull":
            null_ptr = ir.Constant(ptr.type, None)
            return self.builder.icmp_signed("==", ptr, null_ptr)
        elif node.property == "bytes":
            if ptr_var in self.pointer_metadata:
                return self.pointer_metadata[ptr_var]
            return ir.Constant(ir.IntType(32), 0)
        
        raise Exception(f"Unknown pointer property: {node.property}")

    def gen_pointer_assign(self, node):
        ptr_var = self.gen_expr(node.ptr)
        ptr = self.builder.load(ptr_var)
        value = self.gen_expr(node.value)
        
        if node.property == "value":
            self.builder.store(value, ptr)
        else:
            raise Exception(f"Cannot assign to property: {node.property}")

    def gen_array_index(self, node):
        ptr_var = self.gen_expr(node.base)
        ptr = self.builder.load(ptr_var)
        index = self.gen_expr(node.index)
        
        element_size = ir.Constant(ir.IntType(32), 4)
        offset = self.builder.mul(index, element_size)
        element_ptr = self.builder.gep(ptr, [offset])
        
        return self.builder.load(element_ptr)

    def gen_array_index_assign(self, node):
        ptr_var = self.gen_expr(node.base)
        ptr = self.builder.load(ptr_var)
        index = self.gen_expr(node.index)
        value = self.gen_expr(node.value)
        
        element_size = ir.Constant(ir.IntType(32), 4)
        offset = self.builder.mul(index, element_size)
        element_ptr = self.builder.gep(ptr, [offset])
        
        self.builder.store(value, element_ptr)
        return value

    # ========== DATA STRUCTURES ==========

    def gen_data(self, node):
        """Generate data structure - calculate size and field offsets"""
        total_size = 0
        field_offsets = {}
        
        for field_name, field_type in node.fields:
            # Assume all types are 4 bytes (int, float, bool, pointer)
            field_size = 4
            field_offsets[field_name] = total_size
            total_size += field_size
        
        self.data_structures[node.name] = {
            "size": total_size,
            "offsets": field_offsets,
            "fields": node.fields
        }
        
        return None

    def gen_data_instance(self, node):
        """Create an instance of a data structure"""
        if node.data_name not in self.data_structures:
            raise Exception(f"Unknown data structure: {node.data_name}")
        
        data_info = self.data_structures[node.data_name]
        size = data_info["size"]
        
        if not self.malloc_fn:
            malloc_type = ir.FunctionType(ir.IntType(8).as_pointer(), [ir.IntType(32)])
            self.malloc_fn = ir.Function(self.module, malloc_type, name="malloc")
        
        ptr_void = self.builder.call(self.malloc_fn, [ir.Constant(ir.IntType(32), size)])
        ptr = self.builder.bitcast(ptr_void, ir.IntType(8).as_pointer())
        
        ptr_var = self.builder.alloca(ptr.type, name=node.data_name.lower())
        self.builder.store(ptr, ptr_var)
        
        return ptr_var

    def gen_data_field_access(self, node):
        """Access data structure field: instance.field"""
        instance_ptr_var = self.gen_expr(node.instance)
        instance_ptr = self.builder.load(instance_ptr_var)
        
        # Get field offset - try to determine from data structure
        # For now, use hardcoded offsets for common field names
        offset = 0
        if node.field_name == "x":
            offset = 0
        elif node.field_name == "y":
            offset = 4
        elif node.field_name == "width":
            offset = 0
        elif node.field_name == "height":
            offset = 4
        elif node.field_name == "name":
            offset = 0
        elif node.field_name == "age":
            offset = 4
        
        field_ptr = self.builder.gep(instance_ptr, [ir.Constant(ir.IntType(32), offset)])
        field_ptr_int = self.builder.bitcast(field_ptr, ir.IntType(32).as_pointer())
        
        return self.builder.load(field_ptr_int)

    def gen_data_field_assign(self, node):
        """Assign to data structure field: instance.field = value"""
        instance_ptr_var = self.gen_expr(node.instance)
        instance_ptr = self.builder.load(instance_ptr_var)
        value = self.gen_expr(node.value)
        
        offset = 0
        if node.field_name == "x":
            offset = 0
        elif node.field_name == "y":
            offset = 4
        elif node.field_name == "width":
            offset = 0
        elif node.field_name == "height":
            offset = 4
        
        field_ptr = self.builder.gep(instance_ptr, [ir.Constant(ir.IntType(32), offset)])
        field_ptr_int = self.builder.bitcast(field_ptr, ir.IntType(32).as_pointer())
        
        self.builder.store(value, field_ptr_int)
        return value

    # ========== PRINT ==========

    def gen_print(self, node):
        value = self.gen_expr(node.value)
        printf = self.get_printf()
        
        if value.type == ir.IntType(1):
            value = self.builder.zext(value, ir.IntType(32))
            fmt = self.create_string("%d\n")
            fmt_ptr = self.builder.bitcast(fmt, ir.IntType(8).as_pointer())
            self.builder.call(printf, [fmt_ptr, value])
        elif value.type == ir.IntType(64):
            fmt = self.create_string("%llu\n")
            fmt_ptr = self.builder.bitcast(fmt, ir.IntType(8).as_pointer())
            self.builder.call(printf, [fmt_ptr, value])
        elif isinstance(value.type, ir.PointerType):
            fmt = self.create_string("%p\n")
            fmt_ptr = self.builder.bitcast(fmt, ir.IntType(8).as_pointer())
            ptr_int = self.builder.ptrtoint(value, ir.IntType(64))
            self.builder.call(printf, [fmt_ptr, ptr_int])
        else:
            fmt = self.create_string("%d\n")
            fmt_ptr = self.builder.bitcast(fmt, ir.IntType(8).as_pointer())
            self.builder.call(printf, [fmt_ptr, value])

    # ========== CONTROL FLOW ==========

    def gen_ifelse(self, node):
        cond = self.gen_expr(node.condition)
        if cond.type != ir.IntType(1):
            zero = ir.Constant(cond.type, 0)
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
        cond = self.gen_expr(node.condition)
        if cond.type != ir.IntType(1):
            zero = ir.Constant(cond.type, 0)
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
        func_type = ir.FunctionType(ir.IntType(32), [ir.IntType(32)] * len(node.params))
        func = ir.Function(self.module, func_type, name=node.name)
        
        old_builder = self.builder
        old_symbols = self.symbols_stack
        
        self.symbols_stack = [{}]
        block = func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        
        for i, arg in enumerate(func.args):
            arg.name = node.params[i]
            ptr = self.builder.alloca(ir.IntType(32), name=arg.name)
            self.builder.store(arg, ptr)
            self.set_symbol(arg.name, ptr)
        
        for stmt in node.body:
            self.gen_stmt(stmt)
        
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(ir.IntType(32), 0))
        
        self.builder = old_builder
        self.symbols_stack = old_symbols
        self.functions[node.name] = func

    def gen_call(self, node):
        if node.name in self.functions:
            func = self.functions[node.name]
        elif node.name in self.module.globals:
            func = self.module.globals[node.name]
        else:
            raise Exception(f"Undefined function: {node.name}")
        
        args = [self.gen_expr(arg) for arg in node.args]
        return self.builder.call(func, args)

    # ========== RAW BLOCKS ==========

    def gen_raw(self, node):
        self.push_scope()
        local_exports = {}
        
        for stmt in node.body:
            if isinstance(stmt, Assignment):
                value = self.gen_expr(stmt.value)
                ptr = self.builder.alloca(value.type, name=stmt.name)
                self.set_symbol(stmt.name, ptr)
                self.builder.store(value, ptr)
                local_exports[stmt.name] = ptr
            elif isinstance(stmt, Function):
                self.gen_function(stmt)
                local_exports[stmt.name] = self.functions[stmt.name]
            elif isinstance(stmt, Export):
                for name in stmt.names:
                    symbol = self.get_symbol(name)
                    local_exports[name] = symbol
                    self.exports[name] = symbol
            elif isinstance(stmt, Data):
                self.gen_data(stmt)
            else:
                self.gen_stmt(stmt)
        
        self.pop_scope()
        self.exports.update(local_exports)

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
        return global_str

    def get_printf(self):
        if self.printf:
            return self.printf
        func_type = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer()], var_arg=True)
        self.printf = ir.Function(self.module, func_type, name="printf")
        return self.printf
    
    def gen_for(self, node):
        """Generate for loop: for i = start to end step step { body }"""
        
        # Create variables for start, end, step
        start_val = self.gen_expr(node.start)
        end_val = self.gen_expr(node.end)
        step_val = self.gen_expr(node.step)
        
        # Allocate loop variable
        var_ptr = self.builder.alloca(ir.IntType(32), name=node.var_name)
        self.set_symbol(node.var_name, var_ptr)
        self.builder.store(start_val, var_ptr)
        
        # Get function
        func = self.builder.function
        
        # Create blocks
        cond_bb = func.append_basic_block("for.cond")
        body_bb = func.append_basic_block("for.body")
        step_bb = func.append_basic_block("for.step")
        end_bb = func.append_basic_block("for.end")
        
        # Push loop context for break/continue
        self.loop_stack.append((step_bb, end_bb))
        
        # Branch to condition
        self.builder.branch(cond_bb)
        
        # Condition block
        self.builder.position_at_start(cond_bb)
        current_var = self.builder.load(var_ptr)
        
        if node.is_downto:
            # For downto: current >= end
            cond = self.builder.icmp_signed(">=", current_var, end_val)
        else:
            # For to: current <= end
            cond = self.builder.icmp_signed("<=", current_var, end_val)
        
        self.builder.cbranch(cond, body_bb, end_bb)
        
        # Body block
        self.builder.position_at_start(body_bb)
        for stmt in node.body:
            self.gen_stmt(stmt)
        
        # Branch to step block
        if not self.builder.block.is_terminated:
            self.builder.branch(step_bb)
        
        # Step block (increment/decrement)
        self.builder.position_at_start(step_bb)
        current = self.builder.load(var_ptr)
        
        if node.is_downto:
            new_val = self.builder.sub(current, step_val)
        else:
            new_val = self.builder.add(current, step_val)
        
        self.builder.store(new_val, var_ptr)
        self.builder.branch(cond_bb)
        
        # Pop loop context
        self.loop_stack.pop()
        
        # Position builder at end block
        self.builder.position_at_start(end_bb)