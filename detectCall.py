import ctypes
import ctypes.wintypes as wt
import threading
import time
import signal

kernel32 = ctypes.windll.kernel32

# ===== USER CONFIG =====
OFFSET_FROM_BASE = 0xd44ce  # Function offset
PROCESS_NAME = "GeometryDash.exe"
HIT_DEBOUNCE_MS = 100        # Debounce per thread
REENABLE_MS = 50             # Re-enable HW breakpoint after this delay
# ========================

# Toolhelp flags
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE  = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
TH32CS_SNAPTHREAD = 0x00000004

# Thread rights
THREAD_SUSPEND_RESUME = 0x0002
THREAD_GET_CONTEXT    = 0x0008
THREAD_SET_CONTEXT    = 0x0010

# Debugging constants
DBG_CONTINUE = 0x00010002
EXCEPTION_DEBUG_EVENT = 1
EXCEPTION_SINGLE_STEP = 0x80000004
CREATE_THREAD_DEBUG_EVENT = 2

MAX_PATH = 260
ptr_size = ctypes.sizeof(ctypes.c_void_p)
ULONG_PTR = ctypes.c_ulonglong if ptr_size == 8 else ctypes.c_uint
SIZE_T = ctypes.c_size_t
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Toolhelp structures
class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_char * MAX_PATH),
    ]

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
        ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD), ("hModule", wt.HMODULE),
        ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * MAX_PATH),
    ]

class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
        ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", wt.LONG), ("tpDeltaPri", wt.LONG),
        ("dwFlags", wt.DWORD),
    ]

# CONTEXT for debug registers
if ptr_size == 8:
    class CONTEXT(ctypes.Structure):
        _fields_ = [
            ("P1Home", ctypes.c_ulonglong), ("P2Home", ctypes.c_ulonglong), ("P3Home", ctypes.c_ulonglong),
            ("P4Home", ctypes.c_ulonglong), ("P5Home", ctypes.c_ulonglong), ("P6Home", ctypes.c_ulonglong),
            ("ContextFlags", wt.DWORD), ("MxCsr", wt.DWORD), 
            ("SegCs", wt.WORD), ("SegDs", wt.WORD), ("SegEs", wt.WORD),
            ("SegFs", wt.WORD), ("SegGs", wt.WORD), ("SegSs", wt.WORD), ("EFlags", wt.DWORD),
            ("Dr0", ctypes.c_ulonglong), ("Dr1", ctypes.c_ulonglong), ("Dr2", ctypes.c_ulonglong),
            ("Dr3", ctypes.c_ulonglong), ("Dr6", ctypes.c_ulonglong), ("Dr7", ctypes.c_ulonglong),
            ("Rax", ctypes.c_ulonglong), ("Rcx", ctypes.c_ulonglong), ("Rdx", ctypes.c_ulonglong),
            ("Rbx", ctypes.c_ulonglong), ("Rsp", ctypes.c_ulonglong), ("Rbp", ctypes.c_ulonglong),
            ("Rsi", ctypes.c_ulonglong), ("Rdi", ctypes.c_ulonglong),
            ("R8", ctypes.c_ulonglong), ("R9", ctypes.c_ulonglong), ("R10", ctypes.c_ulonglong),
            ("R11", ctypes.c_ulonglong), ("R12", ctypes.c_ulonglong), ("R13", ctypes.c_ulonglong),
            ("R14", ctypes.c_ulonglong), ("R15", ctypes.c_ulonglong), ("Rip", ctypes.c_ulonglong),
        ]
    CONTEXT_DEBUG_REGISTERS = 0x00010010
else:
    class CONTEXT(ctypes.Structure):
        _fields_ = [
            ("ContextFlags", wt.DWORD),
            ("Dr0", wt.DWORD), ("Dr1", wt.DWORD), ("Dr2", wt.DWORD), ("Dr3", wt.DWORD),
            ("Dr6", wt.DWORD), ("Dr7", wt.DWORD), ("EFlags", wt.DWORD),
            ("Eax", wt.DWORD), ("Ecx", wt.DWORD), ("Edx", wt.DWORD), ("Ebx", wt.DWORD),
            ("Esp", wt.DWORD), ("Ebp", wt.DWORD), ("Esi", wt.DWORD), ("Edi", wt.DWORD),
            ("Eip", wt.DWORD),
        ]
    CONTEXT_DEBUG_REGISTERS = 0x00010010

# Globals
target_pid = None
target_address = None
stop_flag = threading.Event()
last_hit_time = {}
reenable_timers = {}
state_lock = threading.Lock()

# ===== Helpers =====
def find_process_by_name(name):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE: raise OSError("Snapshot failed")
    try:
        pe = PROCESSENTRY32(); pe.dwSize = ctypes.sizeof(pe); pid=None
        if kernel32.Process32First(snap, ctypes.byref(pe)):
            while True:
                exe = bytes(pe.szExeFile).split(b'\x00',1)[0].decode(errors='ignore')
                if exe.lower()==name.lower(): pid=pe.th32ProcessID; break
                if not kernel32.Process32Next(snap, ctypes.byref(pe)): break
        return pid
    finally: kernel32.CloseHandle(snap)

def get_module_base_address(pid):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap==INVALID_HANDLE_VALUE: raise OSError("Snapshot failed")
    try:
        me = MODULEENTRY32(); me.dwSize = ctypes.sizeof(me)
        if kernel32.Module32First(snap, ctypes.byref(me)):
            return me.modBaseAddr
    finally: kernel32.CloseHandle(snap)

