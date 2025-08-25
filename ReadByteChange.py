# ReadByteChange.py -- corrected version
# Windows-only live memory change watcher (single-file).
# Fixes: SIZE_T definition, SYSTEM_INFO nested struct, pointer->int conversions.

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import sys
import time
import threading
import queue
from bisect import bisect_right
from collections import namedtuple
from typing import Dict, List, Tuple, Optional

# ---- Windows API bindings ----

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi    = ctypes.WinDLL('Psapi',    use_last_error=True)
SIZE_T = ctypes.c_size_t

# Constants
TH32CS_SNAPPROCESS   = 0x00000002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ      = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

MEM_COMMIT  = 0x1000
MEM_RESERVE = 0x2000
MEM_FREE    = 0x10000

PAGE_NOACCESS          = 0x01
PAGE_READONLY          = 0x02
PAGE_READWRITE         = 0x04
PAGE_WRITECOPY         = 0x08
PAGE_EXECUTE           = 0x10
PAGE_EXECUTE_READ      = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD             = 0x100
PAGE_NOCACHE           = 0x200
PAGE_WRITECOMBINE      = 0x400

MEM_IMAGE    = 0x1000000
MEM_MAPPED   = 0x40000
MEM_PRIVATE  = 0x20000

LIST_MODULES_DEFAULT = 0x0
LIST_MODULES_32BIT   = 0x01
LIST_MODULES_64BIT   = 0x02
LIST_MODULES_ALL     = 0x03

# ctypes.wintypes lacks SIZE_T; define it explicitly.
SIZE_T = ctypes.c_size_t

# Structures
class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wt.DWORD),
        ('cntUsage', wt.DWORD),
        ('th32ProcessID', wt.DWORD),
        ('th32DefaultHeapID', ctypes.POINTER(wt.ULONG)),
        ('th32ModuleID', wt.DWORD),
        ('cntThreads', wt.DWORD),
        ('th32ParentProcessID', wt.DWORD),
        ('pcPriClassBase', wt.LONG),
        ('dwFlags', wt.DWORD),
        ('szExeFile', wt.CHAR * wt.MAX_PATH),
    ]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', wt.LPVOID),
        ('AllocationBase', wt.LPVOID),
        ('AllocationProtect', wt.DWORD),
        ('RegionSize', SIZE_T),
        ('State', wt.DWORD),
        ('Protect', wt.DWORD),
        ('Type', wt.DWORD),
    ]

class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ('lpBaseOfDll', wt.LPVOID),
        ('SizeOfImage', wt.DWORD),
        ('EntryPoint', wt.LPVOID),
    ]

class _SYSTEM_INFO_STRUCT(ctypes.Structure):
    _fields_ = [
        ("wProcessorArchitecture", wt.WORD),
        ("wReserved", wt.WORD),
    ]

class SYSTEM_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("dwOemId", wt.DWORD),
        ("s", _SYSTEM_INFO_STRUCT),
    ]

class SYSTEM_INFO(ctypes.Structure):
    _fields_ = [
        ('u', SYSTEM_INFO_UNION),
        ('dwPageSize', wt.DWORD),
        ('lpMinimumApplicationAddress', wt.LPVOID),
        ('lpMaximumApplicationAddress', wt.LPVOID),
        ('dwActiveProcessorMask', wt.LPVOID),
        ('dwNumberOfProcessors', wt.DWORD),
        ('dwProcessorType', wt.DWORD),
        ('dwAllocationGranularity', wt.DWORD),
        ('wProcessorLevel', wt.WORD),
        ('wProcessorRevision', wt.WORD),
    ]

# Function prototypes
kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.CreateToolhelp32Snapshot.restype  = wt.HANDLE

kernel32.Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32First.restype  = wt.BOOL

kernel32.Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32Next.restype  = wt.BOOL

kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype  = wt.HANDLE

kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype  = wt.BOOL

kernel32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, SIZE_T, ctypes.POINTER(SIZE_T)]
kernel32.ReadProcessMemory.restype  = wt.BOOL

kernel32.VirtualQueryEx.argtypes = [wt.HANDLE, wt.LPCVOID, ctypes.POINTER(MEMORY_BASIC_INFORMATION), SIZE_T]
kernel32.VirtualQueryEx.restype  = SIZE_T

