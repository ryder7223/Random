_L = 'ignore'
_K = 'Snapshot failed'
_J = 'EFlags'
_I = 'ContextFlags'
_H = 'dwFlags'
_G = 'th32ModuleID'
_F = 'th32ProcessID'
_E = 'cntUsage'
_D = 'dwSize'
_C = None
_B = True
_A = False

import ctypes, ctypes.wintypes as wt, threading, time, signal

kernel32 = ctypes.windll.kernel32

OFFSET_FROM_BASE = 0x3a37c0
PROCESS_NAME = 'GeometryDash.exe'
HIT_DEBOUNCE_MS = 100
REENABLE_MS = 50

TH32CS_SNAPPROCESS = 2
TH32CS_SNAPMODULE = 8
TH32CS_SNAPMODULE32 = 16
TH32CS_SNAPTHREAD = 4

THREAD_GET_CONTEXT = 8
THREAD_SET_CONTEXT = 16
THREAD_QUERY_INFORMATION = 64

DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001

EXCEPTION_DEBUG_EVENT = 1
EXCEPTION_SINGLE_STEP = 0x80000004
CREATE_THREAD_DEBUG_EVENT = 2

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400

MAX_PATH = 260
ptr_size = ctypes.sizeof(ctypes.c_void_p)
ULONG_PTR = ctypes.c_ulonglong if ptr_size == 8 else ctypes.c_uint
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        (_D, wt.DWORD), (_E, wt.DWORD), (_F, wt.DWORD),
        ('th32DefaultHeapID', ctypes.c_void_p), (_G, wt.DWORD),
        ('cntThreads', wt.DWORD), ('th32ParentProcessID', wt.DWORD),
        ('pcPriClassBase', ctypes.c_long), (_H, wt.DWORD),
        ('szExeFile', ctypes.c_char * MAX_PATH)
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        (_D, wt.DWORD), (_G, wt.DWORD), (_F, wt.DWORD),
        ('GlblcntUsage', wt.DWORD), ('ProccntUsage', wt.DWORD),
        ('modBaseAddr', ctypes.c_void_p), ('modBaseSize', wt.DWORD),
        ('hModule', wt.HMODULE),
        ('szModule', ctypes.c_char * 256), ('szExePath', ctypes.c_char * MAX_PATH)
    ]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        (_D, wt.DWORD), (_E, wt.DWORD), ('th32ThreadID', wt.DWORD),
        ('th32OwnerProcessID', wt.DWORD),
        ('tpBasePri', wt.LONG), ('tpDeltaPri', wt.LONG), (_H, wt.DWORD)
    ]


if ptr_size == 8:
    class CONTEXT(ctypes.Structure):
        _fields_ = [
            ('P1Home', ctypes.c_ulonglong), ('P2Home', ctypes.c_ulonglong),
            ('P3Home', ctypes.c_ulonglong), ('P4Home', ctypes.c_ulonglong),
            ('P5Home', ctypes.c_ulonglong), ('P6Home', ctypes.c_ulonglong),
            (_I, wt.DWORD), ('MxCsr', wt.DWORD),
            ('SegCs', wt.WORD), ('SegDs', wt.WORD), ('SegEs', wt.WORD),
            ('SegFs', wt.WORD), ('SegGs', wt.WORD), ('SegSs', wt.WORD),
            (_J, wt.DWORD),
            ('Dr0', ctypes.c_ulonglong), ('Dr1', ctypes.c_ulonglong),
            ('Dr2', ctypes.c_ulonglong), ('Dr3', ctypes.c_ulonglong),
            ('Dr6', ctypes.c_ulonglong), ('Dr7', ctypes.c_ulonglong),
            ('Rax', ctypes.c_ulonglong), ('Rcx', ctypes.c_ulonglong),
            ('Rdx', ctypes.c_ulonglong), ('Rbx', ctypes.c_ulonglong),
            ('Rsp', ctypes.c_ulonglong), ('Rbp', ctypes.c_ulonglong),
            ('Rsi', ctypes.c_ulonglong), ('Rdi', ctypes.c_ulonglong),
            ('R8', ctypes.c_ulonglong), ('R9', ctypes.c_ulonglong),
            ('R10', ctypes.c_ulonglong), ('R11', ctypes.c_ulonglong),
            ('R12', ctypes.c_ulonglong), ('R13', ctypes.c_ulonglong),
            ('R14', ctypes.c_ulonglong), ('R15', ctypes.c_ulonglong),
            ('Rip', ctypes.c_ulonglong),
        ]
    CONTEXT_DEBUG_REGISTERS = 0x10010
