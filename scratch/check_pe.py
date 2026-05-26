import struct

with open('build_test_new.exe', 'rb') as f:
    data = f.read()

print(f"File size: {len(data)}")
print(f"DOS e_magic: {data[0:2]}")
e_lfanew = struct.unpack('<I', data[60:64])[0]
print(f"e_lfanew: {e_lfanew}")

pe_sig = data[e_lfanew:e_lfanew+4]
print(f"PE sig: {pe_sig}")

off = e_lfanew + 4
machine = struct.unpack('<H', data[off:off+2])[0]
num_sections = struct.unpack('<H', data[off+2:off+4])[0]
siz_opt_hdr = struct.unpack('<H', data[off+16:off+18])[0]
print(f"\nMachine: {machine} NumSections: {num_sections} OptHdrSize: {siz_opt_hdr}")

opt_off = off + 20
magic = struct.unpack('<H', data[opt_off:opt_off+2])[0]
entry = struct.unpack('<I', data[opt_off+16:opt_off+20])[0]
image_base = struct.unpack('<I', data[opt_off+28:opt_off+32])[0]
size_of_image = struct.unpack('<I', data[opt_off+56:opt_off+60])[0]
print(f"Magic: {magic} Entry: {hex(entry)} ImageBase: {hex(image_base)}")
print(f"SizeOfImage: {size_of_image}")

# Sections
sec_off = opt_off + siz_opt_hdr
for i in range(num_sections):
    s = sec_off + i * 40
    name = data[s:s+8].rstrip(b'\x00').decode()
    vsize = struct.unpack('<I', data[s+8:s+12])[0]
    vaddr = struct.unpack('<I', data[s+12:s+16])[0]
    raw_size = struct.unpack('<I', data[s+16:s+20])[0]
    raw_ptr = struct.unpack('<I', data[s+20:s+24])[0]
    print(f"\n  [{name}] VS={vsize} VA={hex(vaddr)} RS={raw_size} RP={hex(raw_ptr)}")

# Check .idata
idata_va = struct.unpack('<I', data[opt_off+104:opt_off+108])[0]
idata_sz = struct.unpack('<I', data[opt_off+108:opt_off+112])[0]
print(f"\nImport Dir RVA: {hex(idata_va)} Size: {idata_sz}")

# Find idata section
for i in range(num_sections):
    s = sec_off + i * 40
    name = data[s:s+8].rstrip(b'\x00').decode()
    vaddr = struct.unpack('<I', data[s+12:s+16])[0]
    vsize = struct.unpack('<I', data[s+8:s+12])[0]
    raw_ptr = struct.unpack('<I', data[s+20:s+24])[0]
    if vaddr <= idata_va < vaddr + vsize:
        offset_in_file = raw_ptr + (idata_va - vaddr)
        print(f"  idata starts at file offset {hex(offset_in_file)}")
        # Show first few imports
        import_desc = data[offset_in_file:offset_in_file+20]
        print(f"  First import descriptor: {import_desc.hex()}")
        break

# Compare with a known-good exe
with open('tests/test_simple.exe', 'rb') as f:
    good = f.read()
print(f"\nGood exe size: {len(good)}")