kernel32.GetSystemInfo.argtypes = [ctypes.POINTER(SYSTEM_INFO)]
kernel32.GetSystemInfo.restype  = None

psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.EnumProcessModulesEx.restype  = wt.BOOL

psapi.GetModuleInformation.argtypes = [wt.HANDLE, wt.HMODULE, ctypes.POINTER(MODULEINFO), wt.DWORD]
psapi.GetModuleInformation.restype  = wt.BOOL

psapi.GetModuleBaseNameA.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPSTR, wt.DWORD]
psapi.GetModuleBaseNameA.restype  = wt.DWORD

psapi.GetModuleFileNameExA.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPSTR, wt.DWORD]
psapi.GetModuleFileNameExA.restype  = wt.DWORD

# Helper types
Region = namedtuple('Region', 'base size protect state typ')
Module = namedtuple('Module', 'base size name path')

# Global filter state
filter_text = ""
filter_lock = threading.Lock()
reset_requested = False
ranked_mode = False
address_change_counts = {}  # Track how many times each address has changed
address_last_bytes = {}  # Track the last byte values for each address

def win_err(msg: str) -> RuntimeError:
    code = ctypes.get_last_error()
    return RuntimeError(f"{msg} (WinError {code})")

def check(cond, msg):
    if not cond:
        raise win_err(msg)

def is_windows() -> bool:
    return sys.platform == 'win32'

def input_handler():
    """Handle input in a separate thread for live filtering"""
    global filter_text, ranked_mode
    import msvcrt
    
    print("\nType to filter results (Backspace to erase, ESC to clear filter, * (numpad) to reset memory, - (numpad) to toggle ranked mode):")
    while True:
        try:
            ch = msvcrt.getwch()
            with filter_lock:
                if ch == '\x08':  # Backspace
                    if filter_text:
                        filter_text = filter_text[:-1]
                        print(f"\rFilter: '{filter_text}' | Ranked: {ranked_mode}" + " " * 20, end="\r")
                elif ch == '\x1b':  # ESC
                    filter_text = ""
                    print(f"\rFilter: '{filter_text}' | Ranked: {ranked_mode}" + " " * 20, end="\r")
                elif ch == '*':  # Numpad multiply
                    # Signal to reset reported addresses
                    global reset_requested
                    reset_requested = True
                    print(f"\rMemory reset requested! Filter: '{filter_text}' | Ranked: {ranked_mode}" + " " * 20, end="\r")
                elif ch == '-':  # Numpad subtract
                    # Toggle ranked mode
                    ranked_mode = not ranked_mode
                    print(f"\rRanked mode {'enabled' if ranked_mode else 'disabled'}! Filter: '{filter_text}' | Ranked: {ranked_mode}" + " " * 20, end="\r")
                elif ch.isprintable():
                    filter_text += ch
                    print(f"\rFilter: '{filter_text}' | Ranked: {ranked_mode}" + " " * 20, end="\r")
        except (KeyboardInterrupt, EOFError):
            break

# ---- Process enumeration & interactive selection ----

def list_processes() -> List[Tuple[int, str]]:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    check(snap != wt.HANDLE(-1).value, "CreateToolhelp32Snapshot failed")
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = kernel32.Process32First(snap, ctypes.byref(pe))
        if not ok:
            return []
        procs = []
        while ok:
            name = pe.szExeFile.split(b'\x00', 1)[0].decode(errors='replace')
            procs.append((int(pe.th32ProcessID), name))
            ok = kernel32.Process32Next(snap, ctypes.byref(pe))
        procs.sort(key=lambda x: (x[1].lower(), x[0]))
        return procs
    finally:
        kernel32.CloseHandle(snap)

