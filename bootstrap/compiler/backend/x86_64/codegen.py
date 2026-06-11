import os
from nova_ast.nodes import *

class X86_64Codegen:
    """x86_64 System V AMD64 codegen for macOS/Linux. Uses C runtime (no inline assembly runtime)."""

    def __init__(self, ast_nodes, module_names=None, debug_mode=0):
        self.ast = ast_nodes
        self.debug_mode = debug_mode
        self.module_names = module_names or []
        self.assembly = []
        self.data_section = []
        self.string_literals = {}
        self.str_count = 0
        self.label_count = 0
        self.local_vars = {}
        self.local_offset = 0
        self.loop_labels = []
        self.prop_offsets = {}
        self.struct_defs = {}
        self.string_vars = set()
        self.func_returns = {}

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

    def compile_leaf_to_reg(self, node, reg):
        if isinstance(node, Number):
            if isinstance(node.value, float):
                import struct
                bits = struct.unpack('<I', struct.pack('<f', node.value))[0]
                self.assembly.append(f"    mov {reg}, {bits}")
            else:
                self.assembly.append(f"    mov {reg}, {node.value}")
        elif isinstance(node, Boolean):
            val = 1 if node.value else 0
            self.assembly.append(f"    mov {reg}, {val}")
        elif isinstance(node, Variable):
            offset = self.local_vars[node.name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov {reg}, {offset}")
            elif offset < 0:
                self.assembly.append(f"    mov {reg}, [rbp + {-offset}]")
            else:
                self.assembly.append(f"    mov {reg}, [rbp - {offset}]")

    def peephole(self):
        lines = self.assembly
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if (i + 1 < len(lines) and
                stripped == "push rax" and
                lines[i + 1].strip() == "pop rax"):
                i += 2
                continue
            if (i + 1 < len(lines) and
                stripped == "push rax" and
                lines[i + 1].strip() == "pop rbx"):
                result.append("    mov rbx, rax")
                i += 2
                continue
            if stripped == "xor eax, eax":
                result.append("    mov eax, 0")
                i += 1
                continue
            result.append(line)
            i += 1
        self.assembly = result

    def next_label(self, prefix="L"):
        self.label_count += 1
        return f"{prefix}_{self.label_count}"

    def _is_float_expr(self, node):
        if str(getattr(node, 'inferred_type', '')) == 'float':
            return True
        if isinstance(node, Number) and isinstance(node.value, float):
            return True
        return False

    def _is_string_expr(self, node):
        if isinstance(node, String): return True
        if isinstance(node, Variable) and node.name in self.string_vars: return True
        inferred = getattr(node, 'inferred_type', None)
        if str(inferred) == 'string': return True
        if isinstance(node, BinOp) and node.op == '+':
            return self._is_string_expr(node.left) or self._is_string_expr(node.right)
        if isinstance(node, Call):
            if node.name in self.func_returns and self.func_returns[node.name] == 'string':
                return True
        if isinstance(node, MethodCall):
            if node.method_name in ["platform", "file_read", "read", "read_all"]: return True
        if isinstance(node, ArrayIndex):
            base_type = getattr(node.base, 'inferred_type', 'any')
            if str(base_type) == 'string' or self._is_string_expr(node.base):
                return True
            if isinstance(node.base, DataFieldAccess) and node.base.field_name in ['struct_names', 'prop_names', 'local_var_names']:
                return False
            return str(base_type) == 'string' or self._is_string_expr(node.base)
        if isinstance(node, DataFieldAccess):
            inferred = getattr(node, 'inferred_type', None)
            if str(inferred) == 'string': return True
            if node.instance and hasattr(node.instance, 'inferred_type') and str(node.instance.inferred_type) == 'string':
                return True
            if node.instance and node.instance in self.string_vars:
                return True
        if isinstance(node, StrConvert): return True
        if isinstance(node, Slice):
            base_type = getattr(node.base, 'inferred_type', None)
            if str(base_type) == 'string': return True
        return False

    def _is_file_expr(self, node):
        if isinstance(node, Openf): return True
        if isinstance(node, OpenFile): return True
        return str(getattr(node, 'inferred_type', '')) == 'file'

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

    def generate(self):
        self.assembly.append(".intel_syntax noprefix")
        self.assembly.append(".global _main")

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
        self.data_section.append('str_const_sys_platform: .asciz "macos"')

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

        self.assembly.append(".text")

        for fn in functions:
            self.compile_function(fn)

        self.assembly.append("_main:")
        self.assembly.append("    push rbp")
        self.assembly.append("    mov rbp, rsp")
        self.assembly.append("    and rsp, -16")

        self.local_vars = {}
        self.local_offset = 0

        self.local_offset += 8
        self.local_vars["__argc"] = self.local_offset
        self.local_offset += 8
        self.local_vars["__argv"] = self.local_offset

        for node in top_level:
            self.scan_vars(node)

        if self.local_offset > 0:
            aligned = (self.local_offset + 15) & ~15
            self.assembly.append(f"    sub rsp, {aligned}")

        self.assembly.append("    mov [rbp - 8], rdi")
        self.assembly.append("    mov [rbp - 16], rsi")

        for node in top_level:
            self.compile_stmt(node)

        self.assembly.append("    mov rsp, rbp")
        self.assembly.append("    pop rbp")
        self.assembly.append("    xor eax, eax")
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
        self.assembly.append("    push rbp")
        self.assembly.append("    mov rbp, rsp")
        self.assembly.append("    push rbx")
        self.assembly.append("    sub rsp, 40")
        self.assembly.append("    mov rdi, [rbp + 16]")
        self.assembly.append("    call _strlen")
        self.assembly.append("    mov ebx, eax")
        self.assembly.append("    mov rdi, [rbp + 24]")
        self.assembly.append("    call _strlen")
        self.assembly.append("    add ebx, eax")
        self.assembly.append("    inc ebx")
        self.assembly.append("    mov edi, ebx")
        self.assembly.append("    call _malloc")
        self.assembly.append("    mov [rsp], rax")
        self.assembly.append("    mov rsi, [rbp + 16]")
        self.assembly.append("    mov rdi, rax")
        self.assembly.append("    call _strcpy")
        self.assembly.append("    mov rax, [rsp]")
        self.assembly.append("    mov rsi, [rbp + 24]")
        self.assembly.append("    mov rdi, rax")
        self.assembly.append("    call _strcat")
        self.assembly.append("    mov rax, [rsp]")
        self.assembly.append("    add rsp, 40")
        self.assembly.append("    pop rbx")
        self.assembly.append("    pop rbp")
        self.assembly.append("    ret")

    def _emit_slice_string(self):
        self.assembly.append("_slice_string:")
        self.assembly.append("    push rbp")
        self.assembly.append("    mov rbp, rsp")
        self.assembly.append("    push rbx")
        self.assembly.append("    push r12")
        self.assembly.append("    mov r12, rdi") # base string
        self.assembly.append("    mov ebx, esi") # start index
        self.assembly.append("    mov ecx, edx") # end index
        self.assembly.append("    mov rsi, r12")
        self.assembly.append("    sub ecx, ebx")
        self.assembly.append("    cmp ecx, 0")
        self.assembly.append("    jge L_slice_alloc_64")
        self.assembly.append("    xor ecx, ecx")
        self.assembly.append("L_slice_alloc_64:")
        self.assembly.append("    push rcx")
        self.assembly.append("    inc ecx")
        self.assembly.append("    mov edi, ecx")
        self.assembly.append("    mov r13, rsp")
        self.assembly.append("    and rsp, -16")
        self.assembly.append("    sub rsp, 32")
        self.assembly.append("    call _malloc")
        self.assembly.append("    add rsp, 32")
        self.assembly.append("    mov rsp, r13")
        self.assembly.append("    pop rcx")
        self.assembly.append("    mov rdi, rax")
        self.assembly.append("    add rsi, rbx")
        self.assembly.append("    push rdi")
        self.assembly.append("    push rcx")
        self.assembly.append("    cmp ecx, 0")
        self.assembly.append("    jle L_slice_done_64")
        self.assembly.append("L_slice_copy_64:")
        self.assembly.append("    mov al, [rsi]")
        self.assembly.append("    mov [rdi], al")
        self.assembly.append("    inc rsi")
        self.assembly.append("    inc rdi")
        self.assembly.append("    dec ecx")
        self.assembly.append("    cmp ecx, 0")
        self.assembly.append("    jg L_slice_copy_64")
        self.assembly.append("L_slice_done_64:")
        self.assembly.append("    pop rcx")
        self.assembly.append("    pop rdi")
        self.assembly.append("    mov byte ptr [rdi + rcx], 0")
        self.assembly.append("    mov rax, rdi")
        self.assembly.append("    pop r12")
        self.assembly.append("    pop rbx")
        self.assembly.append("    pop rbp")
        self.assembly.append("    ret")

    def _emit_out_of_bounds(self):
        self.data_section.append('oob_msg: .asciz "Index Out Of Bounds\\n"')
        self.assembly.append("_out_of_bounds:")
        self.assembly.append("    lea rdi, [rip + oob_msg]")
        self.assembly.append("    xor eax, eax")
        self.assembly.append("    sub rsp, 32")
        self.assembly.append("    call _printf")
        self.assembly.append("    add rsp, 32")
        self.assembly.append("    mov edi, 1")
        self.assembly.append("    sub rsp, 32")
        self.assembly.append("    call _exit")
        self.assembly.append("    add rsp, 32")


    def scan_vars(self, node):
        if isinstance(node, Assignment):
            if node.name not in self.local_vars:
                self.local_offset += 8
                self.local_vars[node.name] = self.local_offset
        elif isinstance(node, IfElse):
            for s in node.if_body:
                self.scan_vars(s)
            for s in node.else_body:
                self.scan_vars(s)
        elif isinstance(node, While):
            for s in node.body:
                self.scan_vars(s)
        elif isinstance(node, ForLoop):
            if node.var_name not in self.local_vars:
                self.local_offset += 8
                self.local_vars[node.var_name] = self.local_offset
            for s in node.body:
                self.scan_vars(s)
        elif isinstance(node, ForIn):
            if node.var_name not in self.local_vars:
                self.local_offset += 8
                self.local_vars[node.var_name] = self.local_offset
            for s in node.body:
                self.scan_vars(s)
        elif isinstance(node, RawBlock):
            for s in node.body:
                self.scan_vars(s)

    def compile_function(self, fn):
        old_local_vars = self.local_vars.copy()
        old_string_vars = self.string_vars.copy()
        self.local_vars = {}
        self.string_vars = set()
        self.local_offset = 0

        for param in fn.params:
            param_name = param[0] if isinstance(param, (list, tuple)) else param
            param_type = param[1] if isinstance(param, (list, tuple)) and len(param) > 1 else None
            self.local_offset += 8
            self.local_vars[param_name] = self.local_offset
            if param_type == 'string':
                self.string_vars.add(param_name)

        # Allocate space for locals and parameters
        for stmt in fn.body:
            self.scan_vars(stmt)

        self.assembly.append(f"_{fn.name}:")
        self.assembly.append("    push rbp")
        self.assembly.append("    mov rbp, rsp")
        self.assembly.append("    and rsp, -16")

        aligned = (self.local_offset + 15) & ~15
        if aligned > 0:
            self.assembly.append(f"    sub rsp, {aligned}")

        # Save incoming register arguments into their local variable slots
        for i, param in enumerate(fn.params):
            param_name = param[0] if isinstance(param, (list, tuple)) else param
            offset = self.local_vars[param_name]
            if i == 0:
                self.assembly.append(f"    mov [rbp - {offset}], rdi")
            elif i == 1:
                self.assembly.append(f"    mov [rbp - {offset}], rsi")
            elif i == 2:
                self.assembly.append(f"    mov [rbp - {offset}], rdx")
            elif i == 3:
                self.assembly.append(f"    mov [rbp - {offset}], rcx")
            elif i == 4:
                self.assembly.append(f"    mov [rbp - {offset}], r8")
            elif i == 5:
                self.assembly.append(f"    mov [rbp - {offset}], r9")
            else:
                stack_offset = 48 + (i - 6) * 8
                self.assembly.append(f"    mov rax, [rbp + {stack_offset}]")
                self.assembly.append(f"    mov [rbp - {offset}], rax")

        for stmt in fn.body:
            self.compile_stmt(stmt)

        self.assembly.append("    mov rsp, rbp")
        self.assembly.append("    pop rbp")
        self.assembly.append("    ret")

        self.local_vars = old_local_vars
        self.string_vars = old_string_vars

    def _emit_statement_line(self, node):
        if hasattr(node, 'line') and node.line > 0:
            self.assembly.append(f"    # line {node.line}")

    def _ensure_aligned(self):
        pass

    def compile_stmt(self, node):
        self._emit_statement_line(node)

        if isinstance(node, Assignment):
            self.compile_expr(node.value)
            self.assembly.append("    pop rax")
            offset = self.local_vars[node.name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov {offset}, rax")
            elif offset < 0:
                self.assembly.append(f"    mov [rbp + {-offset}], rax")
            else:
                self.assembly.append(f"    mov [rbp - {offset}], rax")
            if self._is_string_expr(node.value):
                self.string_vars.add(node.name)
        elif isinstance(node, DataFieldAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.instance)
            self.assembly.append("    pop rax")
            self.assembly.append("    pop rbx")
            offset = self.get_prop_offset(node.field_name)
            self.assembly.append(f"    mov [rax + {offset}], rbx")
        elif isinstance(node, Print):
            if self._is_file_expr(node.value):
                self.compile_expr(node.value)
                self.assembly.append("    pop rax")
                self.assembly.append("    mov rax, [rax + 8]")
                self.assembly.append("    push rax")
                self.assembly.append("    lea rdi, [rip + fmt_str]")
                self.assembly.append("    pop rsi")
                self.assembly.append("    xor eax, eax")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _printf")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    xor edi, edi")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _fflush")
                self.assembly.append("    add rsp, 32")
            else:
                self.compile_expr(node.value)
                if self._is_string_expr(node.value):
                    self.assembly.append("    lea rdi, [rip + fmt_str]")
                elif self._is_float_expr(node.value):
                    self.assembly.append("    lea rdi, [rip + fmt_float]")
                else:
                    self.assembly.append("    lea rdi, [rip + fmt_int]")
                self.assembly.append("    pop rsi")
                self.assembly.append("    xor eax, eax")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _printf")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    xor edi, edi")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _fflush")
                self.assembly.append("    add rsp, 32")
        elif isinstance(node, PrintD):
            if self.debug_mode == 1:
                self.assembly.append("    lea rdi, [rip + fmt_str]")
                self.assembly.append("    lea rsi, [rip + debug_prefix]")
                self.assembly.append("    xor eax, eax")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _printf")
                self.assembly.append("    add rsp, 32")
                self.assembly.append(f"    lea rdi, [rip + fmt_int_pure]")
                self.assembly.append(f"    mov esi, {node.line}")
                self.assembly.append("    xor eax, eax")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _printf")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    lea rdi, [rip + fmt_str]")
                self.assembly.append("    lea rsi, [rip + debug_suffix]")
                self.assembly.append("    xor eax, eax")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _printf")
                self.assembly.append("    add rsp, 32")
                self.compile_expr(node.value)
                if self._is_string_expr(node.value):
                    self.assembly.append("    lea rdi, [rip + fmt_str]")
                elif self._is_float_expr(node.value):
                    self.assembly.append("    lea rdi, [rip + fmt_float_pure]")
                else:
                    self.assembly.append("    lea rdi, [rip + fmt_int_pure]")
                self.assembly.append("    pop rsi")
                self.assembly.append("    xor eax, eax")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _printf")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    mov edi, 10")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _fputc")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    xor edi, edi")
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _fflush")
                self.assembly.append("    add rsp, 32")
        elif isinstance(node, Return):
            self.compile_expr(node.value)
            self.assembly.append("    pop rax")
            self.assembly.append("    mov rsp, rbp")
            self.assembly.append("    pop rbp")
            self.assembly.append("    ret")
        elif isinstance(node, IfElse):
            else_label = self.next_label("L_else")
            end_label = self.next_label("L_end")
            self.compile_expr(node.condition)
            self.assembly.append("    pop rax")
            self.assembly.append("    cmp eax, 0")
            self.assembly.append(f"    je {else_label}")
            for s in node.if_body:
                self.compile_stmt(s)
            self.assembly.append(f"    jmp {end_label}")
            self.assembly.append(f"{else_label}:")
            for s in node.else_body:
                self.compile_stmt(s)
            self.assembly.append(f"{end_label}:")
        elif isinstance(node, While):
            start_label = self.next_label("L_loop")
            end_label = self.next_label("L_loop_end")
            self.loop_labels.append((start_label, end_label))
            self.assembly.append(f"{start_label}:")
            self.compile_expr(node.condition)
            self.assembly.append("    pop rax")
            self.assembly.append("    cmp eax, 0")
            self.assembly.append(f"    je {end_label}")
            for s in node.body:
                self.compile_stmt(s)
            self.assembly.append(f"    jmp {start_label}")
            self.assembly.append(f"{end_label}:")
            self.loop_labels.pop()
        elif isinstance(node, ForLoop):
            start_val = node.start
            end_val = node.end
            step_val = node.step
            self.compile_expr(start_val)
            self.assembly.append("    pop rax")
            offset = self.local_vars[node.var_name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov {offset}, rax")
            else:
                self.assembly.append(f"    mov [rbp - {offset}], rax")
            loop_label = self.next_label("L_for")
            end_label = self.next_label("L_for_end")
            continue_label = self.next_label("L_for_cont")
            self.loop_labels.append((continue_label, end_label))
            self.assembly.append(f"{loop_label}:")
            if isinstance(offset, str):
                self.assembly.append(f"    mov rax, {offset}")
            else:
                self.assembly.append(f"    mov rax, [rbp - {offset}]")
            self.assembly.append("    push rax")
            self.compile_expr(end_val)
            self.assembly.append("    pop rbx")
            self.assembly.append("    pop rax")
            self.assembly.append("    cmp rax, rbx")
            if node.is_downto:
                self.assembly.append(f"    jl {end_label}")
            else:
                self.assembly.append(f"    jg {end_label}")
            for s in node.body:
                self.compile_stmt(s)
            self.assembly.append(f"{continue_label}:")
            self.compile_expr(step_val)
            self.assembly.append("    pop rax")
            if isinstance(offset, str):
                self.assembly.append(f"    add {offset}, rax")
            else:
                self.assembly.append(f"    add qword [rbp - {offset}], rax")
            self.assembly.append(f"    jmp {loop_label}")
            self.assembly.append(f"{end_label}:")
            self.loop_labels.pop()
        elif isinstance(node, ForIn):
            loop_label = self.next_label("L_forin")
            end_label = self.next_label("L_forin_end")
            self.loop_labels.append((loop_label, end_label))
            self.compile_expr(node.collection)
            self.assembly.append("    pop rdx")
            self.assembly.append(f"    mov eax, [rdx]")
            self.assembly.append("    push rax")
            self.assembly.append(f"    xor eax, eax")
            offset = self.local_vars[node.var_name]
            if isinstance(offset, str):
                pass
            else:
                self.assembly.append(f"    mov [rbp - {offset}], rax")
            self.assembly.append(f"{loop_label}:")
            if isinstance(offset, str):
                self.assembly.append(f"    mov eax, {offset}")
            else:
                self.assembly.append(f"    mov eax, [rbp - {offset}]")
            self.assembly.append("    pop rbx")
            self.assembly.append("    push rbx")
            self.assembly.append("    cmp eax, ebx")
            self.assembly.append(f"    jge {end_label}")
            self.assembly.append(f"    mov rax, [rdx + 8]")
            if isinstance(offset, str):
                self.assembly.append(f"    mov ecx, {offset}")
            else:
                self.assembly.append(f"    mov ecx, [rbp - {offset}]")
            self.assembly.append(f"    mov rax, [rax + rcx*8]")
            if isinstance(offset, str):
                pass
            else:
                self.assembly.append(f"    mov [rbp - 8], rax")
            self.assembly.append("    push rax")
            for s in node.body:
                self.compile_stmt(s)
            if isinstance(offset, str):
                self.assembly.append(f"    inc {offset}")
            else:
                self.assembly.append(f"    inc qword [rbp - {offset}]")
            self.assembly.append(f"    jmp {loop_label}")
            self.assembly.append(f"{end_label}:")
            self.assembly.append("    add rsp, 8")
            self.loop_labels.pop()
        elif isinstance(node, Break):
            if self.loop_labels:
                self.assembly.append(f"    jmp {self.loop_labels[-1][1]}")
        elif isinstance(node, Continue):
            if self.loop_labels:
                self.assembly.append(f"    jmp {self.loop_labels[-1][0]}")
        elif isinstance(node, Free):
            self.compile_expr(node.ptr)
            self.assembly.append("    pop rdi")
            self.assembly.append("    call _free")
        elif isinstance(node, PointerAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.ptr)
            self.assembly.append("    pop rbx")
            self.assembly.append("    pop rax")
            self.assembly.append("    mov [rbx], eax")
        elif isinstance(node, ArrayIndexAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    pop rbx")
            self.assembly.append("    pop rcx")
            self.assembly.append("    pop rax")
            self.assembly.append("    cmp ecx, 0")
            self.assembly.append("    jl _out_of_bounds")
            self.assembly.append("    cmp ecx, [rbx]")
            self.assembly.append("    jge _out_of_bounds")
            self.assembly.append("    mov rdi, [rbx + 8]")
            self.assembly.append("    mov [rdi + rcx*8], rax")
        elif isinstance(node, WriteFile):
            self.compile_expr(node.content)
            self.compile_expr(node.file)
            self.assembly.append("    pop rdi")
            self.assembly.append("    pop rsi")
            self.assembly.append("    mov rdx, -1")
            self.assembly.append("    call _fputs")
        elif isinstance(node, RawBlock):
            for line in node.body:
                if isinstance(line, str):
                    self.assembly.append(line)
                elif type(line).__name__ == "String":
                    self.assembly.append(line.value)
                else:
                    self.compile_stmt(line)
        elif isinstance(node, CloseFile):
            self.compile_expr(node.value)
            self.assembly.append("    pop rdi")
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _fclose")
            self.assembly.append("    add rsp, 32")
        else:
            self.compile_expr(node)
            self.assembly.append("    add rsp, 8")

    def compile_expr(self, node):
        if isinstance(node, Number):
            if isinstance(node.value, float):
                import struct
                bits = struct.unpack('<i', struct.pack('<f', node.value))[0]
                self.assembly.append(f"    push {bits}")
            else:
                if node.value < -2147483648 or node.value > 2147483647:
                    self.assembly.append(f"    mov rax, {node.value}")
                    self.assembly.append("    push rax")
                else:
                    self.assembly.append(f"    push {node.value}")
        elif isinstance(node, String):
            label = self.add_string_literal(node.value)
            self.assembly.append(f"    lea rax, [rip + {label}]")
            self.assembly.append("    push rax")
        elif isinstance(node, Boolean):
            val = 1 if node.value else 0
            self.assembly.append(f"    push {val}")
        elif isinstance(node, Variable):
            offset = self.local_vars[node.name]
            if isinstance(offset, str):
                self.assembly.append(f"    mov rax, {offset}")
            elif offset < 0:
                self.assembly.append(f"    mov rax, [rbp + {-offset}]")
            else:
                self.assembly.append(f"    mov rax, [rbp - {offset}]")
            self.assembly.append("    push rax")
        elif isinstance(node, BinOp):
            if node.op == "and":
                label_false = self.next_label("and_false")
                label_end = self.next_label("and_end")
                self.compile_expr(node.left)
                self.assembly.append("    pop rax")
                self.assembly.append("    cmp eax, 0")
                self.assembly.append(f"    je {label_false}")
                self.compile_expr(node.right)
                self.assembly.append("    pop rax")
                self.assembly.append("    cmp eax, 0")
                self.assembly.append(f"    je {label_false}")
                self.assembly.append("    push 1")
                self.assembly.append(f"    jmp {label_end}")
                self.assembly.append(f"{label_false}:")
                self.assembly.append("    push 0")
                self.assembly.append(f"{label_end}:")
                return
            elif node.op == "or":
                label_true = self.next_label("or_true")
                label_end = self.next_label("or_end")
                self.compile_expr(node.left)
                self.assembly.append("    pop rax")
                self.assembly.append("    cmp eax, 0")
                self.assembly.append(f"    jne {label_true}")
                self.compile_expr(node.right)
                self.assembly.append("    pop rax")
                self.assembly.append("    cmp eax, 0")
                self.assembly.append(f"    jne {label_true}")
                self.assembly.append("    push 0")
                self.assembly.append(f"    jmp {label_end}")
                self.assembly.append(f"{label_true}:")
                self.assembly.append("    push 1")
                self.assembly.append(f"{label_end}:")
                return

            left_leaf = self.is_leaf_expr(node.left)
            right_leaf = self.is_leaf_expr(node.right)
            all_leaf = left_leaf and right_leaf
            is_float_op = self._is_float_expr(node.left) or self._is_float_expr(node.right)
            if is_float_op:
                self.compile_expr(node.left)
                self.compile_expr(node.right)
                self.assembly.append("    movsd xmm0, [rsp + 8]")
                self.assembly.append("    movsd xmm1, [rsp]")
                if node.op == "+":
                    self.assembly.append("    addsd xmm0, xmm1")
                elif node.op == "-":
                    self.assembly.append("    subsd xmm0, xmm1")
                elif node.op == "*":
                    self.assembly.append("    mulsd xmm0, xmm1")
                elif node.op == "/":
                    self.assembly.append("    divsd xmm0, xmm1")
                else:
                    self.assembly.append("    addsd xmm0, xmm1")
                self.assembly.append("    add rsp, 16")
                self.assembly.append("    sub rsp, 8")
                self.assembly.append("    movsd [rsp], xmm0")
            elif all_leaf and node.op == "+" and (self._is_string_expr(node.left) or self._is_string_expr(node.right)):
                self.compile_expr(node.left)
                self.compile_expr(node.right)
                self.assembly.append("    pop rsi")
                self.assembly.append("    pop rdi")
                self.assembly.append("    push rsi")
                self.assembly.append("    push rdi")
                self._ensure_aligned()
                self.assembly.append("    call _concat_strings")
                self.assembly.append("    add rsp, 16")
                self.assembly.append("    push rax")
            elif all_leaf:
                self.compile_leaf_to_reg(node.right, 'ebx')
                self.compile_leaf_to_reg(node.left, 'eax')
                if node.op == "+":
                    self.assembly.append("    add eax, ebx")
                elif node.op == "-":
                    self.assembly.append("    sub eax, ebx")
                elif node.op == "*":
                    self.assembly.append("    imul eax, ebx")
                elif node.op == "/":
                    self.assembly.append("    cdq")
                    self.assembly.append("    idiv ebx")
                elif node.op == "%":
                    self.assembly.append("    cdq")
                    self.assembly.append("    idiv ebx")
                    self.assembly.append("    mov eax, edx")
                elif node.op == "&":
                    self.assembly.append("    and eax, ebx")
                elif node.op == "<<":
                    self.assembly.append("    mov ecx, ebx")
                    self.assembly.append("    shl eax, cl")
                elif node.op == ">>":
                    self.assembly.append("    mov ecx, ebx")
                    self.assembly.append("    sar eax, cl")
                self.assembly.append("    push rax")
            else:
                self.compile_expr(node.left)
                self.compile_expr(node.right)
                self.assembly.append("    pop rbx")
                self.assembly.append("    pop rax")
                if node.op == "+":
                    is_str = self._is_string_expr(node.left) or self._is_string_expr(node.right)
                    if is_str:
                        self.assembly.append("    push rbx")
                        self.assembly.append("    push rax")
                        self._ensure_aligned()
                        self.assembly.append("    call _concat_strings")
                        self.assembly.append("    add rsp, 16")
                    else:
                        self.assembly.append("    add eax, ebx")
                elif node.op == "-":
                    self.assembly.append("    sub eax, ebx")
                elif node.op == "*":
                    self.assembly.append("    imul eax, ebx")
                elif node.op == "/":
                    self.assembly.append("    cdq")
                    self.assembly.append("    idiv ebx")
                elif node.op == "%":
                    self.assembly.append("    cdq")
                    self.assembly.append("    idiv ebx")
                    self.assembly.append("    mov eax, edx")
                elif node.op == "&":
                    self.assembly.append("    and eax, ebx")
                elif node.op == "<<":
                    self.assembly.append("    mov ecx, ebx")
                    self.assembly.append("    shl eax, cl")
                elif node.op == ">>":
                    self.assembly.append("    mov ecx, ebx")
                    self.assembly.append("    sar eax, cl")
                self.assembly.append("    push rax")
        elif isinstance(node, UnaryOp):
            self.compile_expr(node.value)
            self.assembly.append("    pop rax")
            if node.op == "-":
                self.assembly.append("    neg eax")
            elif node.op == "not":
                self.assembly.append("    cmp eax, 0")
                self.assembly.append("    sete al")
                self.assembly.append("    movzx eax, al")
            self.assembly.append("    push rax")
        elif isinstance(node, Compare):
            left_leaf = self.is_leaf_expr(node.left)
            right_leaf = self.is_leaf_expr(node.right)
            all_leaf = left_leaf and right_leaf
            is_float_cmp = self._is_float_expr(node.left) or self._is_float_expr(node.right)

            if is_float_cmp:
                self.compile_expr(node.left)
                self.compile_expr(node.right)
                self.assembly.append("    movsd xmm0, [rsp]")
                self.assembly.append("    movsd xmm1, [rsp + 8]")
                self.assembly.append("    add rsp, 16")
                self.assembly.append("    comisd xmm0, xmm1")
                self.assembly.append("    pushf")
                self.assembly.append("    pop rax")
            elif all_leaf:
                self.compile_leaf_to_reg(node.right, 'rbx')
                self.compile_leaf_to_reg(node.left, 'rax')
            else:
                self.compile_expr(node.left)
                self.compile_expr(node.right)
                self.assembly.append("    pop rbx")
                self.assembly.append("    pop rax")

            left_type = getattr(node.left, 'inferred_type', 'any')
            right_type = getattr(node.right, 'inferred_type', 'any')
            left_is_str = self._is_string_expr(node.left) or str(left_type) == 'string'
            right_is_str = self._is_string_expr(node.right) or str(right_type) == 'string'
            is_str_cmp = False
            if left_is_str or right_is_str:
                left_is_zero = isinstance(node.left, Number) and node.left.value == 0
                right_is_zero = isinstance(node.right, Number) and node.right.value == 0
                if (left_is_str and right_is_zero) or (right_is_str and left_is_zero):
                    is_str_cmp = False
                else:
                    is_str_cmp = True

            if is_float_cmp:
                setcc_map = {"==": "sete", "!=": "setne", "<": "setb", ">": "seta", "<=": "setbe", ">=": "setae"}
                if node.op == "==":
                    self.assembly.append("    sete al")
                elif node.op == "!=":
                    self.assembly.append("    setne al")
                elif node.op == "<":
                    self.assembly.append("    setb al")
                elif node.op == ">":
                    self.assembly.append("    seta al")
                elif node.op == "<=":
                    self.assembly.append("    setbe al")
                elif node.op == ">=":
                    self.assembly.append("    setae al")
                else:
                    self.assembly.append("    sete al")
                self.assembly.append("    movzx eax, al")
                self.assembly.append("    push rax")
            elif is_str_cmp:
                self.assembly.append("    mov rdi, rax")
                self.assembly.append("    mov rsi, rbx")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _strcmp")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    cmp eax, 0")
                setcc_map = {"==": "sete", "!=": "setne", "<": "setl", ">": "setg", "<=": "setle", ">=": "setge"}
                cmp_op = setcc_map.get(node.op, "sete")
                self.assembly.append(f"    {cmp_op} al")
                self.assembly.append("    movzx eax, al")
                self.assembly.append("    push rax")
            else:
                setcc_map = {"==": "sete", "!=": "setne", "<": "setl", ">": "setg", "<=": "setle", ">=": "setge"}
                if node.op == "==":
                    self.assembly.append("    cmp eax, ebx")
                    self.assembly.append("    sete al")
                elif node.op == "!=":
                    self.assembly.append("    cmp eax, ebx")
                    self.assembly.append("    setne al")
                elif node.op == "<":
                    self.assembly.append("    cmp eax, ebx")
                    self.assembly.append("    setl al")
                elif node.op == ">":
                    self.assembly.append("    cmp eax, ebx")
                    self.assembly.append("    setg al")
                elif node.op == "<=":
                    self.assembly.append("    cmp eax, ebx")
                    self.assembly.append("    setle al")
                elif node.op == ">=":
                    self.assembly.append("    cmp eax, ebx")
                    self.assembly.append("    setge al")
                else:
                    self.assembly.append("    cmp eax, 0")
                    self.assembly.append("    sete al")
                self.assembly.append("    movzx eax, al")
                self.assembly.append("    push rax")
        elif isinstance(node, Call):
            if node.name in self.struct_defs:
                struct_size = (max(self.prop_offsets.values()) + 8) if self.prop_offsets else 128
                struct_size = max(struct_size, 16)
                struct_size = (struct_size + 15) & ~15
                self.assembly.append(f"    mov edi, {struct_size}")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _malloc")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    push rax")
            else:
                for arg in reversed(node.args):
                    self.compile_expr(arg)
                n_args = len(node.args)
                if n_args > 0:
                    self.assembly.append("    pop rdi")
                if n_args > 1:
                    self.assembly.append("    pop rsi")
                if n_args > 2:
                    self.assembly.append("    pop rdx")
                if n_args > 3:
                    self.assembly.append("    pop rcx")
                if n_args > 4:
                    self.assembly.append("    pop r8")
                if n_args > 5:
                    self.assembly.append("    pop r9")
                
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                if hasattr(node, 'module') and node.module:
                    module_prefix = node.module.replace(".", "_")
                    self.assembly.append(f"    call _{module_prefix}_{node.name}")
                else:
                    self.assembly.append(f"    call _{node.name}")
                self.assembly.append("    add rsp, 32")
                
                if n_args > 0:
                    pass
                self.assembly.append("    push rax")
        elif isinstance(node, DataFieldAccess):
            self.compile_expr(node.instance)
            self.assembly.append("    pop rax")
            offset = self.get_prop_offset(node.field_name)
            self.assembly.append(f"    mov rax, [rax + {offset}]")
            self.assembly.append("    push rax")
        elif isinstance(node, Alloc):
            self.compile_expr(node.size)
            self.assembly.append("    pop rdi")
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _malloc")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    push rax")
        elif isinstance(node, PointerProperty):
            self.compile_expr(node.ptr)
            if node.property == "value":
                self.assembly.append("    pop rdx")
                self.assembly.append("    mov eax, [rdx]")
                self.assembly.append("    push rax")
            elif node.property == "value_byte":
                self.assembly.append("    pop rdx")
                self.assembly.append("    xor eax, eax")
                self.assembly.append("    mov al, byte [rdx]")
                self.assembly.append("    push rax")
            elif node.property == "addr":
                pass
            else:
                raise Exception(f"[line {getattr(node, 'line', '?')}] Property {node.property} not supported in native codegen")
        elif isinstance(node, ArrayIndex):
            base_type = getattr(node.base, 'inferred_type', 'any')
            is_str = self._is_string_expr(node.base) or str(base_type) == 'string'
            if isinstance(node.base, DataFieldAccess) and node.base.field_name in ['struct_names', 'prop_names', 'local_var_names']:
                is_str = False
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    pop rdx")
            self.assembly.append("    pop rcx")
            if is_str:
                self.assembly.append("    movzx eax, byte ptr [rdx + rcx]")
                self.assembly.append("    shl eax, 1")
                self.assembly.append("    mov rcx, rax")
                self.assembly.append("    lea rax, [rip + char_strings]")
                self.assembly.append("    add rax, rcx")
                self.assembly.append("    push rax")
            else:
                self.assembly.append("    cmp ecx, 0")
                self.assembly.append("    jl _out_of_bounds")
                self.assembly.append("    cmp ecx, [rdx]")
                self.assembly.append("    jge _out_of_bounds")
                self.assembly.append("    mov rdi, [rdx + 8]")
                self.assembly.append("    mov rax, [rdi + rcx*8]")
                self.assembly.append("    push rax")
        elif isinstance(node, ApiRequest):
            self.compile_expr(node.url)
            self.assembly.append("    pop rdi")
            self.assembly.append("    call _api_open_internal")
            self.assembly.append("    push rax")
        elif isinstance(node, Openf):
            self.assembly.append("    mov edi, 24")
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _malloc")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    push rax")
            self.compile_expr(node.mode)
            self.assembly.append("    pop rdx")
            self.compile_expr(node.path)
            self.assembly.append("    pop rcx")
            self.assembly.append("    pop rax")
            self.assembly.append("    push rax")
            self.assembly.append("    mov [rax + 16], rcx")
            self.assembly.append("    mov rdi, rcx")
            self.assembly.append("    mov rsi, rdx")
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _fopen")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    pop rbx")
            self.assembly.append("    push rbx")
            self.assembly.append("    mov [rbx], eax")
            self.assembly.append("    push rbx")
        elif isinstance(node, OpenFile):
            self.compile_expr(node.path)
            self.assembly.append("    pop rdi")
            self.assembly.append("    lea rsi, [rip + str_fmode_a]")
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _fopen")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    push rax")
        elif isinstance(node, ReadFile):
            self.compile_expr(node.file)
            self.assembly.append("    pop rdi")
            self._ensure_aligned()
            self.assembly.append("    call _sys_read")
            self.assembly.append("    push rax")
        elif isinstance(node, ListLiteral):
            n = len(node.elements)
            req_cap = 16 if n == 0 else n * 8
            self.assembly.append("    mov edi, 16")
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _malloc")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    push rax") # push list struct
            self.assembly.append(f"    mov edi, {req_cap}")
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _malloc")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    pop rbx") # rbx = list struct
            self.assembly.append("    push rbx") # save list struct for expression result
            self.assembly.append(f"    mov dword ptr [rbx], {n}")
            self.assembly.append(f"    mov dword ptr [rbx + 4], {req_cap}")
            self.assembly.append("    mov [rbx + 8], rax") # rax is data buffer
            for i, elem in enumerate(node.elements):
                self.assembly.append("    push rbx")
                self.compile_expr(elem)
                self.assembly.append("    pop rax") # rax = elem
                self.assembly.append("    pop rbx") # rbx = list struct
                self.assembly.append("    mov rdx, [rbx + 8]") # rdx = data buffer
                self.assembly.append(f"    mov [rdx + {i*8}], rax")
            self.assembly.append("    pop rax")
            self.assembly.append("    push rax")
        elif isinstance(node, DictLiteral):
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _dict_new")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    push rax")
            for k, v in zip(node.keys, node.values):
                self.compile_expr(v)
                self.compile_expr(k)
                self.assembly.append("    pop rax")
                self.assembly.append("    pop rbx")
                self.assembly.append("    pop rcx")
                self.assembly.append("    push rcx")
                self.assembly.append("    mov rdi, rcx")
                self.assembly.append("    mov rsi, rax")
                self.assembly.append("    mov rdx, rbx")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _dict_set")
                self.assembly.append("    add rsp, 32")
        elif isinstance(node, MethodCall):
            if node.method_name == "append":
                self.compile_expr(node.args[0])
                self.compile_expr(node.instance)
                self.assembly.append("    pop rbx")
                self.assembly.append("    pop rcx")
                self.assembly.append("    mov eax, dword ptr [rbx]")
                self.assembly.append("    mov edx, eax")
                self.assembly.append("    add edx, 1")
                self.assembly.append("    shl edx, 3")
                self.assembly.append("    mov esi, dword ptr [rbx+4]")
                self.assembly.append("    cmp edx, esi")
                lbl = self.next_label("L_append_no_realloc")
                self.assembly.append(f"    jle {lbl}")
                self.assembly.append("    shl esi, 1")
                self.assembly.append("    push rcx")
                self.assembly.append("    push rsi")
                self.assembly.append("    mov rdi, [rbx + 8]")
                self.assembly.append("    mov rsi, rsi")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _realloc")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    pop rsi")
                self.assembly.append("    pop rcx")
                self.assembly.append("    mov [rbx + 8], rax")
                self.assembly.append("    mov dword ptr [rbx+4], esi")
                self.assembly.append(f"{lbl}:")
                self.assembly.append("    mov eax, dword ptr [rbx]")
                self.assembly.append("    mov rdi, [rbx + 8]")
                self.assembly.append("    mov [rdi + rax*8], rcx")
                self.assembly.append("    add eax, 1")
                self.assembly.append("    mov dword ptr [rbx], eax")
                self.assembly.append("    push rax")
            elif node.method_name == "pop":
                self.compile_expr(node.instance)
                self.assembly.append("    pop rbx")
                self.assembly.append("    mov ecx, [rbx]")
                self.assembly.append("    dec ecx")
                self.assembly.append("    mov [rbx], ecx")
                self.assembly.append("    mov rdi, [rbx + 8]")
                self.assembly.append("    mov rax, [rdi + rcx*8]")
                self.assembly.append("    push rax")
            elif node.method_name == "open" or node.method_name == "open_append":
                self.compile_expr(node.args[0])
                self.assembly.append("    pop rdi")
                mode_label = "str_fmode_w" if node.method_name == "open" else "str_fmode_a"
                self.assembly.append(f"    lea rsi, [rip + {mode_label}]")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _fopen")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    push rax")
            elif node.method_name == "read":
                self.compile_expr(node.instance)
                self.assembly.append("    pop rdi")
                self._ensure_aligned()
                self.assembly.append("    call _sys_read")
                self.assembly.append("    push rax")
            elif node.method_name == "write":
                self.compile_expr(node.args[0])
                self.compile_expr(node.instance)
                self.assembly.append("    pop rdi")
                self.assembly.append("    pop rsi")
                self._ensure_aligned()
                self.assembly.append("    call _fputs")
                self.assembly.append("    push rax")
            elif node.method_name == "close":
                self.compile_expr(node.instance)
                self.assembly.append("    pop rdi")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _fclose")
                self.assembly.append("    add rsp, 32")
            elif node.method_name == "flush":
                self.compile_expr(node.instance)
                self.assembly.append("    pop rdi")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _fflush")
                self.assembly.append("    add rsp, 32")
            elif node.method_name in ("get", "has", "set", "remove", "keys", "values", "items"):
                for arg in node.args:
                    self.compile_expr(arg)
                self.compile_expr(node.instance)
                self.assembly.append("    pop rdi")
                if len(node.args) >= 1:
                    self.assembly.append("    pop rsi")
                if len(node.args) >= 2:
                    self.assembly.append("    pop rdx")
                self._ensure_aligned()
                self.assembly.append(f"    call _dict_{node.method_name}")
                self.assembly.append("    push rax")
            else:
                call_node = Call(node.method_name, node.args)
                call_node.line = node.line
                self.compile_expr(call_node)
        elif isinstance(node, Len):
            if self._is_string_expr(node.target):
                self.compile_expr(node.target)
                self.assembly.append("    pop rdi")
                self._ensure_aligned()
                self.assembly.append("    sub rsp, 32")
                self.assembly.append("    call _strlen")
                self.assembly.append("    add rsp, 32")
                self.assembly.append("    push rax")
            else:
                self.compile_expr(node.target)
                self.assembly.append("    pop rax")
                self.assembly.append("    mov eax, [rax]")
                self.assembly.append("    push rax")
        elif isinstance(node, Slice):
            self.compile_expr(node.end)
            self.compile_expr(node.start)
            self.compile_expr(node.base)
            self.assembly.append("    pop rdi")
            self.assembly.append("    pop rsi")
            self.assembly.append("    pop rdx")
            self._ensure_aligned()
            self.assembly.append("    call _slice_string")
            self.assembly.append("    push rax")
        elif isinstance(node, StrConvert):
            self.compile_expr(node.target)
            self.assembly.append("    pop rdx")
            self.assembly.append("    push rdx")  # save value
            self.assembly.append("    mov edi, 32")
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _malloc")
            self.assembly.append("    mov rdi, rax")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    pop rdx")  # restore value
            self.assembly.append("    lea rsi, [rip + fmt_int_pure]")
            self.assembly.append("    push rdi")  # save buffer pointer
            self.assembly.append("    xor eax, eax")
            self._ensure_aligned()
            self.assembly.append("    sub rsp, 32")
            self.assembly.append("    call _sprintf")
            self.assembly.append("    add rsp, 32")
            self.assembly.append("    pop rax")  # restore buffer pointer
            self.assembly.append("    push rax")
        else:
            raise Exception(f"[line {getattr(node, 'line', '?')}] Unsupported expression: {type(node).__name__}")
