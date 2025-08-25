import subprocess
import importlib
import sys

required_modules = ['keyboard', 'win32gui', 'win32con', 'pycaw', 'comtypes', 'psutil']

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

from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize
import win32gui, win32con
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import keyboard
import winsound
import random
import time
from ctypes import cast, POINTER
import atexit

def minimiseWindow():
    win = win32gui.GetForegroundWindow()
    win32gui.ShowWindow(win, win32con.SW_HIDE)

def modifyVolume(inputVolume):
    try:
        CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(0, None)
        volume.SetMasterVolumeLevelScalar(inputVolume, None)
    except Exception as e:
        print(f"Error modifying volume: {e}")
    finally:
        try:
            CoUninitialize()
        except:
            pass

def make_key_handler():
    limit = 0
    limit2 = 0
    com_initialized = False

    def on_key_event(event):
        nonlocal limit, limit2, com_initialized

        if not com_initialized:
            try:
                CoInitialize()
                com_initialized = True
            except Exception as e:
                print(f"Error initializing COM: {e}")
                return

        try:
            modifyVolume(1)

            if event.event_type == 'down':
                if event.name == 'space':
                    if limit2 == 0:
                        if random.random() < 0.1:
                            winsound.MessageBeep(winsound.MB_ICONHAND)
                            limit2 += 1
                    else:
                        limit2 += 1
                        if limit2 >= 10:
                            limit2 = 0
                else:
                    if limit == 0:
                        if random.random() < 0.05:
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                            limit = 1
                    else:
                        limit += 1
                        if limit >= 10:
                            limit = 0
        except Exception as e:
            print(f"Error in key handler: {e}")

    return on_key_event

def cleanup():
    try:
        CoUninitialize()
    except:
        pass

if __name__ == "__main__":
    #minimiseWindow()
    atexit.register(cleanup)
    modifyVolume(1)
    keyboard.hook(make_key_handler())
    while True:
        time.sleep(1)