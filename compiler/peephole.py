def peephole_optimize(asm_lines):
    optimized = []
    i = 0
    n = len(asm_lines)
    
    while i < n:
        line1 = asm_lines[i]
        
        if i + 1 < n:
            line2 = asm_lines[i+1]
            
            l1_strip = line1.strip()
            l2_strip = line2.strip()
            
            if l1_strip.startswith("push ") and l2_strip.startswith("pop "):
                src = l1_strip[5:].strip()
                dst = l2_strip[4:].strip()
                
                # If they are exactly the same register, just eliminate both
                if src == dst:
                    i += 2
                    continue
                
                # push 0 -> pop eax => xor eax, eax
                if src == "0" and dst == "eax":
                    optimized.append("    xor eax, eax")
                    i += 2
                    continue
                
                # push src -> pop dst => mov dst, src
                optimized.append(f"    mov {dst}, {src}")
                i += 2
                continue
                
        # If no match, just append line1
        optimized.append(line1)
        i += 1
        
    return optimized
