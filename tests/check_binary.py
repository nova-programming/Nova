import struct

with open('tests/test_shl_min.exe', 'rb') as f:
    data = f.read()

patterns = {
    'D3 E0': bytes([0xD3, 0xE0]),
    'C1 E0': bytes([0xC1, 0xE0]),
}

for name, pat in patterns.items():
    idx = data.find(pat)
    if idx >= 0:
        print(f'Found {name} at offset {idx} (0x{idx:x})')
        start = max(0, idx-8)
        end = min(len(data), idx+16)
        hex_str = ' '.join(f'{b:02x}' for b in data[start:end])
        print(f'  Context: {hex_str}')
    else:
        print(f'{name} NOT FOUND')