def interactive_select_process() -> int:
    """
    Minimal interactive narrowing: type to filter, Backspace to erase,
    Enter to select if 1 match, or type the shown index number then Enter.
    """
    import msvcrt

    all_procs = list_processes()
    if not all_procs:
        raise RuntimeError("No processes found.")

    filter_text = ""
    selection_number_buffer = ""
    while True:
        # Filter
        fl = filter_text.lower()
        matches = [(i, pid, name) for i, (pid, name) in enumerate(all_procs) if fl in name.lower()]
        # Render
        sys.stdout.write("\x1b[2J\x1b[H")  # clear screen
        print("Select process (type to filter; Backspace to erase; Enter to select; or type index digits then Enter):")
        print(f"Filter: '{filter_text}'")
        print()
        shown = matches[:30]
        for local_idx, (i, pid, name) in enumerate(shown):
            print(f"{i:5d}  pid={pid:<7d}  {name}")
        if len(matches) > len(shown):
            print(f"... and {len(matches) - len(shown)} more")
        if selection_number_buffer:
            print(f"\nIndex buffer: {selection_number_buffer}")

        ch = msvcrt.getwch()
        if ch == '\r':  # Enter
            if selection_number_buffer:
                try:
                    idx = int(selection_number_buffer)
                    if 0 <= idx < len(all_procs):
                        return all_procs[idx][0]
                except ValueError:
                    pass
                selection_number_buffer = ""
            elif len(matches) == 1:
                return matches[0][1]
            else:
                print("Ambiguous selection. Type the index number then Enter, or refine the filter.")
                time.sleep(1.0)
        elif ch == '\x08':  # Backspace
            if selection_number_buffer:
                selection_number_buffer = selection_number_buffer[:-1]
            elif filter_text:
                filter_text = filter_text[:-1]
        elif ch == '\x1b':  # ESC clears
            filter_text = ""
            selection_number_buffer = ""
        elif ch.isdigit():
            selection_number_buffer += ch
        elif ch.isprintable():
            filter_text += ch
        # ignore other keys

# ---- Process open/attach ----

def open_process_for_reading(pid: int):
    access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    h = kernel32.OpenProcess(access, False, pid)
    if not h:
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    check(h != 0, f"OpenProcess failed for pid {pid}")
    return h

# ---- System info ----

def get_address_space_limits() -> Tuple[int, int]:
    si = SYSTEM_INFO()
    kernel32.GetSystemInfo(ctypes.byref(si))
    # lpMinimumApplicationAddress and lpMaximumApplicationAddress are LPVOID; convert to int
    lo = int(si.lpMinimumApplicationAddress)
    hi = int(si.lpMaximumApplicationAddress)
    return lo, hi

# ---- Module enumeration ----

def list_modules(hproc) -> List[Module]:
    needed = wt.DWORD(0)
    if not psapi.EnumProcessModulesEx(hproc, None, 0, ctypes.byref(needed), LIST_MODULES_ALL):
        raise win_err("EnumProcessModulesEx(need size) failed")
    count = needed.value // ctypes.sizeof(wt.HMODULE)
    if count == 0:
        return []
    arr = (wt.HMODULE * count)()
    if not psapi.EnumProcessModulesEx(hproc, arr, needed, ctypes.byref(needed), LIST_MODULES_ALL):
        raise win_err("EnumProcessModulesEx(list) failed")
    mods: List[Module] = []
    for hmod in arr:
        mi = MODULEINFO()
        if not psapi.GetModuleInformation(hproc, hmod, ctypes.byref(mi), ctypes.sizeof(mi)):
            continue
        name_buf = ctypes.create_string_buffer(wt.MAX_PATH)
        path_buf = ctypes.create_string_buffer(260 * 4)
        psapi.GetModuleBaseNameA(hproc, hmod, name_buf, len(name_buf))
        psapi.GetModuleFileNameExA(hproc, hmod, path_buf, len(path_buf))
        base  = int(mi.lpBaseOfDll)   # <-- convert pointer to int
        size  = int(mi.SizeOfImage)
        name  = name_buf.value.decode(errors='replace') or "???"
        path  = path_buf.value.decode(errors='replace') or ""
        mods.append(Module(base=base, size=size, name=name, path=path))
    mods.sort(key=lambda m: m.base)
    return mods

def make_module_locator(mods: List[Module]):
    bases = [m.base for m in mods]
    def locate(addr: int) -> Optional[Module]:
        i = bisect_right(bases, addr) - 1
        if i >= 0:
            m = mods[i]
            if addr < m.base + m.size:
                return m
        return None
    return locate

# ---- Memory region enumeration ----

