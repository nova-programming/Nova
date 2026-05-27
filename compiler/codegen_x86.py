import os
from ast.nodes import *

class X86Codegen:
    def __init__(self, ast_nodes, module_names=None):
        self.ast = ast_nodes
        self.module_names = module_names or []
        self.assembly = []
        self.data_section = []
        self.string_literals = {} # string_value -> label_name
        self.str_count = 0
        self.label_count = 0
        self.local_vars = {} # var_name -> stack_offset
        self.local_offset = 0
        self.loop_labels = [] # stack of (start_label, end_label)
        self.prop_offsets = {}
        self.structs = set()

    def get_prop_offset(self, name):
        if name not in self.prop_offsets:
            self.prop_offsets[name] = len(self.prop_offsets) * 4
        return self.prop_offsets[name]

    def next_label(self, prefix="L"):
        self.label_count += 1
        return f"{prefix}_{self.label_count}"

    def _is_string_expr(self, node):
        """Check if an expression evaluates to a string at compile time."""
        if isinstance(node, String):
            return True
        # Check inferred_type from the type checker
        inferred = getattr(node, 'inferred_type', None)
        if inferred == 'string':
            return True
        if isinstance(node, Variable):
            string_vars = getattr(self, 'string_vars', set())
            if node.name in string_vars: return True
            if node.name in ["path", "file", "cmd", "line", "token", "source", "out_path", "file_path", "out_file", "arg_str"]: return True
            return False
        if isinstance(node, BinOp) and node.op == '+':
            return self._is_string_expr(node.left) or self._is_string_expr(node.right)
        if isinstance(node, Call):
            # Check if function returns string based on pre-populated func_returns
            if hasattr(self, 'func_returns') and node.name in self.func_returns:
                return self.func_returns[node.name] == 'string'
            # Also hardcode some stdlib functions if not found
            if node.name in ['str', 'trim', 'str_sub', '_sys_extract_arg', 'sys_read', 'sys_platform']:
                return True
            return False  # Can't determine statically
        if isinstance(node, ArrayIndex):
            return self._is_string_expr(node.base)
        if isinstance(node, DataFieldAccess):
            # Trust struct_defs over hardcoded lists if available
            if hasattr(self, 'struct_defs') and self.struct_defs:
                for struct_def in self.struct_defs.values():
                    for field in struct_def.fields:
                        if field[0] == node.field_name and field[1] == 'string':
                            return True
            else:
                if node.field_name in ['val_str', 'kind', 'name', 'directive', 'label', 'mnemonic', 'dir_arg', 'raw', 'target', 'val', 'cond', 'field_name']:
                    return True
        if isinstance(node, StrConvert):
            return True
        if isinstance(node, Slice):
            return self._is_string_expr(node.base)
        return False

    def add_string_literal(self, value):
        if value in self.string_literals:
            return self.string_literals[value]
        self.str_count += 1
        label = f"str_const_{self.str_count}"
        self.string_literals[value] = label
        # Escape special characters for GAS .asciz directives
        escaped = value.replace('\\', '\\\\')
        escaped = escaped.replace('"', '\\"')
        escaped = escaped.replace('\n', '\\n')
        escaped = escaped.replace('\r', '\\r')
        escaped = escaped.replace('\t', '\\t')
        self.data_section.append(f'{label}: .asciz "{escaped}"')
        return label

    def generate(self):
        # Initial headers
        self.assembly.append(".intel_syntax noprefix")
        self.assembly.append(".global _main")
        # Win32 API externs (replaces MSVCRT)
        self.assembly.append(".extern _GetProcessHeap@0")
        self.assembly.append(".extern _HeapAlloc@12")
        self.assembly.append(".extern _HeapFree@12")
        self.assembly.append(".extern _HeapReAlloc@16")
        self.assembly.append(".extern _GetStdHandle@4")
        self.assembly.append(".extern _WriteFile@20")
        self.assembly.append(".extern _ReadFile@20")
        self.assembly.append(".extern _CreateFileA@28")
        self.assembly.append(".extern _CloseHandle@4")
        self.assembly.append(".extern _SetFilePointer@16")
        self.assembly.append(".extern _FlushFileBuffers@4")
        self.assembly.append(".extern _ExitProcess@4")
        self.assembly.append(".extern _WinExec@8")
        
        # We also need format strings for printing
        self.data_section.append('fmt_int: .asciz "%d\\n"')
        self.data_section.append('fmt_int_pure: .asciz "%d"')
        self.data_section.append('fmt_str: .asciz "%s\\n"')
        self.data_section.append('L_realloc_fail_msg: .asciz "Realloc failed!\\n"')
        
        self.data_section.append("char_strings:")
        for i in range(256):
            self.data_section.append(f"    .byte {i}")
            self.data_section.append(f"    .byte 0")

        # Split functions from top-level code
        functions = [node for node in self.ast if isinstance(node, Function)]
        top_level = [node for node in self.ast if not isinstance(node, Function) and not isinstance(node, Import) and not isinstance(node, ClassDef) and not isinstance(node, Data)]
        
        for n in self.ast:
            if isinstance(n, Data) or isinstance(n, ClassDef):
                self.structs.add(n.name)
        
        # Pre-populate prop_offsets from all struct field definitions
        # so we know the total struct size before generating code
        self.struct_defs = {}
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
        
        # Compile functions first
        for fn in functions:
            self.compile_function(fn)
            
        # Compile main entry point
        self.assembly.append("_main:")
        self.assembly.append("    push ebp")
        self.assembly.append("    mov ebp, esp")
        self.assembly.append("    and esp, -16")
        
        # Scan top-level code for variables to allocate local space
        self.local_vars = {}
        self.local_offset = 0
        
        # Reserve slots for __argc and __argv from C runtime
        self.local_offset += 4
        self.local_vars["__argc"] = self.local_offset
        self.local_offset += 4
        self.local_vars["__argv"] = self.local_offset
        
        for node in top_level:
            self.scan_vars(node)
            
        if self.local_offset > 0:
            self.assembly.append(f"    sub esp, {self.local_offset}")
        
        # Store argc/argv from cdecl convention
        self.assembly.append("    mov eax, [ebp + 8]")  # argc
        self.assembly.append(f"    mov [ebp - {self.local_vars['__argc']}], eax")
        self.assembly.append("    mov eax, [ebp + 12]") # argv
        self.assembly.append(f"    mov [ebp - {self.local_vars['__argv']}], eax")
            
        for node in top_level:
            self.compile_stmt(node)
            
        self.assembly.append("    mov esp, ebp")
        self.assembly.append("    pop ebp")
        self.assembly.append("    mov eax, 0")
        self.assembly.append("    ret")

        # Generic String Concat Helper
        self.assembly.append("_concat_strings:")
        self.assembly.append("    push ebp")
        self.assembly.append("    mov ebp, esp")
        self.assembly.append("    push dword ptr [ebp+8]") # left
        self.assembly.append("    call _strlen")
        self.assembly.append("    add esp, 4")
        self.assembly.append("    mov ebx, eax") # len_a
        self.assembly.append("    push dword ptr [ebp+12]") # right
        self.assembly.append("    call _strlen")
        self.assembly.append("    add esp, 4")
        self.assembly.append("    add ebx, eax") # len_a + len_b
        self.assembly.append("    inc ebx") # +1 for null
        self.assembly.append("    push ebx")
        self.assembly.append("    call _malloc")
        self.assembly.append("    add esp, 4")
        self.assembly.append("    push eax") # save dest
        self.assembly.append("    push dword ptr [ebp+8]")
        self.assembly.append("    push eax")
        self.assembly.append("    call _strcpy")
        self.assembly.append("    add esp, 8")
        self.assembly.append("    pop eax")
        self.assembly.append("    push eax")
        self.assembly.append("    push dword ptr [ebp+12]")
        self.assembly.append("    push eax")
        self.assembly.append("    call _strcat")
        self.assembly.append("    add esp, 8")
        self.assembly.append("    pop eax")
        self.assembly.append("    pop ebp")
        self.assembly.append("    ret")
        
        # String slice helper: _slice_string(base, start, end) -> new string
        self.assembly.append("_slice_string:")
        self.assembly.append("    push ebp")
        self.assembly.append("    mov ebp, esp")
        self.assembly.append("    push esi")
        self.assembly.append("    push edi")
        self.assembly.append("    push ebx")
        self.assembly.append("    mov esi, [ebp+8]")  # base (esi is callee-saved)
        self.assembly.append("    mov ebx, [ebp+12]") # start
        self.assembly.append("    mov ecx, [ebp+16]") # end
        self.assembly.append("    sub ecx, ebx")       # len = end - start
        self.assembly.append("    cmp ecx, 0")
        self.assembly.append("    jge L_slice_alloc")
        self.assembly.append("    mov ecx, 0")
        self.assembly.append("L_slice_alloc:")
        self.assembly.append("    push ecx")           # save len
        self.assembly.append("    inc ecx")
        self.assembly.append("    push ecx")
        self.assembly.append("    call _malloc")
        self.assembly.append("    add esp, 4")
        self.assembly.append("    pop ecx")            # ecx = len
        self.assembly.append("    mov edi, eax")       # edi = dest
        self.assembly.append("    add esi, ebx")       # esi = base + start
        # Manual byte copy
        self.assembly.append("    push edi")           # save dest
        self.assembly.append("    push ecx")           # save len
        self.assembly.append("    cmp ecx, 0")
        self.assembly.append("    jle L_slice_done")
        self.assembly.append("L_slice_copy:")
        self.assembly.append("    mov al, [esi]")
        self.assembly.append("    mov [edi], al")
        self.assembly.append("    inc esi")
        self.assembly.append("    inc edi")
        self.assembly.append("    dec ecx")
        self.assembly.append("    cmp ecx, 0")
        self.assembly.append("    jg L_slice_copy")
        self.assembly.append("L_slice_done:")
        self.assembly.append("    pop ecx")            # ecx = len
        self.assembly.append("    pop edi")            # edi = original dest
        self.assembly.append("    mov byte ptr [edi + ecx], 0")  # null term
        self.assembly.append("    mov eax, edi")
        self.assembly.append("    pop ebx")
        self.assembly.append("    pop edi")
        self.assembly.append("    pop esi")
        self.assembly.append("    pop ebp")
        self.assembly.append("    ret")
        
        # Win32 API runtime functions (replaces MSVCRT)
        self._emit_win32_runtime()
        
        # Append data section
        self.assembly.append(".data")
        for line in self.data_section:
            self.assembly.append(line)
            
        return "\n".join(self.assembly)

    def _emit_win32_runtime(self):
        """Emit Win32 API replacement functions for MSVCRT runtime."""
        r = self.assembly.append
        # Memory: malloc/free/realloc via Heap API
        r("_malloc:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push dword ptr [ebp + 8]")
        r("    push 0")
        r("    call _GetProcessHeap@0")
        r("    push eax")
        r("    call _HeapAlloc@12")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_free:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push dword ptr [ebp + 8]")
        r("    push 0")
        r("    call _GetProcessHeap@0")
        r("    push eax")
        r("    call _HeapFree@12")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_realloc:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push dword ptr [ebp + 12]")
        r("    push dword ptr [ebp + 8]")
        r("    push 8")
        r("    call _GetProcessHeap@0")
        r("    push eax")
        r("    call _HeapReAlloc@16")
        r("    pop ebp")
        r("    ret")
        r("")
        # String functions
        r("_strlen:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push edi")
        r("    push ecx")
        r("    mov edi, [ebp + 8]")
        r("    mov ecx, -1")
        r("    xor eax, eax")
        r("    repnz scasb")
        r("    not ecx")
        r("    lea eax, [ecx - 1]")
        r("    pop ecx")
        r("    pop edi")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_strcmp:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push esi")
        r("    push edi")
        r("    mov esi, [ebp + 8]")
        r("    mov edi, [ebp + 12]")
        r("L_strcmp_loop:")
        r("    mov al, [esi]")
        r("    cmp al, [edi]")
        r("    jne L_strcmp_diff")
        r("    test al, al")
        r("    jz L_strcmp_eq")
        r("    inc esi")
        r("    inc edi")
        r("    jmp L_strcmp_loop")
        r("L_strcmp_diff:")
        r("    mov al, [esi]")
        r("    sub al, [edi]")
        r("    movsx eax, al")
        r("    pop edi")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("L_strcmp_eq:")
        r("    xor eax, eax")
        r("    pop edi")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_strcpy:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push esi")
        r("    push edi")
        r("    mov esi, [ebp + 12]")
        r("    mov edi, [ebp + 8]")
        r("L_strcpy_loop:")
        r("    mov al, [esi]")
        r("    mov [edi], al")
        r("    test al, al")
        r("    jz L_strcpy_done")
        r("    inc esi")
        r("    inc edi")
        r("    jmp L_strcpy_loop")
        r("L_strcpy_done:")
        r("    mov eax, [ebp + 8]")
        r("    pop edi")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_strcat:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push edi")
        r("    push esi")
        r("    mov edi, [ebp + 8]")
        r("    xor eax, eax")
        r("    mov ecx, -1")
        r("    repnz scasb")
        r("    dec edi")
        r("    mov esi, [ebp + 12]")
        r("L_strcat_loop:")
        r("    mov al, [esi]")
        r("    mov [edi], al")
        r("    test al, al")
        r("    jz L_strcat_done")
        r("    inc esi")
        r("    inc edi")
        r("    jmp L_strcat_loop")
        r("L_strcat_done:")
        r("    mov eax, [ebp + 8]")
        r("    pop esi")
        r("    pop edi")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_strstr:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push esi")
        r("    push edi")
        r("    mov esi, [ebp + 8]")
        r("    mov edx, [ebp + 12]")
        r("    cmp byte ptr [edx], 0")
        r("    jne L_strstr_outer")
        r("    mov eax, [ebp + 8]")
        r("    pop edi")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("L_strstr_outer:")
        r("    cmp byte ptr [esi], 0")
        r("    je L_strstr_nf")
        r("    mov ecx, esi")
        r("    mov edi, edx")
        r("L_strstr_inner:")
        r("    mov al, [edi]")
        r("    cmp al, [esi]")
        r("    jne L_strstr_next")
        r("    test al, al")
        r("    je L_strstr_found")
        r("    inc esi")
        r("    inc edi")
        r("    jmp L_strstr_inner")
        r("L_strstr_next:")
        r("    inc ecx")
        r("    mov esi, ecx")
        r("    jmp L_strstr_outer")
        r("L_strstr_found:")
        r("    mov eax, ecx")
        r("    pop edi")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("L_strstr_nf:")
        r("    xor eax, eax")
        r("    pop edi")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_memset:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push edi")
        r("    mov edi, [ebp + 8]")
        r("    mov eax, [ebp + 12]")
        r("    mov ecx, [ebp + 16]")
        r("    rep stosb")
        r("    mov eax, [ebp + 8]")
        r("    pop edi")
        r("    pop ebp")
        r("    ret")
        r("")
        # sprintf: minimal, handles "%d"
        r("_sprintf:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push ebx")
        r("    push edi")
        r("    mov edi, [ebp + 8]")
        r("    mov eax, [ebp + 12]")
        r("    cmp byte ptr [eax], '%'")
        r("    jne L_sprintf_raw")
        r("    cmp byte ptr [eax + 1], 'd'")
        r("    jne L_sprintf_raw")
        r("    mov eax, [ebp + 16]")
        r("    test eax, eax")
        r("    jns L_sprintf_pos")
        r("    neg eax")
        r("    mov byte ptr [edi], '-'")
        r("    inc edi")
        r("L_sprintf_pos:")
        r("    mov ebx, 10")
        r("    xor ecx, ecx")
        r("    cmp eax, 0")
        r("    jne L_sprintf_loop1")
        r("    mov byte ptr [edi], '0'")
        r("    inc edi")
        r("    jmp L_sprintf_done")
        r("L_sprintf_loop1:")
        r("    xor edx, edx")
        r("    div ebx")
        r("    push edx")
        r("    inc ecx")
        r("    test eax, eax")
        r("    jnz L_sprintf_loop1")
        r("L_sprintf_loop2:")
        r("    pop edx")
        r("    add dl, '0'")
        r("    mov [edi], dl")
        r("    inc edi")
        r("    dec ecx")
        r("    jnz L_sprintf_loop2")
        r("L_sprintf_done:")
        r("    mov byte ptr [edi], 0")
        r("    mov eax, edi")
        r("    sub eax, [ebp + 8]")
        r("    pop edi")
        r("    pop ebx")
        r("    pop ebp")
        r("    ret")
        r("L_sprintf_raw:")
        r("    mov al, [eax]")
        r("    mov [edi], al")
        r("    test al, al")
        r("    jz L_sprintf_raw_done")
        r("    inc edi")
        r("    inc eax")
        r("    jmp L_sprintf_raw")
        r("L_sprintf_raw_done:")
        r("    mov eax, edi")
        r("    sub eax, [ebp + 8]")
        r("    pop edi")
        r("    pop ebx")
        r("    pop ebp")
        r("    ret")
        r("")
        # printf
        r("_printf:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push esi")
        r("    mov esi, [ebp + 8]")
        r("    cmp byte ptr [esi], '%'")
        r("    jne L_printf_raw")
        r("    cmp byte ptr [esi + 1], 's'")
        r("    je L_printf_str")
        r("    cmp byte ptr [esi + 1], 'd'")
        r("    je L_printf_int")
        r("L_printf_raw:")
        r("    push dword ptr [ebp + 8]")
        r("    call L_write_stdout")
        r("    add esp, 4")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("L_printf_str:")
        r("    push dword ptr [ebp + 12]")
        r("    call L_write_stdout")
        r("    add esp, 4")
        r("    mov esi, [ebp + 8]")
        r("    cmp byte ptr [esi + 2], 10")
        r("    jne L_printf_end")
        r("    push 10")
        r("    call L_write_char")
        r("    add esp, 4")
        r("L_printf_end:")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("L_printf_int:")
        r("    push dword ptr [ebp + 12]")
        r("    call L_write_int")
        r("    add esp, 4")
        r("    mov esi, [ebp + 8]")
        r("    cmp byte ptr [esi + 2], 10")
        r("    jne L_printf_end_int")
        r("    push 10")
        r("    call L_write_char")
        r("    add esp, 4")
        r("L_printf_end_int:")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("")
        # stdout helpers
        r("L_write_stdout:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push esi")
        r("    push ebx")
        r("    mov esi, [ebp + 8]")
        r("    push esi")
        r("    call _strlen")
        r("    add esp, 4")
        r("    mov ebx, eax")
        r("    sub esp, 4")
        r("    push 0")
        r("    lea eax, [esp + 4]")
        r("    push eax")
        r("    push ebx")
        r("    push esi")
        r("    push -11")
        r("    call _GetStdHandle@4")
        r("    push eax")
        r("    call _WriteFile@20")
        r("    add esp, 4")
        r("    pop ebx")
        r("    pop esi")
        r("    pop ebp")
        r("    ret")
        r("")
        r("L_write_char:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    sub esp, 8")
        r("    mov eax, [ebp + 8]")
        r("    mov byte ptr [ebp - 4], al")
        r("    lea eax, [ebp - 8]")
        r("    push 0")
        r("    push eax")
        r("    push 1")
        r("    lea eax, [ebp - 4]")
        r("    push eax")
        r("    push -11")
        r("    call _GetStdHandle@4")
        r("    push eax")
        r("    call _WriteFile@20")
        r("    mov esp, ebp")
        r("    pop ebp")
        r("    ret")
        r("")
        r("L_write_int:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    sub esp, 16")
        r("    push ebx")
        r("    push edi")
        r("    lea edi, [esp + 8]")
        r("    mov eax, [ebp + 8]")
        r("    test eax, eax")
        r("    jns L_write_int_pos")
        r("    neg eax")
        r("    push eax")
        r("    push 45")
        r("    call L_write_char")
        r("    add esp, 4")
        r("    pop eax")
        r("L_write_int_pos:")
        r("    mov ebx, 10")
        r("    xor ecx, ecx")
        r("    cmp eax, 0")
        r("    jne L_write_int_loop1")
        r("    mov byte ptr [edi], '0'")
        r("    inc edi")
        r("    jmp L_write_int_done")
        r("L_write_int_loop1:")
        r("    xor edx, edx")
        r("    div ebx")
        r("    push edx")
        r("    inc ecx")
        r("    test eax, eax")
        r("    jnz L_write_int_loop1")
        r("L_write_int_loop2:")
        r("    pop edx")
        r("    add dl, '0'")
        r("    mov [edi], dl")
        r("    inc edi")
        r("    dec ecx")
        r("    jnz L_write_int_loop2")
        r("L_write_int_done:")
        r("    mov byte ptr [edi], 0")
        r("    lea eax, [esp + 8]")
        r("    push eax")
        r("    call L_write_stdout")
        r("    add esp, 4")
        r("    pop edi")
        r("    pop ebx")
        r("    mov esp, ebp")
        r("    pop ebp")
        r("    ret")
        r("")
        # File I/O
        r("_fopen:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    mov eax, [ebp + 12]")
        r("    mov al, byte ptr [eax]")
        r("    cmp al, 'w'")
        r("    je L_fopen_write")
        r("    push 0")
        r("    push 128")
        r("    push 3")
        r("    push 0")
        r("    push 0")
        r("    push -2147483648")
        r("    push dword ptr [ebp + 8]")
        r("    call _CreateFileA@28")
        r("    jmp L_fopen_end")
        r("L_fopen_write:")
        r("    push 0")
        r("    push 128")
        r("    push 2")
        r("    push 0")
        r("    push 0")
        r("    push 1073741824")
        r("    push dword ptr [ebp + 8]")
        r("    call _CreateFileA@28")
        r("L_fopen_end:")
        r("    cmp eax, -1")
        r("    jne L_fopen_ok")
        r("    xor eax, eax")
        r("L_fopen_ok:")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_fclose:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push dword ptr [ebp + 8]")
        r("    call _CloseHandle@4")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_fread:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    sub esp, 4")
        r("    push 0")
        r("    lea eax, [ebp - 4]")
        r("    push eax")
        r("    mov eax, [ebp + 12]")
        r("    imul eax, [ebp + 16]")
        r("    push eax")
        r("    push dword ptr [ebp + 8]")
        r("    push dword ptr [ebp + 20]")
        r("    call _ReadFile@20")
        r("    mov eax, [ebp - 4]")
        r("    mov esp, ebp")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_fputs:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push ebx")
        r("    sub esp, 4")
        r("    push dword ptr [ebp + 8]")
        r("    call _strlen")
        r("    add esp, 4")
        r("    mov ebx, eax")
        r("    push 0")
        r("    lea eax, [ebp - 4]")
        r("    push eax")
        r("    push ebx")
        r("    push dword ptr [ebp + 8]")
        r("    push dword ptr [ebp + 12]")
        r("    call _WriteFile@20")
        r("    mov eax, [ebp - 4]")
        r("    mov esp, ebp")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_fputc:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    sub esp, 8")
        r("    mov eax, [ebp + 8]")
        r("    mov byte ptr [ebp - 4], al")
        r("    lea eax, [ebp - 8]")
        r("    push 0")
        r("    push eax")
        r("    push 1")
        r("    lea eax, [ebp - 4]")
        r("    push eax")
        r("    push dword ptr [ebp + 12]")
        r("    call _WriteFile@20")
        r("    mov eax, [ebp - 8]")
        r("    mov esp, ebp")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_fwrite:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    sub esp, 4")
        r("    mov eax, [ebp + 12]")
        r("    imul eax, [ebp + 16]")
        r("    push 0")
        r("    lea ecx, [ebp - 4]")
        r("    push ecx")
        r("    push eax")
        r("    push dword ptr [ebp + 8]")
        r("    push dword ptr [ebp + 20]")
        r("    call _WriteFile@20")
        r("    mov eax, [ebp - 4]")
        r("    mov esp, ebp")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_fseek:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push dword ptr [ebp + 16]")
        r("    push 0")
        r("    push dword ptr [ebp + 12]")
        r("    push dword ptr [ebp + 8]")
        r("    call _SetFilePointer@16")
        r("    xor eax, eax")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_ftell:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push 1")
        r("    push 0")
        r("    push 0")
        r("    push dword ptr [ebp + 8]")
        r("    call _SetFilePointer@16")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_fflush:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    mov eax, [ebp + 8]")
        r("    test eax, eax")
        r("    jz L_fflush_done")
        r("    push eax")
        r("    call _FlushFileBuffers@4")
        r("L_fflush_done:")
        r("    pop ebp")
        r("    ret")
        r("")
        # Process
        r("_exit:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push dword ptr [ebp + 8]")
        r("    call _ExitProcess@4")
        r("L_exit_never:")
        r("    pop ebp")
        r("    ret")
        r("")
        r("_system:")
        r("    push ebp")
        r("    mov ebp, esp")
        r("    push 1")
        r("    push dword ptr [ebp + 8]")
        r("    call _WinExec@8")
        r("    pop ebp")
        r("    ret")

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
        elif isinstance(node, RawBlock):
            for s in node.body:
                self.scan_vars(s)

    def compile_function(self, fn):
        print("Compiling function:", fn.name)
        self.assembly.append(f"_{fn.name}:")
        self.assembly.append("    push ebp")
        self.assembly.append("    mov ebp, esp")
        
        # Save function arguments in local_vars map
        # Under cdecl: ebp + 8 is 1st arg, ebp + 12 is 2nd, etc.
        old_local_vars = self.local_vars.copy()
        old_string_vars = getattr(self, 'string_vars', set()).copy()
        self.local_vars = {}
        self.string_vars = set()
        for i, param in enumerate(fn.params):
            param_name = param[0] if isinstance(param, (list, tuple)) else param
            param_type = param[1] if isinstance(param, (list, tuple)) and len(param) > 1 else None
            # Argument offset from ebp: ebp + 8 + i * 4
            self.local_vars[param_name] = -(8 + i * 4) # Negative offset to represent arguments
            # Track string parameters
            if param_type == 'string':
                self.string_vars.add(param_name)
            
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
        self.string_vars = old_string_vars

    def compile_stmt(self, node):
        if hasattr(node, 'line') and node.line > 0:
            self.assembly.append(f"    # line {node.line}")
            
        if isinstance(node, Assignment):
            self.compile_expr(node.value)
            self.assembly.append("    pop eax")
            offset = self.local_vars[node.name]
            self.assembly.append(f"    mov [ebp - {offset}], eax")
            # Track if this variable holds a string
            if self._is_string_expr(node.value):
                self.string_vars = getattr(self, 'string_vars', set())
                self.string_vars.add(node.name)
        elif isinstance(node, DataFieldAssign):
            self.compile_expr(node.value)
            self.compile_expr(node.instance)
            self.assembly.append("    pop eax") # instance
            self.assembly.append("    pop ebx") # value
            offset = self.get_prop_offset(node.field_name)
            self.assembly.append(f"    mov [eax + {offset}], ebx")
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
            self.assembly.append("    push 0")
            self.assembly.append("    call _fflush")
            self.assembly.append("    add esp, 4")
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
            if node.property == "value_byte":
                self.assembly.append("    mov byte ptr [edx], al")
            elif node.property == "value_word":
                self.assembly.append("    mov word ptr [edx], ax")
            else:
                self.assembly.append("    mov [edx], eax")
        elif isinstance(node, ArrayIndexAssign):
            # base[index] = value
            self.compile_expr(node.value)
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    pop edx") # base (list struct pointer)
            self.assembly.append("    pop ecx") # index
            self.assembly.append("    pop eax") # value
            # List: data pointer is at [edx + 8]
            self.assembly.append("    mov edx, [edx + 8]")
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
        elif isinstance(node, RawBlock):
            for stmt in node.body:
                self.compile_stmt(stmt)
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
                is_str = self._is_string_expr(node.left) or self._is_string_expr(node.right)
                if is_str:
                    self.assembly.append("    push ebx")
                    self.assembly.append("    push eax")
                    self.assembly.append("    call _concat_strings")
                    self.assembly.append("    add esp, 8")
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
            elif node.op == "and":
                self.assembly.append("    and eax, ebx")
            elif node.op == "or":
                self.assembly.append("    or eax, ebx")
            elif node.op == "&":
                self.assembly.append("    and eax, ebx")
            elif node.op == "<<":
                self.assembly.append("    mov ecx, ebx")
                self.assembly.append("    shl eax, cl")
            elif node.op == ">>":
                self.assembly.append("    mov ecx, ebx")
                self.assembly.append("    sar eax, cl")
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
            
            # Determine if this is a string comparison based on type info
            left_type = getattr(node.left, 'inferred_type', 'any')
            right_type = getattr(node.right, 'inferred_type', 'any')
            is_str_cmp = self._is_string_expr(node.left) or self._is_string_expr(node.right)
            # Also treat 'any' comparisons involving string literals as string
            if not is_str_cmp and (left_type == 'string' or right_type == 'string'):
                is_str_cmp = True
            
            label_true = self.next_label("L_cmp_true")
            label_end = self.next_label("L_cmp_end")
            
            if node.op == "has":
                # String containment: call strstr(haystack, needle)
                self.assembly.append("    push ebx")
                self.assembly.append("    push eax")
                self.assembly.append("    call _strstr")
                self.assembly.append("    add esp, 8")
                # strstr returns non-null (non-zero) if found
                self.assembly.append("    cmp eax, 0")
                self.assembly.append(f"    jne {label_true}")
            elif is_str_cmp:
                # Use strcmp for string comparisons
                self.assembly.append("    push ebx")
                self.assembly.append("    push eax")
                self.assembly.append("    call _strcmp")
                self.assembly.append("    add esp, 8")
                # strcmp returns 0 if equal, <0 or >0 otherwise
                self.assembly.append("    cmp eax, 0")
            else:
                self.assembly.append("    cmp eax, ebx")
            
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
            if hasattr(self, 'structs') and node.name in self.structs:
                # Compute struct size from max prop_offset + 4
                struct_size = (max(self.prop_offsets.values()) + 4) if self.prop_offsets else 128
                # Ensure minimum and alignment
                struct_size = max(struct_size, 16)
                # Align to 16 bytes
                struct_size = (struct_size + 15) & ~15
                self.assembly.append(f"    push {struct_size}")
                self.assembly.append("    call _malloc")
                self.assembly.append("    add esp, 4")
                self.assembly.append("    push eax")
            else:
                for arg in reversed(node.args):
                    self.compile_expr(arg)
                self.assembly.append(f"    call _{node.name}")
                if len(node.args) > 0:
                    self.assembly.append(f"    add esp, {len(node.args) * 4}")
                self.assembly.append("    push eax")
        elif isinstance(node, DataFieldAccess):
            self.compile_expr(node.instance)
            self.assembly.append("    pop eax")
            offset = self.get_prop_offset(node.field_name)
            self.assembly.append(f"    mov eax, [eax + {offset}]")
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
            elif node.property == "value_byte":
                self.assembly.append("    pop edx") # address
                self.assembly.append("    xor eax, eax")
                self.assembly.append("    mov al, byte ptr [edx]")
                self.assembly.append("    push eax")
            elif node.property == "addr":
                pass # already top of stack
            else:
                raise Exception(f"[line {getattr(node, 'line', '?')}] Property {node.property} not supported in native codegen")
        elif isinstance(node, ArrayIndex):
            # base[index] - need to distinguish string vs list indexing
            base_type = getattr(node.base, 'inferred_type', 'any')
            is_str = self._is_string_expr(node.base) or base_type == 'string'
            # Override: list-of-string fields store string POINTERS in data array
            if isinstance(node.base, DataFieldAccess) and node.base.field_name in ['struct_names', 'prop_names', 'local_var_names']:
                is_str = False
            
            self.compile_expr(node.index)
            self.compile_expr(node.base)
            self.assembly.append("    pop edx") # base address
            self.assembly.append("    pop ecx") # index
            
            if is_str:
                # String byte access: lookup in char_strings table
                self.assembly.append("    movzx eax, byte ptr [edx + ecx]")
                self.assembly.append("    shl eax, 1")
                self.assembly.append("    add eax, offset char_strings")
                self.assembly.append("    push eax")
            else:
                # List access: data pointer is at [base + 8]
                self.assembly.append("    mov edx, [edx + 8]")
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
        elif isinstance(node, ListLiteral):
            self.assembly.append("    push 12")
            self.assembly.append("    call _malloc")
            self.assembly.append("    add esp, 4")
            self.assembly.append("    push eax")
            cap = max(4, len(node.elements))
            self.assembly.append(f"    push {cap * 4}")
            self.assembly.append("    call _malloc")
            self.assembly.append("    add esp, 4")
            self.assembly.append("    pop ebx")
            self.assembly.append(f"    mov dword ptr [ebx], {len(node.elements)}")
            self.assembly.append(f"    mov dword ptr [ebx+4], {cap}")
            self.assembly.append("    mov [ebx+8], eax")
            for i, el in enumerate(node.elements):
                self.assembly.append("    push ebx")
                self.assembly.append("    push eax")
                self.compile_expr(el)
                self.assembly.append("    pop ecx")
                self.assembly.append("    pop eax")
                self.assembly.append("    pop ebx")
                self.assembly.append(f"    mov [eax + {i*4}], ecx")
            self.assembly.append("    push ebx")
        elif isinstance(node, MethodCall):
            if node.method_name == "append":
                self.compile_expr(node.args[0])
                self.compile_expr(node.instance)
                self.assembly.append("    pop ebx")
                self.assembly.append("    pop ecx")
                self.assembly.append("    mov eax, [ebx]")
                self.assembly.append("    mov edx, [ebx+4]")
                self.assembly.append("    cmp eax, edx")
                no_realloc_label = self.next_label("L_no_realloc")
                self.assembly.append(f"    jl {no_realloc_label}")
                self.assembly.append("    shl edx, 1")
                self.assembly.append("    mov [ebx+4], edx")
                self.assembly.append("    push ebx")
                self.assembly.append("    push ecx")
                self.assembly.append("    shl edx, 2")
                self.assembly.append("    push edx")
                self.assembly.append("    push dword ptr [ebx+8]")
                self.assembly.append("    call _realloc")
                self.assembly.append("    add esp, 8")
                
                # Check for realloc failure
                self.assembly.append("    cmp eax, 0")
                realloc_ok_label = self.next_label("L_realloc_ok")
                self.assembly.append("    jne " + realloc_ok_label)
                self.assembly.append("    push offset fmt_str")
                self.assembly.append("    push offset L_realloc_fail_msg")
                self.assembly.append("    call _printf")
                self.assembly.append("    push 1")
                self.assembly.append("    call _exit")
                self.assembly.append(f"{realloc_ok_label}:")
                
                self.assembly.append("    pop ecx")
                self.assembly.append("    pop ebx")
                self.assembly.append("    mov [ebx+8], eax")
                self.assembly.append(f"{no_realloc_label}:")
                self.assembly.append("    mov eax, [ebx]")
                self.assembly.append("    mov edx, [ebx+8]")
                self.assembly.append("    mov [edx + eax*4], ecx")
                self.assembly.append("    inc eax")
                self.assembly.append("    mov [ebx], eax")
                self.assembly.append("    push 0")
            elif node.method_name == "pop":
                self.compile_expr(node.instance)
                self.assembly.append("    pop ebx")
                self.assembly.append("    mov eax, [ebx]")
                self.assembly.append("    dec eax")
                self.assembly.append("    mov [ebx], eax")
                self.assembly.append("    mov edx, [ebx+8]")
                self.assembly.append("    mov ecx, [edx + eax*4]")
                self.assembly.append("    push ecx")
            elif isinstance(node.instance, Variable) and node.instance.name in self.module_names:
                for arg in reversed(node.args):
                    self.compile_expr(arg)
                self.assembly.append(f"    call _{node.method_name}")
                if len(node.args) > 0:
                    self.assembly.append(f"    add esp, {len(node.args) * 4}")
                self.assembly.append("    push eax")
        elif isinstance(node, Len):
            self.compile_expr(node.target)
            is_str = self._is_string_expr(node.target)
            # Override: list-type fields should use list length, not strlen
            if isinstance(node.target, DataFieldAccess) and node.target.field_name in ['struct_names', 'prop_names', 'local_var_names']:
                is_str = False
            if is_str:
                self.assembly.append("    call _strlen")
                self.assembly.append("    add esp, 4")
                self.assembly.append("    push eax")
            else:
                self.assembly.append("    pop eax")
                self.assembly.append("    mov eax, [eax]")
                self.assembly.append("    push eax")
        elif isinstance(node, Slice):
            is_str = self._is_string_expr(node.base)
            if is_str:
                if node.start and node.end:
                    self.compile_expr(node.end)
                    self.compile_expr(node.start)
                    self.compile_expr(node.base)
                    self.assembly.append("    call _slice_string")
                    self.assembly.append("    add esp, 12")
                    self.assembly.append("    push eax")
                else:
                    raise Exception(f"[line {getattr(node, 'line', '?')}] Slice with omitted start/end not supported in native codegen yet")
            else:
                raise Exception(f"[line {getattr(node, 'line', '?')}] List slicing not supported in native codegen yet")
        elif isinstance(node, StrConvert):
            self.compile_expr(node.target)
            self.assembly.append("    pop ebx") # int to convert
            self.assembly.append("    push 16") # buffer size
            self.assembly.append("    call _malloc")
            self.assembly.append("    add esp, 4")
            self.assembly.append("    push eax") # save buffer
            self.assembly.append("    push ebx")
            self.assembly.append("    push offset fmt_int_pure") 
            self.assembly.append("    push eax")
            self.assembly.append("    call _sprintf")
            self.assembly.append("    add esp, 12")
            self.assembly.append("    pop eax") # restore buffer pointer
            self.assembly.append("    push eax")
        else:
            raise Exception(f"[line {getattr(node, 'line', '?')}] Native codegen unhandled node: {type(node)}")