def enum_threads(pid):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snap==INVALID_HANDLE_VALUE: raise OSError("Thread snapshot failed")
    try:
        te = THREADENTRY32(); te.dwSize=ctypes.sizeof(te); threads=[]
        if kernel32.Thread32First(snap, ctypes.byref(te)):
            while True:
                if te.th32OwnerProcessID==pid: threads.append(te.th32ThreadID)
                if not kernel32.Thread32Next(snap, ctypes.byref(te)): break
        return threads
    finally: kernel32.CloseHandle(snap)

def set_dr0_dr7_for_thread(tid, addr, enable=True):
    h = kernel32.OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_SET_CONTEXT, False, tid)
    if not h: return False
    try:
        kernel32.SuspendThread(h)
        ctx=CONTEXT(); ctx.ContextFlags=CONTEXT_DEBUG_REGISTERS
        if not kernel32.GetThreadContext(h, ctypes.byref(ctx)):
            kernel32.ResumeThread(h); return False
        if ptr_size == 8:
            ctx.Dr0 = ctypes.c_ulonglong(addr) if enable else ctypes.c_ulonglong(0)
            if enable:
                ctx.Dr7 |= 1
            else:
                ctx.Dr7 &= ~1
        else:
            ctx.Dr0 = ctypes.c_uint(addr) if enable else ctypes.c_uint(0)
            if enable:
                ctx.Dr7 |= 1
            else:
                ctx.Dr7 &= ~1
        kernel32.SetThreadContext(h, ctypes.byref(ctx))
        kernel32.ResumeThread(h)
        return True
    finally: kernel32.CloseHandle(h)

def install_hw_breakpoints_on_all_threads(pid, addr):
    for t in enum_threads(pid): set_dr0_dr7_for_thread(t, addr, True)

def clear_hw_breakpoints_on_all_threads(pid):
    for t in enum_threads(pid): set_dr0_dr7_for_thread(t, 0, False)

def schedule_reenable(tid):
    def _reenable():
        with state_lock: reenable_timers.pop(tid,None); last_hit_time.pop(tid,None); set_dr0_dr7_for_thread(tid,int(target_address),True)
    t=threading.Timer(REENABLE_MS/1000.0,_reenable); t.daemon=True
    with state_lock: prev=reenable_timers.get(tid); 
    if prev: prev.cancel(); reenable_timers[tid]=t
    t.start()

def handle_exception_event(exc_addr, dbg_tid):
    now=time.time()*1000; tid=dbg_tid
    with state_lock:
        last=last_hit_time.get(tid,0)
        if (now-last)<HIT_DEBOUNCE_MS: return
        last_hit_time[tid]=now
    print("[+] Detected function call at 0x%X (thread %d)" % (int(exc_addr), tid))
    if set_dr0_dr7_for_thread(tid,0,False): schedule_reenable(tid)

def debug_event_loop(pid):
    class EX_REC(ctypes.Structure): _fields_=[("ExceptionCode",wt.DWORD),("ExceptionFlags",wt.DWORD),("ExceptionRecord",ctypes.c_void_p),("ExceptionAddress",ctypes.c_void_p),("NumberParameters",wt.DWORD),("ExceptionInformation",ULONG_PTR*15)]
    class EX_DBG(ctypes.Structure): _fields_=[("ExceptionRecord",EX_REC),("dwFirstChance",wt.DWORD)]
    class DBG_EVT_U(ctypes.Union): _fields_=[("Exception",EX_DBG)]
    class DBG_EVT(ctypes.Structure): _fields_=[("dwDebugEventCode",wt.DWORD),("dwProcessId",wt.DWORD),("dwThreadId",wt.DWORD),("u",DBG_EVT_U)]
    evt=DBG_EVT()
    while not stop_flag.is_set():
        if not kernel32.WaitForDebugEvent(ctypes.byref(evt),1000): continue
        try:
            if evt.dwDebugEventCode==EXCEPTION_DEBUG_EVENT:
                exc=evt.u.Exception.ExceptionRecord; tid=evt.dwThreadId
                if exc.ExceptionCode==EXCEPTION_SINGLE_STEP and int(exc.ExceptionAddress)==int(target_address):
                    handle_exception_event(exc.ExceptionAddress, tid)
            elif evt.dwDebugEventCode==CREATE_THREAD_DEBUG_EVENT:
                set_dr0_dr7_for_thread(evt.dwThreadId,int(target_address),True)
        finally: kernel32.ContinueDebugEvent(evt.dwProcessId,evt.dwThreadId,DBG_CONTINUE)

def attach_debugger_and_watch(pid, addr):
    global target_pid,target_address
    target_pid=pid; target_address=addr
    if not kernel32.DebugActiveProcess(pid): raise OSError("DebugActiveProcess failed")
    install_hw_breakpoints_on_all_threads(pid, addr)
    try: debug_event_loop(pid)
    finally:
        with state_lock:
            for t in list(reenable_timers.values()): t.cancel()
            reenable_timers.clear(); last_hit_time.clear()
        clear_hw_breakpoints_on_all_threads(pid)
        kernel32.DebugActiveProcessStop(pid)
        print("[*] Detached and cleaned up")

def handle_exit(sig, frame): stop_flag.set()

def main():
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    pid=find_process_by_name(PROCESS_NAME)
    if not pid: print("ERROR: process not found."); return
    base=get_module_base_address(pid)
    if not base: print("ERROR: base not found."); return
    addr=int(base)+OFFSET_FROM_BASE
    print("[*] PID %d, base 0x%X, watching 0x%X" % (pid,int(base),addr))
    attach_debugger_and_watch(pid,addr)

if __name__=="__main__": main()