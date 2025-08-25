import subprocess
import importlib
import sys

required_modules = ['pyperclip', 'pyrect', 'mouseinfo', 'pygetwindow', 'pymsgbox', 'pyscreeze', 'pytweening', 'pyautogui', 'keyboard', 'pywin32']

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

import pyautogui
import threading
import keyboard
import win32api
import win32gui
import win32con
import pywintypes
import ctypes
import time
import os
import sys

global waitTime
waitTime = 14 # Timer + start time ≈ 4 seconds extra

os.system('cls')

keyboard.press_and_release("f11")

for i in range(500):
    keyboard.block_key(i)

def focus_console_window():
    try:
        hwnd = win32gui.GetForegroundWindow()
        current_pid = win32api.GetCurrentProcessId()
        thread_id = win32api.GetCurrentThreadId()

        console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()

        if hwnd != console_hwnd:
            win32gui.ShowWindow(console_hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(console_hwnd)

    except pywintypes.error as e:
        pass

def repeat_task():
    while True:
        focus_console_window()
        time.sleep(0.1)

threading.Thread(target=repeat_task, daemon=True).start()

def writeMessage(message, duration):
    for char in message:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(duration)

pyautogui.FAILSAFE = False
pos = pyautogui.position()

# Track the actual start time for the countdown - moved here after setup
countdown_start_time = time.time()
start_time = countdown_start_time

def freezeCursor():
    while time.time() - start_time < (waitTime * waitTime):
        pyautogui.moveTo(pos)

mouseThread = threading.Thread(target=freezeCursor)
mouseThread.daemon = True
mouseThread.start()

writeMessage("Whoops! ", 0.05)
time.sleep(0.5)
writeMessage("Looks like I've disabled your computer!", 0.04)
time.sleep(1.3)
os.system('cls')

# Handles adding extra spaces which overwrite extra characters when stdout.write output shortens
spaceCount = ""
for i in range(len(str(waitTime - 1))):
    if len(str(waitTime)) == 1:
        pass
    else:
        spaceCount += " "

# Calculate how much time has already elapsed
elapsed_time = time.time() - countdown_start_time
remaining_time = max(0, int(waitTime - elapsed_time))

writeMessage(f"\rThere are {remaining_time} seconds left until I let you use your computer :)", 0.04)

# Continue countdown based on actual elapsed time
while remaining_time > 0:
    sys.stdout.write(f"\rThere are {remaining_time} seconds left until I let you use your computer :){spaceCount}")
    sys.stdout.flush()
    time.sleep(1)
    remaining_time -= 1

for i in range(500):
    keyboard.unblock_key(i)