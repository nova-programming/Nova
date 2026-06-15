import os
from nova_ast.nodes import *

class Arm64Codegen:
    """AArch64 (ARM64) codegen for Apple Silicon (macOS) and Windows ARM64. Full feature parity with x86_64."""

    def __init__(self, ast_nodes, module_names=None, debug_mode=0, target_os="windows"):
        self.ast = ast_nodes
        self.debug_mode = debug_mode
        self.module_names = module_names or []
        self.target_os = target_os
        self.assembly = []
        self.data_section = []
        self.string_literals = {}
        self.str_count = 0
        self.label_count = 0
        self.local_vars = {}
        self.local_offset = 0
        self.local_aligned = 0
        self.loop_labels = []
        self.prop_offsets = {}
        self.struct_defs = {}
        self.string_vars = set()
        self.func_returns = {}
        self._reg_pool = []

    def get_prop_offset(self, name):
        if name not in self.prop_offsets:
            self.prop_offsets[name] = len(self.prop_offsets) * 8
        return self.prop_offsets[name]

    def get_struct_prop_offset(self, struct_name, field_name):
        if struct_name in self.struct_defs:
            d = self.struct_defs[struct_name]
            for i, (fname, ftype) in enumerate(d.fields):
                if fname == field_name:
                    return i * 8
        return self.get_prop_offset(field_name)

    def is_leaf_expr(self, node):
        if isinstance(node, Number): return True
        if isinstance(node, Boolean): return True
        if isinstance(node, Variable): return True
        return False

    def next_label(self, prefix="L"):
        self.label_count += 1
        return f"{prefix}_{self.label_count}"

    def _get_type_name(self, node, default='any'):
        """Get inferred type name as string, handling ScalarType objects."""
        t = getattr(node, 'inferred_type', None)
        if t is not None:
            return str(t)
        return default

    def _is_float_expr(self, node):
        if self._get_type_name(node, None) == 'float': return True
        if isinstance(node, Number) and isinstance(node.value, float): return True
        return False

    def _is_string_expr(self, node):
        if isinstance(node, String): return True
        if isinstance(node, Variable) and node.name in self.string_vars: return True
        if self._get_type_name(node, None) == 'string': return True
        if isinstance(node, BinOp) and node.op == '+':
            return self._is_string_expr(node.left) or self._is_string_expr(node.right)
        if isinstance(node, Call):
            if node.name in self.func_returns and self.func_returns[node.name] == 'string': return True
        if isinstance(node, ArrayIndex):
            base_type = self._get_type_name(node.base)
            if base_type == 'string' or self._is_string_expr(node.base): return True
            if isinstance(node.base, DataFieldAccess) and node.base.field_name in ['struct_names', 'prop_names', 'local_var_names']:
                return False
            return base_type == 'string' or self._is_string_expr(node.base)
        if isinstance(node, DataFieldAccess):
            if self._get_type_name(node, None) == 'string': return True
            if node.instance and self._get_type_name(node.instance, None) == 'string': return True
            if node.instance and node.instance in self.string_vars: return True
        if isinstance(node, StrConvert): return True
        if isinstance(node, Slice):
            if self._get_type_name(node.base, None) == 'string': return True
        return False

    def _is_file_expr(self, node):
        if isinstance(node, Openf): return True
        if isinstance(node, OpenFile): return True
        return self._get_type_name(node, None) == 'file'

    # --- Register allocator for expression evaluation ---
    def _alloc_reg(self):
        if not self._reg_pool:
            self._reg_pool = [f"x{i}" for i in range(16)]
        return self._reg_pool.pop(0)

    def _free_reg(self, reg):
        if reg not in self._reg_pool:
            self._reg_pool.append(reg)

    def _free_all(self):
        self._reg_pool = [f"x{i}" for i in range(16)]

    def _compile_expr_to_reg(self, node):
        """Compile expression into a register. Returns reg name. Caller MUST _free_reg."""
        if isinstance(node, Number):
            reg = self._alloc_reg()
            if isinstance(node.value, float):
                import struct
                bits = struct.unpack('<I', struct.pack('<f', node.value))[0]
                self.assembly.append(f"    movz {reg}, #{bits}")
            else:
                val = int(node.value)
                if val < 0: val = (1 << 64) + val
                w0 = val & 0xFFFF
                w1 = (val >> 16) & 0xFFFF
                w2 = (val >> 32) & 0xFFFF
                w3 = (val >> 48) & 0xFFFF
                self.assembly.append(f"    movz {reg}, #{w0}")
                if w1: self.assembly.append(f"    movk {reg}, #{w1}, lsl 16")
                if w2: self.assembly.append(f"    movk {reg}, #{w2}, lsl 32")
                if w3: self.assembly.append(f"    movk {reg}, #{w3}, lsl 48")
            return reg
        elif isinstance(node, Boolean):
            reg = self._alloc_reg()
            self.assembly.append(f"    movz {reg}, #{1 if node.value else 0}")
            return reg
        elif isinstance(node, String):
            reg = self._alloc_reg()
            label = self.add_string_literal(node.value)
            self.assembly.append(f"    adrp {reg}, {label}@PAGE")
            self.assembly.append(f"    add {reg}, {reg}, {label}@PAGEOFF")
            return reg
        elif isinstance(node, Variable):
            reg = self._alloc_reg()
            offset = self.local_vars[node.name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov {reg}, {offset}")
            else:
                self.assembly.append(f"    ldr {reg}, [sp, #{self.local_aligned - offset}]")
            return reg
        elif isinstance(node, UnaryOp):
            in_reg = self._compile_expr_to_reg(node.value)
            if node.op == "-":
                self.assembly.append(f"    neg {in_reg}, {in_reg}")
            elif node.op == "not":
                self.assembly.append(f"    cmp {in_reg}, #0")
                self.assembly.append(f"    cset {in_reg}, eq")
            return in_reg
        elif isinstance(node, BinOp):
            return self._compile_binop_to_reg(node)
        elif isinstance(node, Compare):
            return self._compile_compare_to_reg(node)
        # Fallback: push to stack, pop into register
        self.compile_expr(node)
        reg = self._alloc_reg()
        self.assembly.append(f"    ldr {reg}, [sp], #16")
        return reg

    def _compile_binop_to_reg(self, node):
        """Compile binary op into a register. Returns reg name."""
        if node.op == "and":
            label_false = self.next_label("and_false")
            label_end = self.next_label("and_end")
            result_reg = self._alloc_reg()
            lr = self._compile_expr_to_reg(node.left)
            self.assembly.append(f"    cmp {lr}, #0")
            self.assembly.append(f"    b.eq {label_false}")
            self._free_reg(lr)
            rr = self._compile_expr_to_reg(node.right)
            self.assembly.append(f"    cmp {rr}, #0")
            self.assembly.append(f"    b.eq {label_false}")
            self._free_reg(rr)
            self.assembly.append(f"    movz {result_reg}, #1")
            self.assembly.append(f"    b {label_end}")
            self.assembly.append(f"{label_false}:")
            self.assembly.append(f"    movz {result_reg}, #0")
            self.assembly.append(f"{label_end}:")
            return result_reg
        elif node.op == "or":
            label_true = self.next_label("or_true")
            label_end = self.next_label("or_end")
            result_reg = self._alloc_reg()
            lr = self._compile_expr_to_reg(node.left)
            self.assembly.append(f"    cmp {lr}, #0")
            self.assembly.append(f"    b.ne {label_true}")
            self._free_reg(lr)
            rr = self._compile_expr_to_reg(node.right)
            self.assembly.append(f"    cmp {rr}, #0")
            self.assembly.append(f"    b.ne {label_true}")
            self._free_reg(rr)
            self.assembly.append(f"    movz {result_reg}, #0")
            self.assembly.append(f"    b {label_end}")
            self.assembly.append(f"{label_true}:")
            self.assembly.append(f"    movz {result_reg}, #1")
            self.assembly.append(f"{label_end}:")
            return result_reg
        elif self._is_float_expr(node.left) or self._is_float_expr(node.right):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.assembly.append("    ldr d1, [sp]")
            self.assembly.append("    ldr d0, [sp, #16]")
            self.assembly.append("    add sp, sp, #32")
            if node.op == "+":      self.assembly.append("    fadd d0, d0, d1")
            elif node.op == "-":     self.assembly.append("    fsub d0, d0, d1")
            elif node.op == "*":     self.assembly.append("    fmul d0, d0, d1")
            elif node.op == "/":     self.assembly.append("    fdiv d0, d0, d1")
            else:                    self.assembly.append("    fadd d0, d0, d1")
            self.assembly.append("    sub sp, sp, #8")
            self.assembly.append("    str d0, [sp]")
            reg = self._alloc_reg()
            self.assembly.append(f"    ldr {reg}, [sp], #8")
            return reg
        elif node.op == "+" and (self._is_string_expr(node.left) or self._is_string_expr(node.right)):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    str x1, [sp, #-16]!")
            self.assembly.append("    str x0, [sp, #-16]!")
            self.assembly.append("    bl _concat_strings")
            self.assembly.append("    add sp, sp, #32")
            reg = self._alloc_reg()
            self.assembly.append(f"    mov {reg}, x0")
            return reg
        else:
            left_reg = self._compile_expr_to_reg(node.left)
            right_reg = self._compile_expr_to_reg(node.right)
            if node.op == "+":
                self.assembly.append(f"    add {left_reg}, {left_reg}, {right_reg}")
            elif node.op == "-":
                self.assembly.append(f"    sub {left_reg}, {left_reg}, {right_reg}")
            elif node.op == "*":
                self.assembly.append(f"    mul {left_reg}, {left_reg}, {right_reg}")
            elif node.op == "/":
                self.assembly.append(f"    sdiv {left_reg}, {left_reg}, {right_reg}")
            elif node.op == "%":
                tmp = self._alloc_reg()
                self.assembly.append(f"    sdiv {tmp}, {left_reg}, {right_reg}")
                self.assembly.append(f"    msub {left_reg}, {tmp}, {right_reg}, {left_reg}")
                self._free_reg(tmp)
            elif node.op == "&":
                self.assembly.append(f"    and {left_reg}, {left_reg}, {right_reg}")
            elif node.op == "<<":
                self.assembly.append(f"    lsl {left_reg}, {left_reg}, {right_reg}")
            elif node.op == ">>":
                self.assembly.append(f"    asr {left_reg}, {left_reg}, {right_reg}")
            self._free_reg(right_reg)
            return left_reg

    def _compile_compare_to_reg(self, node):
        """Compile comparison into a register. Returns reg name."""
        is_float_cmp = self._is_float_expr(node.left) or self._is_float_expr(node.right)
        left_is_str = self._is_string_expr(node.left) or self._get_type_name(node.left) == 'string'
        right_is_str = self._is_string_expr(node.right) or self._get_type_name(node.right) == 'string'
        is_str_cmp = False
        if left_is_str or right_is_str:
            left_is_zero = isinstance(node.left, Number) and node.left.value == 0
            right_is_zero = isinstance(node.right, Number) and node.right.value == 0
            if not ((left_is_str and right_is_zero) or (right_is_str and left_is_zero)):
                is_str_cmp = True

        if is_float_cmp:
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.assembly.append("    ldr d1, [sp]")
            self.assembly.append("    ldr d0, [sp, #16]")
            self.assembly.append("    add sp, sp, #32")
            self.assembly.append("    fcmp d0, d1")
            setcc_map = {"==": "eq", "!=": "ne", "<": "lo", ">": "hi", "<=": "ls", ">=": "hs"}
            cond = setcc_map.get(node.op, "eq")
            reg = self._alloc_reg()
            self.assembly.append(f"    cset {reg}, {cond}")
            return reg
        elif is_str_cmp:
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    str x1, [sp, #-16]!")
            self.assembly.append("    str x0, [sp, #-16]!")
            self.assembly.append("    bl _strcmp")
            self.assembly.append("    add sp, sp, #32")
            reg = self._alloc_reg()
            self.assembly.append(f"    mov {reg}, x0")
            self.assembly.append(f"    cmp {reg}, #0")
            setcc_map = {"==": "eq", "!=": "ne", "<": "lt", ">": "gt", "<=": "le", ">=": "ge"}
            cond = setcc_map.get(node.op, "eq")
            self.assembly.append(f"    cset {reg}, {cond}")
            return reg
        else:
            left_reg = self._compile_expr_to_reg(node.left)
            right_reg = self._compile_expr_to_reg(node.right)
            self.assembly.append(f"    cmp {left_reg}, {right_reg}")
            setcc_map = {"==": "eq", "!=": "ne", "<": "lt", ">": "gt", "<=": "le", ">=": "ge"}
            cond = setcc_map.get(node.op, "eq")
            self.assembly.append(f"    cset {left_reg}, {cond}")
            self._free_reg(right_reg)
            return left_reg

    def add_string_literal(self, value):
        if value not in self.string_literals:
            label = f"str_{self.str_count}"
            self.str_count += 1
            escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
            escaped = escaped.replace('\0', '\\0')
            self.data_section.append(f'{label}: .asciz "{escaped}"')
            self.string_literals[value] = label
            return label
        return self.string_literals[value]

    def peephole(self):
        lines = self.assembly
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 1. Dead str/ldr pair: str xN,[sp,#-16]! / ldr xN,[sp],#16
            if (i + 1 < len(lines) and
                stripped.startswith("str x") and stripped.endswith("[sp, #-16]!") and
                lines[i+1].strip().startswith("ldr x") and lines[i+1].strip().endswith("[sp], #16")):
                r1 = stripped.split()[1].rstrip(",")
                r2 = lines[i+1].strip().split()[1].rstrip(",")
                if r1 == r2 and r1.startswith("x") and r1[1:].isdigit():
                    i += 2
                    continue

            # 2. cbz/cbnz: cmp xN,#0 / b.eq L → cbz xN,L
            if (i + 1 < len(lines) and
                stripped.startswith("cmp x") and stripped.endswith("#0")):
                next_line = lines[i+1].strip()
                if next_line.startswith("b.eq ") or next_line.startswith("b.ne "):
                    try:
                        reg_str = stripped.split()[1].rstrip(",")
                        reg = int(reg_str[1:])  # "x0" → 0
                        if reg <= 15:
                            label = next_line.split(" ", 1)[1]
                            if next_line.startswith("b.eq "):
                                result.append(f"    cbz x{reg}, {label}")
                            else:
                                result.append(f"    cbnz x{reg}, {label}")
                            i += 2
                            continue
                    except (ValueError, IndexError):
                        pass

            result.append(line)
            i += 1
        self.assembly = result

    def generate(self):
        self.assembly.append(".text")
        self.assembly.append(".align 2")
        entry = "_main" if self.target_os == "windows" else "main"
        self.assembly.append(f".global {entry}")

        self.assembly.append(".extern _printf")
        self.assembly.append(".extern _malloc")
        self.assembly.append(".extern _free")
        self.assembly.append(".extern _realloc")
        self.assembly.append(".extern _fopen")
        self.assembly.append(".extern _fclose")
        self.assembly.append(".extern _fread")
        self.assembly.append(".extern _fwrite")
        self.assembly.append(".extern _fputs")
        self.assembly.append(".extern _fputc")
        self.assembly.append(".extern _fseek")
        self.assembly.append(".extern _ftell")
        self.assembly.append(".extern _fflush")
        self.assembly.append(".extern _exit")
        self.assembly.append(".extern _system")
        self.assembly.append(".extern _strlen")
        self.assembly.append(".extern _strcmp")
        self.assembly.append(".extern _strcpy")
        self.assembly.append(".extern _strcat")
        self.assembly.append(".extern _strstr")
        self.assembly.append(".extern _memset")
        self.assembly.append(".extern _sprintf")
        self.assembly.append(".extern _dict_new")
        self.assembly.append(".extern _dict_get")
        self.assembly.append(".extern _dict_set")
        self.assembly.append(".extern _dict_has")
        self.assembly.append(".extern _dict_remove")
        self.assembly.append(".extern _dict_keys")
        self.assembly.append(".extern _dict_values")
        self.assembly.append(".extern _dict_items")
        self.assembly.append(".extern _abs")
        self.assembly.append(".extern _min")
        self.assembly.append(".extern _max")
        self.assembly.append(".extern _file_exists")
        self.assembly.append(".extern _file_size")
        self.assembly.append(".extern _file_type")
        self.assembly.append(".extern _now")

        self.data_section.append(".align 3")
        self.data_section.append('fmt_int: .asciz "%d\\n"')
        self.data_section.append('fmt_int_pure: .asciz "%d"')
        self.data_section.append('fmt_str: .asciz "%s\\n"')
        self.data_section.append('fmt_float: .asciz "%f\\n"')
        self.data_section.append('fmt_float_pure: .asciz "%f"')
        self.data_section.append('debug_prefix: .asciz "debug - [line "')
        self.data_section.append('debug_suffix: .asciz "]: "')
        self.data_section.append('str_fmode_a: .asciz "a"')
        self.data_section.append('str_fmode_rw: .asciz "r+"')
        self.data_section.append('str_fmode_wp: .asciz "w+"')
        self.data_section.append('str_fmode_w: .asciz "w"')

        self.data_section.append("char_strings:")
        for i in range(256):
            self.data_section.append(f"    .byte {i}")
            self.data_section.append(f"    .byte 0")

        functions = [node for node in self.ast if isinstance(node, Function)]
        top_level = [node for node in self.ast if not isinstance(node, Function) and not isinstance(node, Import) and not isinstance(node, ClassDef) and not isinstance(node, Data)]

        self.func_returns = {}
        for n in self.ast:
            if isinstance(n, Data):
                self.struct_defs[n.name] = n
                for field_name, field_type in n.fields:
                    self.get_prop_offset(field_name)
            elif isinstance(n, ClassDef):
                for field_name, field_type in n.fields:
                    self.get_prop_offset(field_name)
            elif isinstance(n, Function):
                self.func_returns[n.name] = n.return_type

        for fn in functions:
            self.compile_function(fn)

        entry = "_main" if self.target_os == "windows" else "main"
        self.assembly.append(f"{entry}:")
        self.assembly.append("    stp fp, lr, [sp, #-16]!")

        self.local_vars = {}
        self.local_offset = 0

        self.local_offset += 8
        self.local_vars["__argc"] = self.local_offset
        self.local_offset += 8
        self.local_vars["__argv"] = self.local_offset

        for node in top_level:
            self.scan_vars(node)

        aligned = (self.local_offset + 15) & ~15 if self.local_offset > 0 else 0
        self.local_aligned = aligned
        if aligned > 0:
            self.assembly.append(f"    sub sp, sp, #{aligned}")

        self.assembly.append(f"    str w0, [sp, #{aligned - 8}]")
        self.assembly.append(f"    str x1, [sp, #{aligned - 16}]")

        for node in top_level:
            self.compile_stmt(node)

        if aligned > 0:
            self.assembly.append(f"    add sp, sp, #{aligned}")
        self.assembly.append("    ldp fp, lr, [sp], #16")
        self.assembly.append("    mov w0, #0")
        self.assembly.append("    ret")

        self._emit_concat_strings()
        self._emit_slice_string()
        self._emit_out_of_bounds()

        self.peephole()

        self.assembly.append(".data")
        for line in self.data_section:
            self.assembly.append(line)

        return "\n".join(self.assembly)

    def _emit_concat_strings(self):
        self.assembly.append("_concat_strings:")
        self.assembly.append("    stp fp, lr, [sp, #-16]!")
        self.assembly.append("    sub sp, sp, #32")
        self.assembly.append("    str x19, [sp, #16]")
        self.assembly.append("    ldr x0, [sp, #48]")
        self.assembly.append("    bl _strlen")
        self.assembly.append("    mov x19, x0")
        self.assembly.append("    ldr x0, [sp, #56]")
        self.assembly.append("    bl _strlen")
        self.assembly.append("    add x19, x19, x0")
        self.assembly.append("    add x0, x19, #1")
        self.assembly.append("    bl _malloc")
        self.assembly.append("    str x0, [sp, #8]")
        self.assembly.append("    ldr x1, [sp, #48]")
        self.assembly.append("    mov x0, x0")
        self.assembly.append("    bl _strcpy")
        self.assembly.append("    ldr x1, [sp, #56]")
        self.assembly.append("    ldr x0, [sp, #8]")
        self.assembly.append("    bl _strcat")
        self.assembly.append("    ldr x0, [sp, #8]")
        self.assembly.append("    ldr x19, [sp, #16]")
        self.assembly.append("    add sp, sp, #32")
        self.assembly.append("    ldp fp, lr, [sp], #16")
        self.assembly.append("    ret")

    def _emit_slice_string(self):
        self.assembly.append("_slice_string:")
        self.assembly.append("    stp fp, lr, [sp, #-16]!")
        self.assembly.append("    sub sp, sp, #48")
        self.assembly.append("    str x19, [sp, #32]")
        self.assembly.append("    ldr x0, [sp, #64]")
        self.assembly.append("    ldr w1, [sp, #72]")
        self.assembly.append("    ldr w2, [sp, #80]")
        self.assembly.append("    sub w2, w2, w1")
        self.assembly.append("    cmp w2, #0")
        self.assembly.append("    b.ge L_slice_alloc_arm")
        self.assembly.append("    mov w2, #0")
        self.assembly.append("L_slice_alloc_arm:")
        self.assembly.append("    str w2, [sp, #24]")
        self.assembly.append("    add w0, w2, #1")
        self.assembly.append("    bl _malloc")
        self.assembly.append("    str x0, [sp, #16]")
        self.assembly.append("    ldr w2, [sp, #24]")
        self.assembly.append("    ldr x0, [sp, #64]")
        self.assembly.append("    ldr w1, [sp, #72]")
        self.assembly.append("    add x0, x0, w1")
        self.assembly.append("    ldr x1, [sp, #16]")
        self.assembly.append("    str x1, [sp, #8]")
        self.assembly.append("    str w2, [sp, #40]")
        self.assembly.append("    mov w3, #0")
        self.assembly.append("    cmp w2, #0")
        self.assembly.append("    b.le L_slice_done_arm")
        self.assembly.append("L_slice_copy_arm:")
        self.assembly.append("    ldrb w4, [x0, x3]")
        self.assembly.append("    strb w4, [x1, x3]")
        self.assembly.append("    add w3, w3, #1")
        self.assembly.append("    cmp w3, w2")
        self.assembly.append("    b.lt L_slice_copy_arm")
        self.assembly.append("L_slice_done_arm:")
        self.assembly.append("    ldr x1, [sp, #8]")
        self.assembly.append("    ldr w2, [sp, #40]")
        self.assembly.append("    strb wzr, [x1, x2]")
        self.assembly.append("    ldr x0, [sp, #8]")
        self.assembly.append("    ldr x19, [sp, #32]")
        self.assembly.append("    add sp, sp, #48")
        self.assembly.append("    ldp fp, lr, [sp], #16")
        self.assembly.append("    ret")

    def _emit_out_of_bounds(self):
        self.data_section.append('oob_msg: .asciz "Index Out Of Bounds\\n"')
        self.assembly.append("_out_of_bounds:")
        self.assembly.append("    adrp x0, oob_msg@PAGE")
        self.assembly.append("    add x0, x0, oob_msg@PAGEOFF")
        self.assembly.append("    mov w0, #0")
        self.assembly.append("    bl _printf")
        self.assembly.append("    mov w0, #1")
        self.assembly.append("    bl _exit")

    def scan_vars(self, node):
        if isinstance(node, Assignment):
            if node.name not in self.local_vars:
                self.local_offset += 8
                self.local_vars[node.name] = self.local_offset
        elif isinstance(node, IfElse):
            for s in node.if_body: self.scan_vars(s)
            for s in node.else_body: self.scan_vars(s)
        elif isinstance(node, While):
            for s in node.body: self.scan_vars(s)
        elif isinstance(node, ForLoop):
            if node.var_name not in self.local_vars:
                self.local_offset += 8
                self.local_vars[node.var_name] = self.local_offset
            for s in node.body: self.scan_vars(s)
        elif isinstance(node, ForIn):
            if node.var_name not in self.local_vars:
                self.local_offset += 8
                self.local_vars[node.var_name] = self.local_offset
            for s in node.body: self.scan_vars(s)
        elif isinstance(node, RawBlock):
            for s in node.body: self.scan_vars(s)

    def compile_function(self, fn):
        self.assembly.append(f"_{fn.name}:")
        self.assembly.append("    stp fp, lr, [sp, #-16]!")

        old_local_vars = self.local_vars.copy()
        old_string_vars = self.string_vars.copy()
        self.local_vars = {}
        self.string_vars = set()
        for i, param in enumerate(fn.params):
            param_name = param[0] if isinstance(param, (list, tuple)) else param
            param_type = param[1] if isinstance(param, (list, tuple)) and len(param) > 1 else None
            self.local_vars[param_name] = -(16 + i * 8)
            if param_type == 'string':
                self.string_vars.add(param_name)

        self.local_offset = 0
        for stmt in fn.body:
            self.scan_vars(stmt)

        aligned = (self.local_offset + 15) & ~15 if self.local_offset > 0 else 0
        self.local_aligned = aligned
        if aligned > 0:
            self.assembly.append(f"    sub sp, sp, #{aligned}")

        for i, param in enumerate(fn.params):
            if i < 8:
                param_name = param[0] if isinstance(param, (list, tuple)) else param
                offset = self.local_vars[param_name]
                self.assembly.append(f"    str x{i}, [sp, #{aligned - offset}]")

        for stmt in fn.body:
            self.compile_stmt(stmt)

        if aligned > 0:
            self.assembly.append(f"    add sp, sp, #{aligned}")
        self.assembly.append("    ldp fp, lr, [sp], #16")
        self.assembly.append("    ret")

        self.local_vars = old_local_vars
        self.string_vars = old_string_vars

    def _emit_statement_line(self, node):
        if hasattr(node, 'line') and node.line > 0:
            self.assembly.append(f"    # line {node.line}")

    def compile_stmt(self, node):
        self._emit_statement_line(node)

        if isinstance(node, Assignment):
            self.compile_expr(node.value)
            self.assembly.append("    ldr x0, [sp], #16")
            offset = self.local_vars[node.name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov {offset}, x0")
            else:
                self.assembly.append(f"    str x0, [sp, #{self.local_aligned - offset}]")
            if self._is_string_expr(node.value):
                self.string_vars.add(node.name)
        elif isinstance(node, DataFieldAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.instance)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            offset = self.get_prop_offset(node.field_name)
            self.assembly.append(f"    str x1, [x0, #{offset}]")
        elif isinstance(node, Print):
            if self._is_file_expr(node.value):
                self.compile_expr(node.value)
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    ldr x0, [x0, #8]")
                self.assembly.append("    str x0, [sp, #-16]!")
                self.assembly.append("    adrp x0, fmt_str@PAGE")
                self.assembly.append("    add x0, x0, fmt_str@PAGEOFF")
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _printf")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _fflush")
            else:
                self.compile_expr(node.value)
                if self._is_string_expr(node.value):
                    self.assembly.append("    adrp x0, fmt_str@PAGE")
                    self.assembly.append("    add x0, x0, fmt_str@PAGEOFF")
                elif self._is_float_expr(node.value):
                    self.assembly.append("    adrp x0, fmt_float@PAGE")
                    self.assembly.append("    add x0, x0, fmt_float@PAGEOFF")
                else:
                    self.assembly.append("    adrp x0, fmt_int@PAGE")
                    self.assembly.append("    add x0, x0, fmt_int@PAGEOFF")
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _printf")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _fflush")
        elif isinstance(node, PrintD):
            if self.debug_mode == 1:
                self.assembly.append("    adrp x0, fmt_str@PAGE")
                self.assembly.append("    add x0, x0, fmt_str@PAGEOFF")
                self.assembly.append("    adrp x1, debug_prefix@PAGE")
                self.assembly.append("    add x1, x1, debug_prefix@PAGEOFF")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _printf")
                self.assembly.append("    adrp x0, fmt_int_pure@PAGE")
                self.assembly.append("    add x0, x0, fmt_int_pure@PAGEOFF")
                self.assembly.append(f"    mov w1, #{node.line}")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _printf")
                self.assembly.append("    adrp x0, fmt_str@PAGE")
                self.assembly.append("    add x0, x0, fmt_str@PAGEOFF")
                self.assembly.append("    adrp x1, debug_suffix@PAGE")
                self.assembly.append("    add x1, x1, debug_suffix@PAGEOFF")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _printf")
                self.compile_expr(node.value)
                if self._is_string_expr(node.value):
                    self.assembly.append("    adrp x0, fmt_str@PAGE")
                    self.assembly.append("    add x0, x0, fmt_str@PAGEOFF")
                elif self._is_float_expr(node.value):
                    self.assembly.append("    adrp x0, fmt_float_pure@PAGE")
                    self.assembly.append("    add x0, x0, fmt_float_pure@PAGEOFF")
                else:
                    self.assembly.append("    adrp x0, fmt_int_pure@PAGE")
                    self.assembly.append("    add x0, x0, fmt_int_pure@PAGEOFF")
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _printf")
                self.assembly.append("    mov w0, #10")
                self.assembly.append("    bl _fputc")
                self.assembly.append("    mov w0, #0")
                self.assembly.append("    bl _fflush")
        elif isinstance(node, Return):
            self.compile_expr(node.value)
            self.assembly.append("    ldr x0, [sp], #16")
            if self.local_aligned > 0:
                self.assembly.append(f"    add sp, sp, #{self.local_aligned}")
            self.assembly.append("    ldp fp, lr, [sp], #16")
            self.assembly.append("    ret")
        elif isinstance(node, IfElse):
            else_label = self.next_label("L_else")
            end_label = self.next_label("L_end")
            self.compile_expr(node.condition)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    cmp x0, #0")
            self.assembly.append(f"    b.eq {else_label}")
            for s in node.if_body: self.compile_stmt(s)
            self.assembly.append(f"    b {end_label}")
            self.assembly.append(f"{else_label}:")
            for s in node.else_body: self.compile_stmt(s)
            self.assembly.append(f"{end_label}:")
        elif isinstance(node, While):
            start_label = self.next_label("L_loop")
            end_label = self.next_label("L_loop_end")
            self.loop_labels.append((start_label, end_label))
            self.assembly.append(f"{start_label}:")
            self.compile_expr(node.condition)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    cmp x0, #0")
            self.assembly.append(f"    b.eq {end_label}")
            for s in node.body: self.compile_stmt(s)
            self.assembly.append(f"    b {start_label}")
            self.assembly.append(f"{end_label}:")
            self.loop_labels.pop()
        elif isinstance(node, ForLoop):
            start_val = node.start
            end_val = node.end
            step_val = node.step
            self.compile_expr(start_val)
            self.assembly.append("    ldr x0, [sp], #16")
            offset = self.local_vars[node.var_name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov {offset}, x0")
            else:
                self.assembly.append(f"    str x0, [sp, #{self.local_aligned - offset}]")
            loop_label = self.next_label("L_for")
            end_label = self.next_label("L_for_end")
            continue_label = self.next_label("L_for_cont")
            self.loop_labels.append((continue_label, end_label))
            self.assembly.append(f"{loop_label}:")
            if isinstance(offset, str):
                self.assembly.append(f"    mov x0, {offset}")
            else:
                self.assembly.append(f"    ldr x0, [sp, #{self.local_aligned - offset}]")
            self.assembly.append("    str x0, [sp, #-16]!")
            self.compile_expr(end_val)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    cmp x0, x1")
            if node.is_downto:
                self.assembly.append(f"    b.lt {end_label}")
            else:
                self.assembly.append(f"    b.gt {end_label}")
            for s in node.body: self.compile_stmt(s)
            self.assembly.append(f"{continue_label}:")
            self.compile_expr(step_val)
            self.assembly.append("    ldr x1, [sp], #16")
            if isinstance(offset, str):
                self.assembly.append(f"    add {offset}, {offset}, x1")
            else:
                self.assembly.append(f"    ldr x0, [sp, #{self.local_aligned - offset}]")
                self.assembly.append("    add x0, x0, x1")
                self.assembly.append(f"    str x0, [sp, #{self.local_aligned - offset}]")
            self.assembly.append(f"    b {loop_label}")
            self.assembly.append(f"{end_label}:")
            self.loop_labels.pop()
        elif isinstance(node, ForIn):
            loop_label = self.next_label("L_forin")
            end_label = self.next_label("L_forin_end")
            self.loop_labels.append((loop_label, end_label))
            self.compile_expr(node.collection)
            self.assembly.append("    ldr x3, [sp], #16")
            self.assembly.append("    ldr w0, [x3]")
            self.assembly.append("    str x0, [sp, #-16]!")
            offset = self.local_vars[node.var_name]
            if not isinstance(offset, str):
                self.assembly.append(f"    str xzr, [sp, #{self.local_aligned - offset}]")
            self.assembly.append(f"{loop_label}:")
            if isinstance(offset, str):
                self.assembly.append(f"    ldr w0, {offset}")
            else:
                self.assembly.append(f"    ldr w0, [sp, #{self.local_aligned - offset}]")
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    str x1, [sp, #-16]!")
            self.assembly.append("    cmp w0, w1")
            self.assembly.append(f"    b.ge {end_label}")
            self.assembly.append("    ldr x2, [x3, #16]")
            if isinstance(offset, str):
                self.assembly.append(f"    ldr w1, {offset}")
            else:
                self.assembly.append(f"    ldr w1, [sp, #{self.local_aligned - offset}]")
            self.assembly.append("    ldr w0, [x2, x1, lsl #2]")
            if not isinstance(offset, str):
                self.assembly.append(f"    str x0, [sp, #{self.local_aligned - 8}]")
            self.assembly.append("    str x0, [sp, #-16]!")
            for s in node.body: self.compile_stmt(s)
            if isinstance(offset, str):
                self.assembly.append(f"    add {offset}, {offset}, #1")
            else:
                self.assembly.append(f"    ldr x0, [sp, #{self.local_aligned - offset}]")
                self.assembly.append("    add x0, x0, #1")
                self.assembly.append(f"    str x0, [sp, #{self.local_aligned - offset}]")
            self.assembly.append(f"    b {loop_label}")
            self.assembly.append(f"{end_label}:")
            self.assembly.append("    add sp, sp, #16")
            self.loop_labels.pop()
        elif isinstance(node, Break):
            if self.loop_labels:
                self.assembly.append(f"    b {self.loop_labels[-1][1]}")
        elif isinstance(node, Continue):
            if self.loop_labels:
                self.assembly.append(f"    b {self.loop_labels[-1][0]}")
        elif isinstance(node, Free):
            self.compile_expr(node.ptr)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    bl _free")
        elif isinstance(node, PointerAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.ptr)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    str w1, [x0]")
        elif isinstance(node, ArrayIndexAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    ldr x2, [sp], #16")
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    cmp w1, #0")
            self.assembly.append("    b.lt _out_of_bounds")
            self.assembly.append("    ldr w3, [x2]")
            self.assembly.append("    cmp w1, w3")
            self.assembly.append("    b.ge _out_of_bounds")
            self.assembly.append("    ldr x3, [x2, #16]")
            self.assembly.append("    str w0, [x3, x1, lsl #2]")
        elif isinstance(node, WriteFile):
            self.compile_expr(node.content)
            self.compile_expr(node.file)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    bl _fputs")
        elif isinstance(node, CloseFile):
            self.compile_expr(node.value)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    bl _fclose")
        elif isinstance(node, Try):
            for stmt in node.body:
                self.compile_stmt(stmt)
        elif isinstance(node, Throw):
            self.compile_expr(node.value)
            self.assembly.append("    add sp, sp, #16")
        elif isinstance(node, RawBlock):
            for line in node.body:
                if isinstance(line, str): self.assembly.append(line)
                elif type(line).__name__ == "String": self.assembly.append(line.value)
                else: self.compile_stmt(line)
        else:
            self.compile_expr(node)
            self.assembly.append("    add sp, sp, #16")

    def compile_expr(self, node):
        if isinstance(node, Number):
            if isinstance(node.value, float):
                import struct
                bits = struct.unpack('<I', struct.pack('<f', node.value))[0]
                self.assembly.append(f"    mov w0, #{bits}")
                self.assembly.append("    str x0, [sp, #-16]!")
            else:
                val = int(node.value)
                if val < 0: val = (1 << 64) + val
                w0 = val & 0xFFFF
                w1 = (val >> 16) & 0xFFFF
                w2 = (val >> 32) & 0xFFFF
                w3 = (val >> 48) & 0xFFFF
                self.assembly.append(f"    movz x0, #{w0}")
                if w1: self.assembly.append(f"    movk x0, #{w1}, lsl 16")
                if w2: self.assembly.append(f"    movk x0, #{w2}, lsl 32")
                if w3: self.assembly.append(f"    movk x0, #{w3}, lsl 48")
                self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, String):
            label = self.add_string_literal(node.value)
            self.assembly.append(f"    adrp x0, {label}@PAGE")
            self.assembly.append(f"    add x0, x0, {label}@PAGEOFF")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, Boolean):
            val = 1 if node.value else 0
            self.assembly.append(f"    mov x0, #{val}")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, Variable):
            offset = self.local_vars[node.name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov x0, {offset}")
            else:
                self.assembly.append(f"    ldr x0, [sp, #{self.local_aligned - offset}]")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, BinOp):
            reg = self._compile_binop_to_reg(node)
            self.assembly.append(f"    str {reg}, [sp, #-16]!")
            self._free_reg(reg)
        elif isinstance(node, UnaryOp):
            reg = self._compile_expr_to_reg(node)
            self.assembly.append(f"    str {reg}, [sp, #-16]!")
            self._free_reg(reg)
        elif isinstance(node, Compare):
            reg = self._compile_compare_to_reg(node)
            self.assembly.append(f"    str {reg}, [sp, #-16]!")
            self._free_reg(reg)
        elif isinstance(node, Call):
            if node.name in self.struct_defs:
                struct_size = (max(self.prop_offsets.values()) + 8) if self.prop_offsets else 128
                struct_size = max(struct_size, 16)
                struct_size = (struct_size + 15) & ~15
                self.assembly.append(f"    mov x0, #{struct_size}")
                self.assembly.append("    bl _malloc")
                self.assembly.append("    str x0, [sp, #-16]!")
            else:
                for arg in reversed(node.args):
                    self.compile_expr(arg)
                n_args = len(node.args)
                if n_args >= 1:
                    self.assembly.append("    ldr x1, [sp], #16")
                if n_args >= 2:
                    self.assembly.append("    ldr x2, [sp], #16")
                if n_args >= 3:
                    self.assembly.append("    ldr x3, [sp], #16")
                if n_args >= 4:
                    self.assembly.append("    ldr x4, [sp], #16")
                if n_args >= 5:
                    self.assembly.append("    ldr x5, [sp], #16")
                if n_args >= 6:
                    self.assembly.append("    ldr x6, [sp], #16")
                if n_args >= 7:
                    self.assembly.append("    ldr x7, [sp], #16")
                if n_args >= 1:
                    self.assembly.append("    ldr x0, [sp], #16")
                else:
                    self.assembly.append("    mov x0, #0")

                if hasattr(node, 'module') and node.module:
                    module_prefix = node.module.replace(".", "_")
                    self.assembly.append(f"    bl _{module_prefix}_{node.name}")
                else:
                    self.assembly.append(f"    bl _{node.name}")
                self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, DataFieldAccess):
            self.compile_expr(node.instance)
            self.assembly.append("    ldr x0, [sp], #16")
            offset = self.get_prop_offset(node.field_name)
            self.assembly.append(f"    ldr x0, [x0, #{offset}]")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, Alloc):
            self.compile_expr(node.size)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    bl _malloc")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, PointerProperty):
            self.compile_expr(node.ptr)
            if node.property == "value":
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    ldr w0, [x0]")
                self.assembly.append("    str x0, [sp, #-16]!")
            elif node.property == "value_byte":
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    ldrb w0, [x0]")
                self.assembly.append("    str x0, [sp, #-16]!")
            elif node.property == "addr":
                pass
            else:
                raise Exception(f"[line {getattr(node, 'line', '?')}] Property {node.property} not supported in native codegen")
        elif isinstance(node, ArrayIndex):
            base_type = self._get_type_name(node.base)
            is_str = self._is_string_expr(node.base) or base_type == 'string'
            if isinstance(node.base, DataFieldAccess) and node.base.field_name in ['struct_names', 'prop_names', 'local_var_names']:
                is_str = False
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            if is_str:
                self.assembly.append("    ldrb w0, [x0, x1]")
                self.assembly.append("    lsl x0, x0, #1")
                self.assembly.append("    adrp x1, char_strings@PAGE")
                self.assembly.append("    add x1, x1, char_strings@PAGEOFF")
                self.assembly.append("    add x0, x1, x0")
                self.assembly.append("    str x0, [sp, #-16]!")
            else:
                self.assembly.append("    cmp w1, #0")
                self.assembly.append("    b.lt _out_of_bounds")
                self.assembly.append("    ldr w2, [x0]")
                self.assembly.append("    cmp w1, w2")
                self.assembly.append("    b.ge _out_of_bounds")
                self.assembly.append("    ldr x2, [x0, #16]")
                self.assembly.append("    ldr w0, [x2, x1, lsl #2]")
                self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, Openf):
            self.assembly.append("    mov x0, #24")
            self.assembly.append("    bl _malloc")
            self.assembly.append("    str x0, [sp, #-16]!")
            self.compile_expr(node.mode)
            self.assembly.append("    ldr x2, [sp], #16")
            self.compile_expr(node.path)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    str x0, [sp, #-16]!")
            self.assembly.append("    str x1, [x0, #16]")
            self.assembly.append("    bl _fopen")
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    str x1, [sp, #-16]!")
            self.assembly.append("    str w0, [x1]")
            self.assembly.append("    str x1, [sp, #-16]!")
        elif isinstance(node, OpenFile):
            self.compile_expr(node.path)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    adrp x1, str_fmode_a@PAGE")
            self.assembly.append("    add x1, x1, str_fmode_a@PAGEOFF")
            self.assembly.append("    bl _fopen")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, ReadFile):
            self.compile_expr(node.file)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    bl _sys_read")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, ListLiteral):
            n = len(node.elements)
            list_size = 16 + n * 4
            self.assembly.append(f"    mov x0, #{list_size}")
            self.assembly.append("    bl _malloc")
            self.assembly.append("    str x0, [sp, #-16]!")
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    str x1, [sp, #-16]!")
            self.assembly.append(f"    str w{n}, [x1]")
            self.assembly.append(f"    str w{list_size}, [x1, #8]")
            self.assembly.append("    add x2, x1, #16")
            for i, elem in enumerate(node.elements):
                self.compile_expr(elem)
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append(f"    str w0, [x2, #{i*4}]")
            self.assembly.append("    str x1, [sp, #-16]!")
        elif isinstance(node, DictLiteral):
            self.assembly.append("    bl _dict_new")
            self.assembly.append("    str x0, [sp, #-16]!")
            for k, v in zip(node.keys, node.values):
                self.compile_expr(v)
                self.compile_expr(k)
                self.assembly.append("    ldr x2, [sp], #16")
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    str x0, [sp, #-16]!")
                self.assembly.append("    bl _dict_set")
        elif isinstance(node, MethodCall):
            if node.method_name == "append":
                self.compile_expr(node.args[0])
                self.compile_expr(node.instance)
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    ldr w2, [x1]")
                self.assembly.append("    add w2, w2, #1")
                self.assembly.append("    str w2, [x1]")
                self.assembly.append("    ldr w3, [x1, #8]")
                self.assembly.append("    cmp w2, w3")
                self.assembly.append("    b.lt L_append_no_realloc_arm")
                self.assembly.append("    str x1, [sp, #-16]!")
                self.assembly.append("    str x0, [sp, #-16]!")
                self.assembly.append("    str x1, [sp, #-16]!")
                self.assembly.append("    lsl x0, x3, #1")
                self.assembly.append("    bl _realloc")
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    ldr w3, [x1, #8]")
                self.assembly.append("    lsl w3, w3, #1")
                self.assembly.append("    str w3, [x1, #8]")
                self.assembly.append("    add x2, x0, #16")
                self.assembly.append("    mov x1, x0")
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("L_append_no_realloc_arm:")
                self.assembly.append("    add x2, x1, #16")
                self.assembly.append("    sub w3, w2, #1")
                self.assembly.append("    str w0, [x2, x3, lsl #2]")
                self.assembly.append("    str x1, [sp, #-16]!")
            elif node.method_name == "pop":
                self.compile_expr(node.instance)
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    ldr w2, [x1]")
                self.assembly.append("    sub w2, w2, #1")
                self.assembly.append("    str w2, [x1]")
                self.assembly.append("    add x3, x1, #16")
                self.assembly.append("    ldr w0, [x3, x2, lsl #2]")
                self.assembly.append("    str x0, [sp, #-16]!")
            elif node.method_name == "open" or node.method_name == "open_append":
                self.compile_expr(node.args[0])
                self.assembly.append("    ldr x0, [sp], #16")
                mode_label = "str_fmode_w" if node.method_name == "open" else "str_fmode_a"
                self.assembly.append(f"    adrp x1, {mode_label}@PAGE")
                self.assembly.append(f"    add x1, x1, {mode_label}@PAGEOFF")
                self.assembly.append("    bl _fopen")
                self.assembly.append("    str x0, [sp, #-16]!")
            elif node.method_name == "read":
                self.compile_expr(node.instance)
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    bl _sys_read")
                self.assembly.append("    str x0, [sp, #-16]!")
            elif node.method_name == "write":
                self.compile_expr(node.args[0])
                self.compile_expr(node.instance)
                self.assembly.append("    ldr x1, [sp], #16")
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    bl _fputs")
                self.assembly.append("    str x0, [sp, #-16]!")
            elif node.method_name == "close":
                self.compile_expr(node.instance)
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    bl _fclose")
            elif node.method_name == "flush":
                self.compile_expr(node.instance)
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    bl _fflush")
            elif node.method_name in ("get", "has", "set", "remove", "keys", "values", "items"):
                for arg in node.args:
                    self.compile_expr(arg)
                self.compile_expr(node.instance)
                self.assembly.append("    ldr x0, [sp], #16")
                if len(node.args) >= 1:
                    self.assembly.append("    ldr x1, [sp], #16")
                if len(node.args) >= 2:
                    self.assembly.append("    ldr x2, [sp], #16")
                self.assembly.append(f"    bl _dict_{node.method_name}")
                self.assembly.append("    str x0, [sp, #-16]!")
            else:
                call_node = Call(node.method_name, node.args)
                call_node.line = node.line
                self.compile_expr(call_node)
        elif isinstance(node, Len):
            if self._is_string_expr(node.target):
                self.compile_expr(node.target)
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    bl _strlen")
                self.assembly.append("    str x0, [sp, #-16]!")
            else:
                self.compile_expr(node.target)
                self.assembly.append("    ldr x0, [sp], #16")
                self.assembly.append("    ldr w0, [x0]")
                self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, Slice):
            self.compile_expr(node.end)
            self.compile_expr(node.start)
            self.compile_expr(node.base)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x2, [sp], #16")
            self.assembly.append("    str x2, [sp, #-16]!")
            self.assembly.append("    str x1, [sp, #-16]!")
            self.assembly.append("    str x0, [sp, #-16]!")
            self.assembly.append("    bl _slice_string")
            self.assembly.append("    add sp, sp, #48")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, StrConvert):
            self.compile_expr(node.target)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    adrp x1, fmt_int_pure@PAGE")
            self.assembly.append("    add x1, x1, fmt_int_pure@PAGEOFF")
            self.assembly.append("    sub sp, sp, #16")
            self.assembly.append("    mov x2, sp")
            self.assembly.append("    mov w0, #0")
            self.assembly.append("    bl _sprintf")
            self.assembly.append("    mov x0, sp")
            self.assembly.append("    add sp, sp, #16")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, Block):
            for stmt in node.stmts[:-1]:
                self.compile_stmt(stmt)
            self.compile_expr(node.stmts[-1])
        else:
            raise Exception(f"[line {getattr(node, 'line', '?')}] Unsupported expression: {type(node).__name__}")