READABLE_MASKS = (
    PAGE_READONLY, PAGE_READWRITE, PAGE_WRITECOPY,
    PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY
)

def is_readable_page(protect: int) -> bool:
    if protect & PAGE_GUARD:
        return False
    if protect in READABLE_MASKS:
        return True
    return False

def enumerate_regions(hproc, modules_only: bool) -> List[Region]:
    lo, hi = get_address_space_limits()
    regions: List[Region] = []
    addr = lo
    mbi = MEMORY_BASIC_INFORMATION()
    module_ranges: List[Tuple[int, int]] = []
    if modules_only:
        mods = list_modules(hproc)
        module_ranges = [(m.base, m.base + m.size) for m in mods]
    while addr < hi:
        res = kernel32.VirtualQueryEx(hproc, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if res == 0:
            addr += 0x1000
            continue
        base = int(mbi.BaseAddress)        # <-- use int() not cast to c_size_t
        size = int(mbi.RegionSize)
        prot = int(mbi.Protect)
        state = int(mbi.State)
        typ = int(mbi.Type)

        if state == MEM_COMMIT and is_readable_page(prot):
            if not modules_only:
                regions.append(Region(base, size, prot, state, typ))
            else:
                r0, r1 = base, base + size
                for m0, m1 in module_ranges:
                    a0 = max(r0, m0)
                    a1 = min(r1, m1)
                    if a1 > a0:
                        regions.append(Region(a0, a1 - a0, prot, state, typ))
        addr = base + size
    regions.sort(key=lambda r: r.base)
    coalesced: List[Region] = []
    for r in regions:
        if coalesced and (coalesced[-1].base + coalesced[-1].size == r.base) and (coalesced[-1].protect == r.protect):
            prev = coalesced[-1]
            coalesced[-1] = Region(prev.base, prev.size + r.size, prev.protect, prev.state, prev.typ)
        else:
            coalesced.append(r)
    return coalesced

# ---- Memory reading & change detection ----

def read_memory(hproc, addr: int, size: int) -> Optional[bytes]:
    buf = (ctypes.c_char * size)()
    read = SIZE_T(0)
    ok = kernel32.ReadProcessMemory(hproc, ctypes.c_void_p(addr), buf, size, ctypes.byref(read))
    if not ok:
        return None
    return bytes(buf[:read.value])

def chunk_hash(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()

def iter_region_chunks(base: int, size: int, chunk_size: int):
    off = 0
    while off < size:
        n = min(chunk_size, size - off)
        yield base + off, n
        off += n

def format_location(addr: int, locate_mod) -> str:
    m = locate_mod(addr) if locate_mod else None
    if m:
        return f"{m.name}+0x{addr - m.base:X}"
    return f"region+0x{addr:X}"

def diff_and_print(prev_bytes: bytes, curr_bytes: bytes, chunk_base: int, locate_mod, max_diffs: int) -> int:
    count = 0
    for i, (a, b) in enumerate(zip(prev_bytes, curr_bytes)):
        if a != b:
            loc = format_location(chunk_base + i, locate_mod)
            print(f"{loc}: 0x{a:02X} -> 0x{b:02X}")
            count += 1
            if max_diffs and count >= max_diffs:
                print(f"... diff limit reached ({max_diffs}), more changes suppressed")
                break
    return count

def diff_and_print_new_addresses(prev_bytes: bytes, curr_bytes: bytes, chunk_base: int, locate_mod, reported_addresses: set, max_diffs: int) -> int:
    global filter_text, ranked_mode, address_change_counts, address_last_bytes
    count = 0
    first_change_this_cycle = True
    changed_addresses_this_cycle = set()  # Track which addresses changed this cycle
    
    for i, (a, b) in enumerate(zip(prev_bytes, curr_bytes)):
        if a != b:
            addr = chunk_base + i
            loc = format_location(addr, locate_mod)
            # Only print if it's not a region+ address (i.e., it's within a loaded module)
            if not loc.startswith("region+"):
                # Check if the location matches the current filter
                with filter_lock:
                    current_filter = filter_text.lower()
                    current_ranked_mode = ranked_mode
                
                if not current_filter or current_filter in loc.lower():
                    if current_ranked_mode:
                        # Ranked mode: track change count and last byte values
                        if addr not in address_change_counts:
                            address_change_counts[addr] = 0
                        address_change_counts[addr] += 1
                        address_last_bytes[addr] = (a, b)  # Store the last change (from -> to)
                        changed_addresses_this_cycle.add(addr)
                    else:
                        # Normal mode: only show if not reported before
                        if addr not in reported_addresses:
                            # Print separator before first change in this cycle
                            if first_change_this_cycle:
                                print("-" * 80)
                                first_change_this_cycle = False
                            
                            print(f"{loc}: 0x{a:02X} -> 0x{b:02X}")
                            reported_addresses.add(addr)  # Mark this address as reported
                            count += 1
                            if max_diffs and count >= max_diffs:
                                print(f"... diff limit reached ({max_diffs}), more changes suppressed")
                                break
    
    # For ranked mode, print all addresses sorted by change count with last byte change
    if ranked_mode and changed_addresses_this_cycle:
        print("-" * 80)
        # Sort addresses by change count (descending) and then by address for stability
        sorted_addresses = sorted(address_change_counts.items(), 
                                key=lambda x: (-x[1], x[0]))  # Sort by count desc, then address asc
        
        for addr, change_count in sorted_addresses:
            loc = format_location(addr, locate_mod)
            if not current_filter or current_filter in loc.lower():
                if addr in address_last_bytes:
                    last_from, last_to = address_last_bytes[addr]
                    print(f"{change_count}: {loc}: 0x{last_from:02X} -> 0x{last_to:02X}")
                else:
                    print(f"{change_count}: {loc}")
                count += 1
                if max_diffs and count >= max_diffs:
                    print(f"... diff limit reached ({max_diffs}), more changes suppressed")
                    break
    
    return count

# ---- Main watch loop ----

def watch_process(pid: int, interval: float, chunk_size: int, modules_only: bool, max_diffs: int):
    hproc = open_process_for_reading(pid)
    try:
        try:
            mods = list_modules(hproc)
        except Exception:
            mods = []
        locate_mod = make_module_locator(mods) if mods else (lambda _addr: None)

        regions = enumerate_regions(hproc, modules_only=modules_only)
        total = sum(r.size for r in regions)
        print(f"Attached to pid {pid}. Scanning {'module-backed' if modules_only else 'all readable'} regions.")
        print(f"Regions: {len(regions)}, total bytes: {total:,}. Chunk size: {chunk_size}. Interval: {interval}s.")
        if not regions:
            print("No readable regions found with current options.")
            return

        snapshot: Dict[int, Tuple[bytes, bytes]] = {}
        reported_addresses = set()  # Track addresses that have already been reported

        for r in regions:
            for chunk_base, n in iter_region_chunks(r.base, r.size, chunk_size):
                data = read_memory(hproc, chunk_base, n)
                if data is None or len(data) == 0:
                    continue
                snapshot[chunk_base] = (chunk_hash(data), data)

        print("Initial snapshot complete. Watching for changes... Press Ctrl+C to stop.\n")
        
        # Start input handler thread for live filtering
        input_thread = threading.Thread(target=input_handler, daemon=True)
        input_thread.start()
        
        last_module_refresh = time.time()
        last_filter_check = time.time()
        filtered_regions = regions  # Start with all regions

        while True:
            if time.time() - last_module_refresh > 5.0:
                try:
                    mods = list_modules(hproc)
                    locate_mod = make_module_locator(mods) if mods else (lambda _addr: None)
                except Exception:
                    pass
                last_module_refresh = time.time()

            # Check if filter has changed and update regions accordingly
            if time.time() - last_filter_check > 0.1:  # Check every 100ms
                with filter_lock:
                    current_filter = filter_text.lower()
                
                if current_filter and modules_only:
                    # Filter modules based on current filter
                    filtered_mods = [m for m in mods if current_filter in m.name.lower()]
                    if filtered_mods:
                        # Create module ranges for filtered modules only
                        module_ranges = [(m.base, m.base + m.size) for m in filtered_mods]
                        filtered_regions = []
                        
                        # Get all regions and filter them
                        all_regions = enumerate_regions(hproc, modules_only=False)
                        for r in all_regions:
                            r0, r1 = r.base, r.base + r.size
                            for m0, m1 in module_ranges:
                                a0 = max(r0, m0)
                                a1 = min(r1, m1)
                                if a1 > a0:
                                    filtered_regions.append(Region(a0, a1 - a0, r.protect, r.state, r.typ))
                                    break
                    else:
                        # No modules match filter, use empty regions
                        filtered_regions = []
                else:
                    # No filter or not modules_only mode, use all regions
                    filtered_regions = enumerate_regions(hproc, modules_only=modules_only)
                
                last_filter_check = time.time()

            # Check for reset request
            global reset_requested, ranked_mode, address_change_counts, address_last_bytes
            if reset_requested:
                with filter_lock:
                    reset_requested = False
                if ranked_mode:
                    address_change_counts.clear()
                    address_last_bytes.clear()
                    print("\nRanked mode reset! All change counts and byte history cleared.")
                else:
                    reported_addresses.clear()
                    print("\nMemory reset! All addresses will be reported again.")
            
            diffs_this_cycle = 0
            for r in filtered_regions:
                for chunk_base, n in iter_region_chunks(r.base, r.size, chunk_size):
                    data = read_memory(hproc, chunk_base, n)
                    if data is None or len(data) == 0:
                        snapshot.pop(chunk_base, None)
                        continue
                    h = chunk_hash(data)
                    prev = snapshot.get(chunk_base)
                    if prev is None:
                        snapshot[chunk_base] = (h, data)
                        continue
                    prev_h, prev_bytes = prev
                    if h != prev_h:
                        # Only print diffs for addresses that haven't been reported before
                        new_addresses_found = diff_and_print_new_addresses(prev_bytes, data, chunk_base, locate_mod, reported_addresses, max_diffs=(0 if max_diffs is None else max(0, max_diffs - diffs_this_cycle)))
                        diffs_this_cycle += new_addresses_found
                        snapshot[chunk_base] = (h, data)
                        if max_diffs and diffs_this_cycle >= max_diffs:
                            break
                if max_diffs and diffs_this_cycle >= max_diffs:
                    break

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        kernel32.CloseHandle(hproc)

# ---- Bitness advisory ----

def bitness_advisory():
    try:
        IsWow64Process2 = getattr(kernel32, "IsWow64Process2", None)
        if IsWow64Process2:
            IsWow64Process2.argtypes = [wt.HANDLE, ctypes.POINTER(wt.USHORT), ctypes.POINTER(wt.USHORT)]
            IsWow64Process2.restype  = wt.BOOL
            p = kernel32.GetCurrentProcess()
            pProcessMachine = wt.USHORT(0)
            pNativeMachine  = wt.USHORT(0)
            if IsWow64Process2(p, ctypes.byref(pProcessMachine), ctypes.byref(pNativeMachine)):
                if pProcessMachine.value != 0:
                    print("Warning: You're running a 32-bit Python on a 64-bit OS. You may not be able to read 64-bit processes fully.")
    except Exception:
        pass

# ---- CLI ----

def parse_args():
    ap = argparse.ArgumentParser(description="Live memory change watcher with module mapping (Windows only).")
    ap.add_argument('--interval', type=float, default=0.5, help='Polling interval in seconds (default: 0.5)')
    ap.add_argument('--chunk', type=int, default=65536, help='Chunk size for hashing (default: 65536)')
    ap.add_argument('--modules-only', action='store_true', help='Only scan memory backed by loaded modules (EXE/DLL)')
    ap.add_argument('--max-diffs', type=int, default=500, help='Max diffs to print per cycle (0 = unlimited). Default: 500')
    ap.add_argument('--pid', type=int, default=None, help='Attach directly to a PID instead of interactive selection')
    return ap.parse_args()

def main():
    if not is_windows():
        print("This tool runs on Windows only.")
        sys.exit(1)
    args = parse_args()
    bitness_advisory()
    if args.pid is not None:
        pid = args.pid
    else:
        pid = interactive_select_process()
    max_diffs = None if args.max_diffs == 0 else max(1, args.max_diffs)
    watch_process(pid=pid, interval=max(0.05, args.interval), chunk_size=max(4096, args.chunk), modules_only=args.modules_only, max_diffs=max_diffs)

if __name__ == '__main__':
    main()