else:
    class CONTEXT(ctypes.Structure):
        _fields_ = [
            (_I, wt.DWORD),
            ('Dr0', wt.DWORD), ('Dr1', wt.DWORD), ('Dr2', wt.DWORD), ('Dr3', wt.DWORD),
            ('Dr6', wt.DWORD), ('Dr7', wt.DWORD), (_J, wt.DWORD),
            ('Eax', wt.DWORD), ('Ecx', wt.DWORD), ('Edx', wt.DWORD), ('Ebx', wt.DWORD),
            ('Esp', wt.DWORD), ('Ebp', wt.DWORD), ('Esi', wt.DWORD), ('Edi', wt.DWORD),
            ('Eip', wt.DWORD),
        ]
    CONTEXT_DEBUG_REGISTERS = 0x10010


target_pid = _C
target_address = _C
stop_flag = threading.Event()
last_hit_time = {}
reenable_timers = {}
state_lock = threading.Lock()


def detect_wow64(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, _A, pid)
    if not h:
        return _A
    try:
        is_wow64 = wt.BOOL()
        if not kernel32.IsWow64Process(h, ctypes.byref(is_wow64)):
            return _A
        return bool(is_wow64.value)
    finally:
        kernel32.CloseHandle(h)


def find_process_by_name(name):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        raise OSError(_K)
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(pe)
        pid = _C
        if kernel32.Process32First(snap, ctypes.byref(pe)):
            while _B:
                exe = bytes(pe.szExeFile).split(b'\x00', 1)[0].decode(errors=_L)
                if exe.lower() == name.lower():
                    pid = pe.th32ProcessID
                    break
                if not kernel32.Process32Next(snap, ctypes.byref(pe)):
                    break
        return pid
    finally:
        kernel32.CloseHandle(snap)


def get_module_base_address(pid, module_name=_C):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == INVALID_HANDLE_VALUE:
        raise OSError(_K)
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(me)
        if kernel32.Module32First(snap, ctypes.byref(me)):
            while _B:
                mod_name = bytes(me.szModule).split(b'\x00', 1)[0].decode(errors=_L)
                if module_name is _C or mod_name.lower() == module_name.lower():
                    return me.modBaseAddr
                if not kernel32.Module32Next(snap, ctypes.byref(me)):
                    break
        return
    finally:
        kernel32.CloseHandle(snap)


def enum_threads(pid):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snap == INVALID_HANDLE_VALUE:
        raise OSError('Thread snapshot failed')
    try:
        te = THREADENTRY32()
        te.dwSize = ctypes.sizeof(te)
        threads = []
        if kernel32.Thread32First(snap, ctypes.byref(te)):
            while _B:
                if te.th32OwnerProcessID == pid:
                    threads.append(te.th32ThreadID)
                if not kernel32.Thread32Next(snap, ctypes.byref(te)):
                    break
        return threads
    finally:
        kernel32.CloseHandle(snap)


def set_dr0_dr7_for_thread(tid, addr, enable=_B):
    THREAD_ACCESS = THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_QUERY_INFORMATION
    h = kernel32.OpenThread(THREAD_ACCESS, _A, tid)
    if not h:
        return _A
    try:
        if IS_WOW64_TARGET:
            ctx32 = CONTEXT()
            ctx32.ContextFlags = CONTEXT_DEBUG_REGISTERS
            if not kernel32.Wow64GetThreadContext(h, ctypes.byref(ctx32)):
                return _A
            if enable:
                ctx32.Dr0 = addr & 0xFFFFFFFF
                ctx32.Dr7 |= 1
            else:
                ctx32.Dr0 = 0
                ctx32.Dr7 &= ~1
            if not kernel32.Wow64SetThreadContext(h, ctypes.byref(ctx32)):
                return _A
        else:
            ctx = CONTEXT()
            ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS
            if not kernel32.GetThreadContext(h, ctypes.byref(ctx)):
                return _A
            if ptr_size == 8:
                ctx.Dr0 = int(addr) if enable else 0
                ctx.Dr7 = ctx.Dr7 | 1 if enable else ctx.Dr7 & ~1
            else:
                ctx.Dr0 = int(addr) if enable else 0
                ctx.Dr7 = ctx.Dr7 | 1 if enable else ctx.Dr7 & ~1
            if not kernel32.SetThreadContext(h, ctypes.byref(ctx)):
                return _A
        return _B
    finally:
        kernel32.CloseHandle(h)


def install_hw_breakpoints_on_all_threads(pid, addr):
    for t in enum_threads(pid):
        set_dr0_dr7_for_thread(t, addr, _B)


def clear_hw_breakpoints_on_all_threads(pid):
    for t in enum_threads(pid):
        set_dr0_dr7_for_thread(t, 0, _A)


def schedule_reenable(tid):
    def _reenable():
        with state_lock:
            reenable_timers.pop(tid, _C)
            last_hit_time.pop(tid, _C)
            set_dr0_dr7_for_thread(tid, int(target_address), _B)

    t = threading.Timer(REENABLE_MS / 1e3, _reenable)
    t.daemon = _B
    with state_lock:
        prev = reenable_timers.get(tid)
    if prev:
        prev.cancel()
    reenable_timers[tid] = t
    t.start()


