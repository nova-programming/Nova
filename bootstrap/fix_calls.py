import os
import re

def process_file(filepath, pattern, call_instruction):
    if not os.path.exists(filepath): return
    with open(filepath, "r") as f:
        content = f.read()

    # Regex to match:
    # emit(state, "    call _printf")
    # clean_n(state, 2)
    # Group 1: leading whitespace
    # Group 2: function name (e.g. _printf)
    # Group 3: optional clean_n line
    # Group 4: argument count in clean_n
    
    regex = re.compile(r'([ \t]*)emit\(state, "(?:    )?' + call_instruction + r' (.*?)"\)\n([ \t]*clean_n\(state, (.*?)\))?')
    
    def repl(m):
        indent = m.group(1)
        func_name = m.group(2)
        has_clean = m.group(3)
        arg_count = m.group(4) if has_clean else "0"
        
        # If the function name is dynamically built like `_" + node.val_str`
        if '" +' in func_name or '+ "' in func_name:
            # We pass it exactly as is
            pass
        else:
            func_name = f'"{func_name}"'
            
        return f'{indent}emit_call(state, {func_name}, {arg_count})'
        
    new_content = regex.sub(repl, content)
    
    with open(filepath, "w") as f:
        f.write(new_content)
    print(f"Processed {filepath}")

process_file("stdlib/backend/x86_64/codegen_expr.nv", "call", "call")
process_file("stdlib/backend/x86_64/codegen_stmt.nv", "call", "call")
process_file("stdlib/backend/arm64/codegen_expr.nv", "bl", "bl")
process_file("stdlib/backend/arm64/codegen_stmt.nv", "bl", "bl")
