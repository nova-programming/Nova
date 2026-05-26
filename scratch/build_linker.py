import sys

with open("stdlib/linker.nv", "r") as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if "import_names = []" in line and "1. Collect imports" in lines[i-1]:
        # Replace the import collection logic
        new_lines.append("    msvcrt_names = []\n")
        new_lines.append("    kernel32_names = []\n")
        new_lines.append("    i = 0\n")
        new_lines.append("    while i < len(labels) {\n")
        new_lines.append("        if labels[i].defined == 0 {\n")
        new_lines.append("            actual_name = labels[i].name\n")
        new_lines.append("            if len(actual_name) > 0 and actual_name[0] == \"_\" {\n")
        new_lines.append("                actual_name = str_sub(actual_name, 1, len(actual_name))\n")
        new_lines.append("            }\n")
        new_lines.append("            if actual_name == \"GetCommandLineA\" {\n")
        new_lines.append("                kernel32_names.append(actual_name)\n")
        new_lines.append("            } else {\n")
        new_lines.append("                msvcrt_names.append(actual_name)\n")
        new_lines.append("            }\n")
        new_lines.append("        }\n")
        new_lines.append("        i = i + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    import_names = []\n")
        new_lines.append("    i = 0\n")
        new_lines.append("    while i < len(msvcrt_names) {\n")
        new_lines.append("        import_names.append(msvcrt_names[i])\n")
        new_lines.append("        i = i + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    i = 0\n")
        new_lines.append("    while i < len(kernel32_names) {\n")
        new_lines.append("        import_names.append(kernel32_names[i])\n")
        new_lines.append("        i = i + 1\n")
        new_lines.append("    }\n")
        
        # Skip original loop
        i += 1
        while "i = i + 1" not in lines[i]: i += 1
        i += 1 # skip }
        while "}" not in lines[i]: i += 1
        i += 1 # skip }
    elif "text_size_with_thunks = len(code) + (num_imports * 6)" in line:
        new_lines.append(line)
    elif "idata_rva = data_rva + align_up(len(data_sec), section_align)" in line:
        new_lines.append(line)
        new_lines.append("\n")
        new_lines.append("    num_dlls = 0\n")
        new_lines.append("    if len(msvcrt_names) > 0 { num_dlls = num_dlls + 1 }\n")
        new_lines.append("    if len(kernel32_names) > 0 { num_dlls = num_dlls + 1 }\n")
        new_lines.append("    descriptors_size = (num_dlls + 1) * 20\n")
        new_lines.append("    ilt_msvcrt_size = 0\n")
        new_lines.append("    if len(msvcrt_names) > 0 { ilt_msvcrt_size = (len(msvcrt_names) + 1) * 4 }\n")
        new_lines.append("    ilt_kernel32_size = 0\n")
        new_lines.append("    if len(kernel32_names) > 0 { ilt_kernel32_size = (len(kernel32_names) + 1) * 4 }\n")
        new_lines.append("    ilt_total_size = ilt_msvcrt_size + ilt_kernel32_size\n")
        new_lines.append("    ilt_rva = idata_rva + descriptors_size\n")
        new_lines.append("    iat_rva = ilt_rva + ilt_total_size\n")
        new_lines.append("    dll_names_rva = iat_rva + ilt_total_size\n")
        new_lines.append("    dll_msvcrt_len = 11\n")
        new_lines.append("    dll_kernel32_len = 13\n")
        new_lines.append("    dll_msvcrt_rva = 0\n")
        new_lines.append("    dll_kernel32_rva = 0\n")
        new_lines.append("    curr_dll_rva = dll_names_rva\n")
        new_lines.append("    if len(msvcrt_names) > 0 {\n")
        new_lines.append("        dll_msvcrt_rva = curr_dll_rva\n")
        new_lines.append("        curr_dll_rva = curr_dll_rva + dll_msvcrt_len\n")
        new_lines.append("    }\n")
        new_lines.append("    if len(kernel32_names) > 0 {\n")
        new_lines.append("        dll_kernel32_rva = curr_dll_rva\n")
        new_lines.append("        curr_dll_rva = curr_dll_rva + dll_kernel32_len\n")
        new_lines.append("    }\n")
        new_lines.append("    hint_name_table_rva = curr_dll_rva\n")
        new_lines.append("    \n")
        new_lines.append("    iat_offsets = []\n")
        new_lines.append("    i = 0\n")
        new_lines.append("    while i < len(msvcrt_names) {\n")
        new_lines.append("        iat_offsets.append(i * 4)\n")
        new_lines.append("        i = i + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    i = 0\n")
        new_lines.append("    while i < len(kernel32_names) {\n")
        new_lines.append("        iat_offsets.append(ilt_msvcrt_size + (i * 4))\n")
        new_lines.append("        i = i + 1\n")
        new_lines.append("    }\n")
        
        # Skip the old idata layout logic up to hint_name_table_rva
        i += 1
        while "hint_name_table_rva" not in lines[i]: i += 1
        i += 1
    elif "import_idx = 0" in line and "while i < len(labels)" in lines[i+2]:
        new_lines.append("    i = 0\n")
        i += 1
    elif "entry_iat_rva = iat_rva + (import_idx * 4)" in line:
        new_lines.append("            actual_name = labels[i].name\n")
        new_lines.append("            if len(actual_name) > 0 and actual_name[0] == \"_\" {\n")
        new_lines.append("                actual_name = str_sub(actual_name, 1, len(actual_name))\n")
        new_lines.append("            }\n")
        new_lines.append("            j = 0\n")
        new_lines.append("            idx = 0\n")
        new_lines.append("            while j < len(import_names) {\n")
        new_lines.append("                if import_names[j] == actual_name {\n")
        new_lines.append("                    idx = j\n")
        new_lines.append("                    break\n")
        new_lines.append("                }\n")
        new_lines.append("                j = j + 1\n")
        new_lines.append("            }\n")
        new_lines.append("            entry_iat_rva = iat_rva + iat_offsets[idx]\n")
        i += 1
    elif "import_idx = import_idx + 1" in line:
        i += 1
    elif "Import Descriptor for msvcrt.dll" in line:
        # Re-write the idata section builder!
        # Skip everything until `while i < num_imports {` for Hint/Name builder
        while "Hint/Name bytes first" not in lines[i]: i += 1
        
        # Now insert our new `.idata` generation!
        new_lines.append("    idata = []\n")
        new_lines.append("    \n")
        new_lines.append("    if len(msvcrt_names) > 0 {\n")
        new_lines.append("        append_u32(idata, ilt_rva)\n")
        new_lines.append("        append_u32(idata, 0)\n")
        new_lines.append("        append_u32(idata, 0)\n")
        new_lines.append("        append_u32(idata, dll_msvcrt_rva)\n")
        new_lines.append("        append_u32(idata, iat_rva)\n")
        new_lines.append("    }\n")
        new_lines.append("    if len(kernel32_names) > 0 {\n")
        new_lines.append("        append_u32(idata, ilt_rva + ilt_msvcrt_size)\n")
        new_lines.append("        append_u32(idata, 0)\n")
        new_lines.append("        append_u32(idata, 0)\n")
        new_lines.append("        append_u32(idata, dll_kernel32_rva)\n")
        new_lines.append("        append_u32(idata, iat_rva + ilt_msvcrt_size)\n")
        new_lines.append("    }\n")
        new_lines.append("    \n")
        new_lines.append("    # Null descriptor\n")
        new_lines.append("    j = 0\n")
        new_lines.append("    while j < 5 {\n")
        new_lines.append("        append_u32(idata, 0)\n")
        new_lines.append("        j = j + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    \n")
        new_lines.append("    # We need hint_rvas to write ILT/IAT\n")
        
    elif "hint_name_bytes =" in line and "Hint/Name bytes first" in lines[i-1]:
        new_lines.append(line)
    elif "# Write ILT" in line:
        # Instead of old ILT generation, generate it correctly per DLL
        while "# Write IAT" not in lines[i]: i += 1
        
        new_lines.append("    # Write ILT\n")
        new_lines.append("    j = 0\n")
        new_lines.append("    while j < len(msvcrt_names) {\n")
        new_lines.append("        append_u32(idata, hint_rvas[j])\n")
        new_lines.append("        j = j + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    if len(msvcrt_names) > 0 { append_u32(idata, 0) }\n")
        new_lines.append("    j = 0\n")
        new_lines.append("    while j < len(kernel32_names) {\n")
        new_lines.append("        append_u32(idata, hint_rvas[len(msvcrt_names) + j])\n")
        new_lines.append("        j = j + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    if len(kernel32_names) > 0 { append_u32(idata, 0) }\n")
        
    elif "# Write IAT" in line:
        while "Write DLL Name" not in lines[i]: i += 1
        
        new_lines.append("    # Write IAT\n")
        new_lines.append("    j = 0\n")
        new_lines.append("    while j < len(msvcrt_names) {\n")
        new_lines.append("        append_u32(idata, hint_rvas[j])\n")
        new_lines.append("        j = j + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    if len(msvcrt_names) > 0 { append_u32(idata, 0) }\n")
        new_lines.append("    j = 0\n")
        new_lines.append("    while j < len(kernel32_names) {\n")
        new_lines.append("        append_u32(idata, hint_rvas[len(msvcrt_names) + j])\n")
        new_lines.append("        j = j + 1\n")
        new_lines.append("    }\n")
        new_lines.append("    if len(kernel32_names) > 0 { append_u32(idata, 0) }\n")
        
    elif "Write DLL Name" in line:
        while "Write Hint/Name bytes" not in lines[i]: i += 1
        
        new_lines.append("    # Write DLL Names\n")
        new_lines.append("    if len(msvcrt_names) > 0 {\n")
        new_lines.append("        append_string_bytes(idata, \"msvcrt.dll\")\n")
        new_lines.append("        idata.append(0)\n")
        new_lines.append("    }\n")
        new_lines.append("    if len(kernel32_names) > 0 {\n")
        new_lines.append("        append_string_bytes(idata, \"kernel32.dll\")\n")
        new_lines.append("        idata.append(0)\n")
        new_lines.append("    }\n")
        
    else:
        new_lines.append(line)
        i += 1


with open("stdlib/linker.nv", "w") as f:
    f.writelines(new_lines)
