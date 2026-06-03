def apply_injection(file_path, injection_file, marker):
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    with open(injection_file, 'r') as f:
        injection_code = f.read()
        
    for i, line in enumerate(lines):
        if marker in line:
            lines.insert(i, injection_code + '\n')
            break
            
    with open(file_path, 'w') as f:
        f.writelines(lines)
        
apply_injection('compiler/codegen_x86.py', 'py_injection.txt', 'def scan_vars')
apply_injection('stdlib/codegen.nv', 'nv_injection.txt', 'def generate_assembly')
print("Injection applied.")
