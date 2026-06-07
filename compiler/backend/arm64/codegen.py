import os
from nova_ast.nodes import *

class Arm64Codegen:
    """AArch64 (ARM64) codegen for Apple Silicon (macOS). Phase 1 features."""

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

    def next_label(self, prefix="L"):
        self.label_count += 1
        return f"{prefix}_{self.label_count}"

    def add_string_literal(self, value):
        if value not in self.string_literals:
            label = f"str_{self.str_count}"
            self.str_count += 1
            escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
            self.data_section.append(f'{label}: .asciz "{escaped}"')
            self.string_literals[value] = label
            return label
        return self.string_literals[value]

    def _is_string_expr(self, node):
        if isinstance(node, String): return True
        if getattr(node, 'inferred_type', None) == 'string': return True
        return False

    def generate(self):
        self.assembly.append(".text")
        self.assembly.append(".align 2")
        self.assembly.append(".global _main")

        self.assembly.append(".extern _printf")
        self.assembly.append(".extern _malloc")
        self.assembly.append(".extern _free")
        self.assembly.append(".extern _exit")

        self.data_section.append(".align 3")
        self.data_section.append('fmt_int: .asciz "%d\\n"')
        self.data_section.append('fmt_str: .asciz "%s\\n"')

        functions = [node for node in self.ast if isinstance(node, Function)]
        top_level = [node for node in self.ast if not isinstance(node, Function) and not isinstance(node, Import) and not isinstance(node, ClassDef) and not isinstance(node, Data)]

        for fn in functions:
            self.compile_function(fn)

        self.assembly.append("_main:")
        self.assembly.append("    stp fp, lr, [sp, #-16]!")
        self.assembly.append("    mov fp, sp")

        self.local_vars = {}
        self.local_offset = 0

        for node in top_level:
            self.scan_vars(node)

        if self.local_offset > 0:
            aligned = (self.local_offset + 15) & ~15
            self.assembly.append(f"    sub sp, sp, #{aligned}")

        for node in top_level:
            self.compile_stmt(node)

        self.assembly.append("    mov sp, fp")
        self.assembly.append("    ldp fp, lr, [sp], #16")
        self.assembly.append("    mov w0, #0")
        self.assembly.append("    ret")

        self.assembly.append(".data")
        self.assembly.append(".align 3")
        for line in self.data_section:
            self.assembly.append(line)

        return "\n".join(self.assembly)

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

    def compile_function(self, fn):
        self.assembly.append(f"_{fn.name}:")
        self.assembly.append("    stp fp, lr, [sp, #-16]!")
        self.assembly.append("    mov fp, sp")

        old_local_vars = self.local_vars.copy()
        self.local_vars = {}
        
        # Pre-allocate stack for arguments
        for i, param in enumerate(fn.params):
            param_name = param[0] if isinstance(param, (list, tuple)) else param
            self.local_offset += 8
            self.local_vars[param_name] = self.local_offset

        for stmt in fn.body:
            self.scan_vars(stmt)

        if self.local_offset > 0:
            aligned = (self.local_offset + 15) & ~15
            self.assembly.append(f"    sub sp, sp, #{aligned}")

        # Store arguments (passed in x0-x7) to local stack variables
        for i, param in enumerate(fn.params):
            if i < 8:
                param_name = param[0] if isinstance(param, (list, tuple)) else param
                offset = self.local_vars[param_name]
                self.assembly.append(f"    str x{i}, [fp, #{-offset}]")

        for stmt in fn.body:
            self.compile_stmt(stmt)

        self.assembly.append("    mov sp, fp")
        self.assembly.append("    ldp fp, lr, [sp], #16")
        self.assembly.append("    ret")

        self.local_vars = old_local_vars

    def compile_stmt(self, node):
        if isinstance(node, Assignment):
            self.compile_expr(node.value)
            self.assembly.append("    ldr x0, [sp], #16")
            offset = self.local_vars[node.name]
            self.assembly.append(f"    str x0, [fp, #{-offset}]")
        elif isinstance(node, Print):
            self.compile_expr(node.value)
            self.assembly.append("    ldr x1, [sp], #16")
            if self._is_string_expr(node.value):
                self.assembly.append("    adrp x0, fmt_str@PAGE")
                self.assembly.append("    add x0, x0, fmt_str@PAGEOFF")
            else:
                self.assembly.append("    adrp x0, fmt_int@PAGE")
                self.assembly.append("    add x0, x0, fmt_int@PAGEOFF")
            self.assembly.append("    bl _printf")
        elif isinstance(node, Return):
            self.compile_expr(node.value)
            self.assembly.append("    ldr x0, [sp], #16")
            self.assembly.append("    mov sp, fp")
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
        elif isinstance(node, RawBlock):
            for line in node.body:
                if isinstance(line, str): self.assembly.append(line)
                else: self.compile_stmt(line)
        else:
            self.compile_expr(node)
            self.assembly.append("    ldr x0, [sp], #16") # pop and discard

    def compile_expr(self, node):
        if isinstance(node, Number):
            val = int(node.value)
            if val < 0: val = (1 << 64) + val  # Two's complement for 64-bit
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
            self.assembly.append(f"    ldr x0, [fp, #{-offset}]")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, Call):
            for arg in node.args:
                self.compile_expr(arg)
            for i in reversed(range(len(node.args))):
                if i < 8:
                    self.assembly.append(f"    ldr x{i}, [sp], #16")
            self.assembly.append(f"    bl _{node.name}")
            self.assembly.append("    str x0, [sp, #-16]!")
        elif isinstance(node, BinOp):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.assembly.append("    ldr x1, [sp], #16")
            self.assembly.append("    ldr x0, [sp], #16")
            if node.op == "+":
                self.assembly.append("    add x0, x0, x1")
            elif node.op == "-":
                self.assembly.append("    sub x0, x0, x1")
            elif node.op == "*":
                self.assembly.append("    mul x0, x0, x1")
            elif node.op == "/":
                self.assembly.append("    sdiv x0, x0, x1")
            elif node.op == "==":
                self.assembly.append("    cmp x0, x1")
                self.assembly.append("    cset x0, eq")
            elif node.op == "!=":
                self.assembly.append("    cmp x0, x1")
                self.assembly.append("    cset x0, ne")
            elif node.op == "<":
                self.assembly.append("    cmp x0, x1")
                self.assembly.append("    cset x0, lt")
            elif node.op == ">":
                self.assembly.append("    cmp x0, x1")
                self.assembly.append("    cset x0, gt")
            elif node.op == "<=":
                self.assembly.append("    cmp x0, x1")
                self.assembly.append("    cset x0, le")
            elif node.op == ">=":
                self.assembly.append("    cmp x0, x1")
                self.assembly.append("    cset x0, ge")
            self.assembly.append("    str x0, [sp, #-16]!")
