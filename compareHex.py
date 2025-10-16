import sys

def read_hex_file(path):
    with open(path, 'r') as f:
        hex_string = ''
        for line in f:
            line = line.strip().replace(' ', '')
            hex_string += line
        return bytes.fromhex(hex_string)

def compare_dumps(file1, file2):
    data1 = read_hex_file(file1)
    data2 = read_hex_file(file2)

    min_len = min(len(data1), len(data2))
    max_len = max(len(data1), len(data2))

    differences = []

    for i in range(min_len):
        if data1[i] != data2[i]:
            differences.append((i, data1[i], data2[i]))

    if len(data1) != len(data2):
        print(f"Warning: Files have different lengths ({len(data1)} vs {len(data2)}). Truncating comparison at {min_len} bytes.")

        # Append remaining differences
        longer_data = data1 if len(data1) > len(data2) else data2
        for i in range(min_len, max_len):
            differences.append((i, data1[i] if i < len(data1) else None, data2[i] if i < len(data2) else None))

    print(f"\nFound {len(differences)} differences:\n")
    for offset, byte1, byte2 in differences:
        b1 = f"{byte1:02X}" if byte1 is not None else "--"
        b2 = f"{byte2:02X}" if byte2 is not None else "--"
        print(f"Offset 0x{offset:08X}: {b1} -> {b2}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: compare_dumps.py <original_dump.txt> <modified_dump.txt>")
        sys.exit(1)

    compare_dumps(sys.argv[1], sys.argv[2])