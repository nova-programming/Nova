import os
import re

# Read the new stdlib_asm.txt
with open('stdlib_asm.txt', 'r') as f:
    asm_lines = [line.strip() for line in f if line.strip()]

# 1. Patch compiler/codegen_x86.py
with open('compiler/codegen_x86.py', 'r') as f:
    py_code = f.read()

# We need to find the injection block in py_code. 
# It starts at `        self.assembly.append("L_out_of_bounds_msg: .asciz \\"Array index out of bounds\\n\\"")`
# and ends near the end of the file. But actually, we can just find `        self.assembly.append("_random:")`
# and replace everything up to the next function or end.
py_random_start = py_code.find('        self.assembly.append("_random:")')
py_random_end = py_code.find('        self.assembly.append("_sys_write:")', py_random_start)

new_py_random = []
# Find the bounds in asm_lines
asm_random_start = asm_lines.index('_random:')
asm_random_end = asm_lines.index('_sys_write:')

for line in asm_lines[asm_random_start:asm_random_end]:
    escaped = line.replace('"', '\\"')
    new_py_random.append(f'        self.assembly.append("{escaped}")')

py_code = py_code[:py_random_start] + '\n'.join(new_py_random) + '\n' + py_code[py_random_end:]

with open('compiler/codegen_x86.py', 'w') as f:
    f.write(py_code)


# 2. Patch stdlib/codegen.nv
with open('stdlib/codegen.nv', 'r') as f:
    nv_code = f.read()

nv_random_start = nv_code.find('    emit(state, "_random:")')
nv_random_end = nv_code.find('    emit(state, "_sys_write:")', nv_random_start)

new_nv_random = []
for line in asm_lines[asm_random_start:asm_random_end]:
    escaped = line.replace('"', '\\"')
    new_nv_random.append(f'    emit(state, "{escaped}")')

nv_code = nv_code[:nv_random_start] + '\n'.join(new_nv_random) + '\n' + nv_code[nv_random_end:]

with open('stdlib/codegen.nv', 'w') as f:
    f.write(nv_code)

print("Patch applied to both compilers successfully.")
