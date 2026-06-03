lines = open("stdlib_asm.txt").read().splitlines()
fixed = []
for i, l in enumerate(lines):
    if "str_const_1" in l:
        fixed.append(l.replace("str_const_1", "L_sys_platform_str" if i < 500 else "L_chacha_buffer_str"))
    else:
        fixed.append(l)
open("stdlib_asm.txt", "w").write("\n".join(fixed) + "\n")
