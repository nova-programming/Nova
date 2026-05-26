import struct

f = open('build_test_new.exe', 'rb')
data = f.read()
f.close()

e_lfanew = struct.unpack('<I', data[60:64])[0]
off = e_lfanew + 4
num_sections = struct.unpack('<H', data[off+2:off+4])[0]
siz_opt_hdr = struct.unpack('<H', data[off+16:off+18])[0]
opt_off = off + 20
sec_off = opt_off + siz_opt_hdr

for i in range(num_sections):
    s = sec_off + i * 40
    name = data[s:s+8].rstrip(b'\x00').decode()
    vsize = struct.unpack('<I', data[s+8:s+12])[0]
    raw_size = struct.unpack('<I', data[s+16:s+20])[0]
    raw_ptr = struct.unpack('<I', data[s+20:s+24])[0]
    print('[%s] raw_ptr=0x%x raw_size=%d vsize=%d' % (name, raw_ptr, raw_size, vsize))
    chunk = data[raw_ptr:raw_ptr + min(raw_size, 128)]
    hex_str = ' '.join('%02x' % b for b in chunk)
    print(hex_str)
    print()