def handle_exception_event(exc_addr, dbg_tid):
    now = time.time() * 1000
    tid = dbg_tid
    with state_lock:
        last = last_hit_time.get(tid, 0)
        if now - last < HIT_DEBOUNCE_MS:
            return
        last_hit_time[tid] = now
    print('[+] Detected function call at 0x%X (thread %d)' % (int(exc_addr), tid))
    if set_dr0_dr7_for_thread(tid, 0, _A):
        schedule_reenable(tid)


def debug_event_loop(pid):
    class EX_REC(ctypes.Structure):
        _fields_ = [
            ('ExceptionCode', wt.DWORD),
            ('ExceptionFlags', wt.DWORD),
            ('ExceptionRecord', ctypes.c_void_p),
            ('ExceptionAddress', ctypes.c_void_p),
            ('NumberParameters', wt.DWORD),
            ('ExceptionInformation', ULONG_PTR * 15)
        ]

    class EX_DBG(ctypes.Structure):
        _fields_ = [('ExceptionRecord', EX_REC), ('dwFirstChance', wt.DWORD)]

    class DBG_EVT_U(ctypes.Union):
        _fields_ = [('Exception', EX_DBG)]

    class DBG_EVT(ctypes.Structure):
        _fields_ = [
            ('dwDebugEventCode', wt.DWORD),
            ('dwProcessId', wt.DWORD),
            ('dwThreadId', wt.DWORD),
            ('u', DBG_EVT_U)
        ]

    evt = DBG_EVT()
    seen_other = {}

    while not stop_flag.is_set():
        if not kernel32.WaitForDebugEvent(ctypes.byref(evt), 1000):
            continue
        try:
            code = evt.dwDebugEventCode
            tid = evt.dwThreadId
            status = DBG_CONTINUE

            if code == EXCEPTION_DEBUG_EVENT:
                exc = evt.u.Exception.ExceptionRecord
                exc_code = exc.ExceptionCode
                exc_addr = int(ctypes.cast(exc.ExceptionAddress, ctypes.c_void_p).value or 0)

                if exc_code == EXCEPTION_SINGLE_STEP:
                    if exc_addr == int(target_address):
                        handle_exception_event(exc_addr, tid)
                    status = DBG_CONTINUE
                else:
                    cnt = seen_other.get(exc_code, 0)
                    if cnt < 3:
                        #print(f"[dbg] OTHER_EXCEPTION code=0x{exc_code:08X} addr=0x{exc_addr:X} tid={tid} firstchance={evt.u.Exception.dwFirstChance}")
                        pass
                    seen_other[exc_code] = cnt + 1
                    status = DBG_EXCEPTION_NOT_HANDLED

            elif code == CREATE_THREAD_DEBUG_EVENT:
                set_dr0_dr7_for_thread(evt.dwThreadId, int(target_address), _B)

            kernel32.ContinueDebugEvent(evt.dwProcessId, evt.dwThreadId, status)
        except Exception:
            kernel32.ContinueDebugEvent(evt.dwProcessId, evt.dwThreadId, DBG_EXCEPTION_NOT_HANDLED)


def attach_debugger_and_watch(pid, addr):
    global target_pid, target_address
    target_pid = pid
    target_address = addr
    if not kernel32.DebugActiveProcess(pid):
        raise OSError('DebugActiveProcess failed')
    install_hw_breakpoints_on_all_threads(pid, addr)
    try:
        debug_event_loop(pid)
    finally:
        with state_lock:
            for t in list(reenable_timers.values()):
                t.cancel()
            reenable_timers.clear()
            last_hit_time.clear()
        clear_hw_breakpoints_on_all_threads(pid)
        kernel32.DebugActiveProcessStop(pid)
        print('[*] Detached and cleaned up')


def handle_exit(sig, frame):
    stop_flag.set()


def main():
    module = 'GeometryDash.exe'
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    pid = find_process_by_name(PROCESS_NAME)
    if not pid:
        print('ERROR: process not found.')
        return
    global IS_WOW64_TARGET
    IS_WOW64_TARGET = detect_wow64(pid)
    print('[*] Target is WOW64 (32-bit)?:', IS_WOW64_TARGET)
    base = get_module_base_address(pid, module)
    if not base:
        print(f'ERROR: {module} not found.')
        return
    addr = int(base) + OFFSET_FROM_BASE
    print(f'[*] PID %d, {module} base 0x%X, watching 0x%X' % (pid, int(base), addr))
    attach_debugger_and_watch(pid, addr)


if __name__ == '__main__':
    IS_WOW64_TARGET = _A
    main()