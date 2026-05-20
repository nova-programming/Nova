import os
from ast.nodes import *

class X86Codegen:
    def __init__(self, ast_nodes):
        self.ast = ast_nodes
        self.assembly = []
        self.data_section = []
        self.string_literals = {} # string_value -> label_name
        self.str_count = 0
        self.label_count = 0
        self.local_vars = {} # var_name -> stack_offset
        self.local_offset = 0
        self.loop_labels = [] # stack of (start_label, end_label)

    def next_label(self, prefix="L"):
        self.label_count += 1
        return f"{prefix}_{self.label_count}"

    def _is_string_expr(self, node):
        """Check if an expression evaluates to a string at compile time."""
        if isinstance(node, String):
            return True
        if isinstance(node, Variable):
            string_vars = getattr(self, 'string_vars', set())
            return node.name in string_vars
        return False

    def add_string_literal(self, value):
        if value in self.string_literals:
            return self.string_literals[value]
        self.str_count += 1
        label = f"str_const_{self.str_count}"
        self.string_literals[value] = label
        # Escaping quotes and newlines for assembly
        escaped = value.replace('"', '\\"')
        self.data_section.append(f'{label}: .asciz "{escaped}"')
        return label

    def generate(self):
        # Initial headers
        self.assembly.append(".intel_syntax noprefix")
        self.assembly.append(".global _main")
        self.assembly.append(".extern _printf")
        self.assembly.append(".extern _malloc")
        self.assembly.append(".extern _free")
        self.assembly.append(".extern _puts")
        self.assembly.append(".extern _fopen")
        self.assembly.append(".extern _fread")
        self.assembly.append(".extern _fputs")
        self.assembly.append(".extern _fclose")
        
        # We also need format strings for printing
        self.data_section.append('fmt_int: .asciz "%d\\n"')
        self.data_section.append('fmt_str: .asciz "%s\\n"')

        # Compile functions and top-level code
        # We compile top-level statements inside a "_main" wrapper
        
        self.assembly.append(".text")
        
        # Split functions from top-level code
        functions = [node for node in self.ast if isinstance(node, Function)]
        top_level = [node for node in self.ast if not isinstance(node, Function) and not isinstance(node, Import) and not isinstance(node, ClassDef) and not isinstance(node, Data)]
        
        # Compile functions first
        for fn in functions:
            self.compile_function(fn)
            
        # Compile main entry point
        self.assembly.append("_main:")
        self.assembly.append("    push ebp")
        self.assembly.append("    mov ebp, esp")
        
        # Scan top-level code for variables to allocate local space
        self.local_vars = {}
        self.local_offset = 0
        for node in top_level:
            self.scan_vars(node)
            
        if self.local_offset > 0:
            self.assembly.append(f"    sub esp, {self.local_offset}")
            
        for node in top_level:
            self.compile_stmt(node)
            
        self.assembly.append("    mov esp, ebp")
        self.assembly.append("    pop ebp")
        self.assembly.append("    mov eax, 0")
        self.assembly.append("    ret")
        
        # Append data section
        self.assembly.append(".data")
        for line in self.data_section:
            self.assembly.append(line)
            
        return "\n".join(self.assembly)

    def scan_vars(self, node):
        """Pre-scan statements for assignments to reserve stack space for local variables"""
        if isinstance(node, Assignment):
            if node.name not in self.local_vars:
                self.local_offset += 4
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
                self.local_offset += 4
                self.local_vars[node.var_name] = self.local_offset
            for s in node.body:
                self.scan_vars(s)

    def compile_function(self, fn):
        self.assembly.append(f"_{fn.name}:")
        self.assembly.append("    push ebp")
        self.assembly.append("    mov ebp, esp")
        
        # Save function arguments in local_vars map
        # Under cdecl: ebp + 8 is 1st arg, ebp + 12 is 2nd, etc.
        old_local_vars = self.local_vars.copy()
        self.local_vars = {}
        for i, param in enumerate(fn.params):
            param_name = param[0] if isinstance(param, (list, tuple)) else param
            # Argument offset from ebp: ebp + 8 + i * 4
            self.local_vars[param_name] = -(8 + i * 4) # Negative offset to represent arguments
            
        # Scan function body for local variables
        self.local_offset = 0
        for stmt in fn.body:
            self.scan_vars(stmt)
            
        if self.local_offset > 0:
            self.assembly.append(f"    sub esp, {self.local_offset}")
            
        for stmt in fn.body:
            self.compile_stmt(stmt)
            
        # Epilogue
        self.assembly.append("    mov esp, ebp")
        self.assembly.append("    pop ebp")
        self.assembly.append("    ret")
        
        self.local_vars = old_local_vars

    def compile_stmt(self, node):
        if isinstance(node, Assignment):
            self.compile_expr(node.value)
            self.assembly.append("    pop eax")
            offset = self.local_vars[node.name]
            self.assembly.append(f"    mov [ebp - {offset}], eax")
            # Track if this variable holds a string
            if isinstance(node.value, String):
                self.string_vars = getattr(self, 'string_vars', set())
                self.string_vars.add(node.name)
        elif isinstance(node, Print):
            self.compile_expr(node.value)
            # Check type of target (we default to int printing unless it's a string)
            if self._is_string_expr(node.value):
                self.assembly.append("    push offset fmt_str")
                self.assembly.append("    call _printf")
                self.assembly.append("    add esp, 8")
            else:
                self.assembly.append("    push offset fmt_int")
                self.assembly.append("    call _printf")
                self.assembly.append("    add esp, 8")
        elif isinstance(node, Return):
            self.compile_expr(node.value)
            self.assembly.append("    pop eax")
            self.assembly.append("    mov esp, ebp")
            self.assembly.append("    pop ebp")
            self.assembly.append("    ret")
        elif isinstance(node, IfElse):
            else_label = self.next_label("L_else")
            end_label = self.next_label("L_end")
            
            self.compile_expr(node.condition)
            self.assembly.append("    pop eax")
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
            self.assembly.append("    pop eax")
            self.assembly.append("    cmp eax, 0")
            self.assembly.append(f"    je {end_label}")
            
            for s in node.body:
                self.compile_stmt(s)
                
            self.assembly.append(f"    jmp {start_label}")
            self.assembly.append(f"{end_label}:")
            self.loop_labels.pop()
        elif isinstance(node, ForLoop):
            # For loop translates to:
            # var = start
            # L_loop:
            # if var > end (or < end if downto): jmp L_loop_end
            # body...
            # var = var + step
            # jmp L_loop
            start_val = node.start
            end_val = node.end
            step_val = node.step
            
            # Assignment: var = start
            self.compile_expr(start_val)
            self.assembly.append("    pop eax")
            offset = self.local_vars[node.var_name]
            self.assembly.append(f"    mov [ebp - {offset}], eax")
            
            loop_label = self.next_label("L_for")
            end_label = self.next_label("L_for_end")
            continue_label = self.next_label("L_for_cont")
            self.loop_labels.append((continue_label, end_label))
            
            self.assembly.append(f"{loop_label}:")
            # Load var
            self.assembly.append(f"    mov eax, [ebp - {offset}]")
            self.assembly.append("    push eax")
            # Evaluate end
            self.compile_expr(end_val)
            self.assembly.append("    pop ebx") # end
            self.assembly.append("    pop eax") # var
            self.assembly.append("    cmp eax, ebx")
            if node.is_downto:
                self.assembly.append(f"    jl {end_label}") # if var < end, terminate
            else:
                self.assembly.append(f"    jg {end_label}") # if var > end, terminate
                
            # Loop body
            for s in node.body:
                self.compile_stmt(s)
                
            # Increment/Decrement step
            self.assembly.append(f"{continue_label}:")
            self.assembly.append(f"    mov eax, [ebp - {offset}]")
            self.compile_expr(step_val)
            self.assembly.append("    pop ebx")
            if node.is_downto:
                self.assembly.append("    sub eax, ebx")
            else:
                self.assembly.append("    add eax, ebx")
            self.assembly.append(f"    mov [ebp - {offset}], eax")
            
            self.assembly.append(f"    jmp {loop_label}")
            self.assembly.append(f"{end_label}:")
            self.loop_labels.pop()
        elif isinstance(node, Break):
            if self.loop_labels:
                self.assembly.append(f"    jmp {self.loop_labels[-1][1]}")
        elif isinstance(node, Continue):
            if self.loop_labels:
                self.assembly.append(f"    jmp {self.loop_labels[-1][0]}")
        elif isinstance(node, Free):
            self.compile_expr(node.ptr)
            self.assembly.append("    call _free")
            self.assembly.append("    add esp, 4")
        elif isinstance(node, PointerAssign):
            # Assign value to *ptr (dereference write)
            self.compile_expr(node.value)
            self.compile_expr(node.ptr)
            self.assembly.append("    pop edx") # address
            self.assembly.append("    pop eax") # value
            self.assembly.append("    mov [edx], eax")
        elif isinstance(node, ArrayIndexAssign):
            # base[index] = value
            self.compile_expr(node.value)
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    pop edx") # base address
            self.assembly.append("    pop ecx") # index
            self.assembly.append("    pop eax") # value
            # Store 32-bit int: base + index * 4
            self.assembly.append("    mov [edx + ecx * 4], eax")
        elif isinstance(node, WriteFile):
            self.compile_expr(node.content)
            self.compile_expr(node.fd)
            self.assembly.append("    pop ecx") # fd
            self.assembly.append("    pop eax") # content string pointer
            self.assembly.append("    push ecx") # stream (2nd arg)
            self.assembly.append("    push eax") # str (1st arg)
            self.assembly.append("    call _fputs")
            self.assembly.append("    add esp, 8")
        elif isinstance(node, CloseFile):
            self.compile_expr(node.fd)
            self.assembly.append("    call _fclose")
            self.assembly.append("    add esp, 4")
        else:
            # Might be an expression statement (e.g. function call)
            self.compile_expr(node)
            # Pop unused result if expression statement pushed one
            # Call nodes push a return value, so pop it
            if isinstance(node, Call) or isinstance(node, MethodCall):
                self.assembly.append("    pop eax")

    def compile_expr(self, node):
        if isinstance(node, Number):
            # Check if float or int (for simplicity, cast floats to ints or just load as ints)
            val = int(float(node.value))
            self.assembly.append(f"    push {val}")
        elif isinstance(node, String):
            label = self.add_string_literal(node.value)
            self.assembly.append(f"    push offset {label}")
        elif isinstance(node, Boolean):
            val = 1 if node.value else 0
            self.assembly.append(f"    push {val}")
        elif isinstance(node, Variable):
            offset = self.local_vars[node.name]
            if offset < 0:
                # Argument: ebp - offset (offset is negative, e.g. -8)
                self.assembly.append(f"    mov eax, [ebp + {-offset}]")
            else:
                self.assembly.append(f"    mov eax, [ebp - {offset}]")
            self.assembly.append("    push eax")
        elif isinstance(node, BinOp):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.assembly.append("    pop ebx") # right
            self.assembly.append("    pop eax") # left
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
            elif node.op == "and":
                self.assembly.append("    and eax, ebx")
            elif node.op == "or":
                self.assembly.append("    or eax, ebx")
            self.assembly.append("    push eax")
        elif isinstance(node, UnaryOp):
            self.compile_expr(node.value)
            self.assembly.append("    pop eax")
            if node.op == "-":
                self.assembly.append("    neg eax")
            elif node.op == "not":
                self.assembly.append("    cmp eax, 0")
                self.assembly.append("    sete al")
                self.assembly.append("    movzx eax, al")
            self.assembly.append("    push eax")
        elif isinstance(node, Compare):
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            self.assembly.append("    pop ebx") # right
            self.assembly.append("    pop eax") # left
            self.assembly.append("    cmp eax, ebx")
            
            label_true = self.next_label("L_cmp_true")
            label_end = self.next_label("L_cmp_end")
            
            if node.op == "==":
                self.assembly.append(f"    je {label_true}")
            elif node.op == "!=":
                self.assembly.append(f"    jne {label_true}")
            elif node.op == "<":
                self.assembly.append(f"    jl {label_true}")
            elif node.op == "<=":
                self.assembly.append(f"    jle {label_true}")
            elif node.op == ">":
                self.assembly.append(f"    jg {label_true}")
            elif node.op == ">=":
                self.assembly.append(f"    jge {label_true}")
                
            self.assembly.append("    push 0")
            self.assembly.append(f"    jmp {label_end}")
            self.assembly.append(f"{label_true}:")
            self.assembly.append("    push 1")
            self.assembly.append(f"{label_end}:")
        elif isinstance(node, Call):
            # Push arguments in reverse order (right-to-left)
            for arg in reversed(node.args):
                self.compile_expr(arg)
            self.assembly.append(f"    call _{node.name}")
            # Clean up stack after call
            if len(node.args) > 0:
                self.assembly.append(f"    add esp, {len(node.args) * 4}")
            self.assembly.append("    push eax")
        elif isinstance(node, Alloc):
            self.compile_expr(node.size)
            self.assembly.append("    call _malloc")
            self.assembly.append("    add esp, 4")
            self.assembly.append("    push eax")
        elif isinstance(node, PointerProperty):
            self.compile_expr(node.ptr)
            if node.property == "value":
                self.assembly.append("    pop edx") # address
                self.assembly.append("    mov eax, [edx]") # dereference
                self.assembly.append("    push eax")
            elif node.property == "addr":
                pass # already top of stack
            else:
                raise Exception(f"Property {node.property} not supported in native codegen")
        elif isinstance(node, ArrayIndex):
            # base[index]
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    pop edx") # base address
            self.assembly.append("    pop ecx") # index
            self.assembly.append("    mov eax, [edx + ecx * 4]")
            self.assembly.append("    push eax")
        elif isinstance(node, OpenFile):
            self.compile_expr(node.mode)
            self.compile_expr(node.path)
            self.assembly.append("    call _fopen")
            self.assembly.append("    add esp, 8")
            self.assembly.append("    push eax")
        elif isinstance(node, ReadFile):
            self.compile_expr(node.fd)
            self.assembly.append("    pop ecx") # ecx = fd
            # Allocate 65536 bytes
            self.assembly.append("    push ecx") # save fd
            self.assembly.append("    push 65536")
            self.assembly.append("    call _malloc")
            self.assembly.append("    add esp, 4")
            self.assembly.append("    pop ecx") # restore fd
            
            # Now eax = buffer pointer. Save it.
            self.assembly.append("    push eax") # save buffer pointer to return later
            
            # Call fread(buffer, 1, 65535, fd)
            self.assembly.append("    push ecx") # fd
            self.assembly.append("    push 65535") # count
            self.assembly.append("    push 1") # size
            self.assembly.append("    push eax") # buffer
            self.assembly.append("    call _fread")
            self.assembly.append("    add esp, 16")
            
            # eax now contains bytes read.
            # Null-terminate buffer: buffer[bytes_read] = 0
            self.assembly.append("    pop ebx") # restore buffer pointer
            self.assembly.append("    mov byte ptr [ebx + eax], 0")
            self.assembly.append("    push ebx") # push buffer pointer as result
        else:
            raise Exception(f"Native codegen unhandled node: {type(node)}")
