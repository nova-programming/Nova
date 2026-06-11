import os
import re

def process_file(path):
    with open(path, "r") as f:
        content = f.read()

    # Stack ops
    content = re.sub(r'push (%[abcd])', r'str \1, [sp, #-16]!', content)
    content = re.sub(r'pop (%[abcd])', r'ldr \1, [sp], #16', content)
    content = content.replace("push 0", "mov x0, 0\n        emit(state, \"    str x0, [sp, #-16]!\")")
    content = content.replace("push 1", "mov x0, 1\n        emit(state, \"    str x0, [sp, #-16]!\")")

    # Math
    content = re.sub(r'add (%[abcd]), (%[abcd])', r'add \1, \1, \2', content)
    content = re.sub(r'sub (%[abcd]), (%[abcd])', r'sub \1, \1, \2', content)
    content = re.sub(r'imul (%[abcd]), (%[abcd])', r'mul \1, \1, \2', content)
    
    # Division
    content = content.replace('emit(state, "    cqo")', '')
    content = re.sub(r'idiv (%[abcd])', r'sdiv %a, %a, \1', content)
    content = content.replace('emit(state, "    push %d")', 'emit(state, "    str %a, [sp, #-16]!") # push result') # x86 modulo puts result in rdx, ARM we need to compute it.
    
    # Logic
    content = re.sub(r'xor (%[abcd]), \1', r'mov \1, 0', content)
    content = re.sub(r'sete (%[abcd])', r'cset \1, eq', content)
    content = re.sub(r'setne (%[abcd])', r'cset \1, ne', content)
    content = re.sub(r'setg (%[abcd])', r'cset \1, gt', content)
    content = re.sub(r'setl (%[abcd])', r'cset \1, lt', content)
    content = re.sub(r'setge (%[abcd])', r'cset \1, ge', content)
    content = re.sub(r'setle (%[abcd])', r'cset \1, le', content)
    content = re.sub(r'movzx (%[abcd]), [a-z]+', r'', content) # Remove movzx as cset handles it

    # Branches
    content = re.sub(r'jmp (L_[A-Za-z0-9_]+)', r'b \1', content)
    content = re.sub(r'je (L_[A-Za-z0-9_]+)', r'b.eq \1', content)
    content = re.sub(r'jne (L_[A-Za-z0-9_]+)', r'b.ne \1', content)

    # Calls
    content = re.sub(r'call (.*)', r'bl \1', content)

    # Memory Access
    # mov [%b - offset], %a -> str %a, [%b, #-offset]
    # In Nova source, it looks like: emit(state, "    mov [%b - " + str(0 - offset) + "], %a")
    content = content.replace('emit(state, "    mov [%b - " + str(0 - offset) + "], %a")', 
                              'emit(state, "    str %a, [%b, #" + str(offset) + "]")')
    content = content.replace('emit(state, "    mov [%b - " + str(offset) + "], %a")', 
                              'emit(state, "    str %a, [%b, #-" + str(offset) + "]")')
    
    # mov %a, [%b - offset]
    content = content.replace('emit(state, "    mov %a, [%b - " + str(0 - offset) + "]")', 
                              'emit(state, "    ldr %a, [%b, #" + str(offset) + "]")')
    content = content.replace('emit(state, "    mov %a, [%b - " + str(offset) + "]")', 
                              'emit(state, "    ldr %a, [%b, #-" + str(offset) + "]")')
    
    # lea %a, [rip + label]
    # emit(state, "    lea %a, [rip + " + node.val_str + "]")
    content = content.replace('emit(state, "    lea %a, [rip + " + ', 
                              'emit(state, "    adrp %a, " + node.val_str + "@PAGE")\n            emit(state, "    add %a, %a, " + ')
    content = content.replace('@PAGE")\n            emit(state, "    add %a, %a, " + node.val_str + "]', 
                              '@PAGE")\n            emit(state, "    add %a, %a, " + node.val_str + "@PAGEOFF")')

    # mov %a, [rip + label]
    content = content.replace('emit(state, "    mov %a, [rip + " + ', 
                              'emit(state, "    adrp %a, " + node.val_str + "@PAGE")\n            emit(state, "    ldr %a, [%a, " + ')
    content = content.replace('@PAGE")\n            emit(state, "    ldr %a, [%a, " + node.val_str + "]', 
                              '@PAGE")\n            emit(state, "    ldr %a, [%a, " + node.val_str + "@PAGEOFF]")')

    # Also handle strings constants
    content = content.replace('emit(state, "    lea %a, [rip + " + label + "]")',
                              'emit(state, "    adrp %a, " + label + "@PAGE")\n        emit(state, "    add %a, %a, " + label + "@PAGEOFF")')
    
    # Remove x86 registers
    content = re.sub(r'\beax\b', 'x0', content)
    content = re.sub(r'\bebx\b', 'x1', content)
    content = re.sub(r'\becx\b', 'x2', content)
    content = re.sub(r'\bedx\b', 'x3', content)

    with open(path, "w") as f:
        f.write(content)

process_file("stdlib/backend/arm64/codegen_expr.nv")
process_file("stdlib/backend/arm64/codegen_stmt.nv")
print("Done")
