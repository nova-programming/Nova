import os

with open('stdlib_asm.txt', 'r') as f:
    asm_lines = [line.strip() for line in f if line.strip()]

# For Python (codegen_x86.py)
py_code = []
for line in asm_lines:
    # Escape quotes
    escaped = line.replace('"', '\\"')
    py_code.append(f'        self.assembly.append("{escaped}")')

with open('py_injection.txt', 'w') as f:
    f.write('\n'.join(py_code))

# For Nova (stdlib/codegen.nv)
nv_code = []
for line in asm_lines:
    escaped = line.replace('"', '\\"')
    nv_code.append(f'    emit(state, "{escaped}")')

with open('nv_injection.txt', 'w') as f:
    f.write('\n'.join(nv_code))

print("Generated injection code.")
