import struct
from collections import Counter

with open('tests/test_shl_min.exe', 'rb') as f:
    data = f.read()

pe_offset = struct.unpack('<I', data[0x3C:0x40])[0]
file_header_off = pe_offset + 4
num_sections = struct.unpack('<H', data[file_header_off+2:file_header_off+4])[0]
opt_header_off = file_header_off + 20
opt_header_size = struct.unpack('<H', data[file_header_off+16:file_header_off+18])[0]
section_off = opt_header_off + opt_header_size

for i in range(num_sections):
    section_start = section_off + i * 40
    name = data[section_start:section_start+8].rstrip(b'\x00').decode('ascii', errors='replace')
    raw_size = struct.unpack('<I', data[section_start+16:section_start+20])[0]
    raw_addr = struct.unpack('<I', data[section_start+20:section_start+24])[0]
    
    if name == '.text':
        text_data = data[raw_addr:raw_addr+raw_size]
        opcodes = Counter(text_data)
        print('Top opcodes:')
        for op, count in opcodes.most_common(20):
            print(f'  0x{op:02x}: {count}')
        print()
        print('Bytes 0-64:', ' '.join(f'{b:02x}' for b in text_data[:64]))
