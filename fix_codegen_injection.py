# Fix the broken injected code in stdlib/codegen.nv
# The injection was placed at top level (before def generate_assembly) 
# but references 'cg' and 'cg_add_line' which don't exist there.
# Fix: Remove the top-level injection and insert corrected code
# inside generate_assembly using emit(state, ...) instead.

import os

nv_path = 'stdlib/codegen.nv'
asm_path = 'stdlib_asm.txt'

with open(nv_path, 'r') as f:
    content = f.read()

# Find the injection boundaries
# The injection starts at "# --- Main entry point ---" (line 1068)
# and ends right before "def generate_assembly" (line 3933)
# Actually, let's find the exact positions

start_marker = "# --- Main entry point ---\n"
end_marker = "def generate_assembly"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Could not find injection boundaries")
    print(f"start_marker found: {start_idx != -1}")
    print(f"end_marker found: {end_idx != -1}")
    exit(1)

print(f"Removing injection from bytes {start_idx} to {end_idx}")

# Keep the start_marker comment but remove the injected code
keep_before = content[:start_idx]
keep_after = content[end_idx:]

# Read the asm lines and generate correct Nova emit() calls
with open(asm_path, 'r') as f:
    asm_lines = [line.strip() for line in f if line.strip()]

# Generate emit(state, ...) lines for Nova codegen
emit_lines = []
for line in asm_lines:
    escaped = line.replace('"', '\\"')
    emit_lines.append(f'    emit(state, "{escaped}")')

emit_block = '\n'.join(emit_lines)

# Create the new content:
# 1. Everything up to the main entry point comment
# 2. The emit_codegen_runtime(state) function definition
# 3. The original def generate_assembly (modified to call emit_codegen_runtime)
injection_function = f"""
# --- Emit stdlib runtime functions ---
def emit_codegen_runtime(state) {{{emit_block}
}}
"""

# Insert the call to emit_codegen_runtime inside generate_assembly
# Right before emit_win32_runtime(state)
old_call = "    emit_win32_runtime(state)"
new_call = f"    emit_codegen_runtime(state)\n{old_call}"

new_content = keep_before + injection_function + keep_after
new_content = new_content.replace(old_call, new_call)

with open(nv_path, 'w') as f:
    f.write(new_content)

print("Done! Fixed codegen.nv")
