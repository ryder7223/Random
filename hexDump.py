import ctypes
import ctypes.wintypes as wintypes
import psutil
import sys

# Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
MAX_MODULE_NAME32 = 255

# Structs
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress',       ctypes.c_void_p),
        ('AllocationBase',    ctypes.c_void_p),
        ('AllocationProtect', wintypes.DWORD),
        ('RegionSize',        ctypes.c_size_t),
        ('State',             wintypes.DWORD),
        ('Protect',           wintypes.DWORD),
        ('Type',              wintypes.DWORD),
    ]

class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wintypes.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]

# Load DLLs
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('Psapi', use_last_error=True)

# Function pointers
OpenProcess = kernel32.OpenProcess
CloseHandle = kernel32.CloseHandle
VirtualQueryEx = kernel32.VirtualQueryEx
ReadProcessMemory = kernel32.ReadProcessMemory

EnumProcessModules = psapi.EnumProcessModules
GetModuleBaseName = psapi.GetModuleBaseNameA
GetModuleInformation = psapi.GetModuleInformation

def list_modules(process_handle):
    hMods = (ctypes.c_void_p * 1024)()
    cbNeeded = ctypes.c_ulong()
    if not EnumProcessModules(process_handle, hMods, ctypes.sizeof(hMods), ctypes.byref(cbNeeded)):
        raise ctypes.WinError(ctypes.get_last_error())

    module_count = cbNeeded.value // ctypes.sizeof(ctypes.c_void_p)
    modules = []

    for i in range(module_count):
        hMod = hMods[i]
        mod_name = ctypes.create_string_buffer(MAX_MODULE_NAME32)
        hMod_casted = ctypes.cast(hMod, wintypes.HMODULE)
        GetModuleBaseName(process_handle, hMod_casted, mod_name, MAX_MODULE_NAME32)

        mod_info = MODULEINFO()
        GetModuleInformation(process_handle, hMod_casted, ctypes.byref(mod_info), ctypes.sizeof(mod_info))

        modules.append({
            'name': mod_name.value.decode(),
            'base': mod_info.lpBaseOfDll,
            'size': mod_info.SizeOfImage
        })

    return modules

def dump_memory(pid, output_file, module_name=None):
    process_handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not process_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    filter_range = None
    if module_name:
        modules = list_modules(process_handle)
        selected = next((m for m in modules if m['name'].lower() == module_name.lower()), None)
        if not selected:
            print(f"Module '{module_name}' not found.")
            CloseHandle(process_handle)
            return
        base = selected['base']
        end = base + selected['size']
        filter_range = (base, end)
        print(f"Dumping module: {module_name} from 0x{base:08X} to 0x{end:08X}")

    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    with open(output_file, "w") as f:
        while True:
            result = VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi))
            if result == 0:
                break  # No more memory regions to query

            if mbi.BaseAddress is None or mbi.RegionSize == 0:
                address += 0x1000  # Move by one page if something's wrong
                continue

            region_start = int(mbi.BaseAddress)
            region_end = region_start + mbi.RegionSize

            # Apply module range filter if specified
            if filter_range:
                if region_end <= filter_range[0] or region_start >= filter_range[1]:
                    address = region_end
                    continue

            if mbi.State == MEM_COMMIT and not (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)):
                buffer = ctypes.create_string_buffer(mbi.RegionSize)
                bytesRead = ctypes.c_size_t()
                if ReadProcessMemory(process_handle, ctypes.c_void_p(region_start), buffer, mbi.RegionSize, ctypes.byref(bytesRead)):
                    hex_data = buffer.raw[:bytesRead.value].hex()
                    f.write(' '.join(hex_data[i:i+2] for i in range(0, len(hex_data), 2)) + '\n')

            address = region_end

    CloseHandle(process_handle)
    print(f"Memory dumped to {output_file}")

def list_processes():
    for proc in psutil.process_iter(['pid', 'name']):
        print(f"{proc.info['pid']:>6} {proc.info['name']}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: script.py <pid>")
        list_processes()
        sys.exit(1)

    pid = int(sys.argv[1])
    process_handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not process_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    modules = list_modules(process_handle)
    print("\nModules:")
    for i, mod in enumerate(modules):
        print(f"{i:2}: {mod['name']} (Base: 0x{mod['base']:08X}, Size: 0x{mod['size']:X})")

    print("\nOptions:")
    print("  [number] - Dump only this module")
    print("  a        - Dump all memory")
    choice = input("\nEnter your choice: ").strip()

    if choice.lower() == 'a':
        dump_memory(pid, "memory_dump.txt")
    elif choice.isdigit():
        idx = int(choice)
        if idx < len(modules):
            dump_memory(pid, "module_dump.txt", modules[idx]['name'])
        else:
            print("Invalid module index.")
    else:
        print("Invalid choice.")