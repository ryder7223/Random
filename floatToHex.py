import struct

def float_to_ieee754(value: float):
    # Pack as IEEE 754 single-precision
    packed = struct.pack('!f', value)  # big-endian
    hex_big_endian = packed.hex().upper()
    
    # Memory layout (little-endian, how it's stored in RAM)
    packed_le = struct.pack('<f', value)
    hex_memory = " ".join(f"{b:02x}" for b in packed_le)

    return hex_big_endian, hex_memory

# Example usage
num = 100.0
ieee_hex, memory_hex = float_to_ieee754(num)
print(f"Float: {num}")
print(f"IEEE 754 Hex (big-endian): {ieee_hex}")
print(f"Memory Representation (little-endian): {memory_hex}")