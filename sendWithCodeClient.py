# 1.0

import subprocess
import importlib
import sys

requiredModules = ['requests']
def installMissingModules(modules):
    pip = 'pip'
    try:
        importlib.import_module(pip)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

installMissingModules(requiredModules)

import requests
import os
import time
import re
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

def checkForUpdate(force: int):
    localFile = os.path.abspath(__file__)
    repoUrl = "https://raw.githubusercontent.com/ryder7223/Random/refs/heads/main/sendWithCodeClient.py"
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
        os.execv(sys.executable, [sys.executable] + sys.argv)

import shlex, zipfile, shutil, tempfile, time, threading

serverUrl = "https://simple-tunes-singer-consultancy.trycloudflare.com"

cancelFlag = False
runHeartbeat = False
senderToken = None  # Will store token assigned by server

def pause():
    try: input("Press Enter to continue...")
    except EOFError: pass

def clear():
    try: os.system("cls")
    except: pass

def zipPath(sourcePath):
    tmp = tempfile.mkdtemp()
    zipFile = os.path.join(tmp, "upload.zip")
    with zipfile.ZipFile(zipFile, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.isfile(sourcePath):
            zipf.write(sourcePath, os.path.basename(sourcePath))
        else:
            for root, _, files in os.walk(sourcePath):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, os.path.dirname(sourcePath))
                    zipf.write(full, rel)
    return zipFile, tmp

def heartbeatThread(code, token):
    global runHeartbeat
    while runHeartbeat:
        try:
            requests.post(serverUrl + f"/heartbeat/{code}", timeout=5, data={"token": token})
        except:
            pass
        time.sleep(10)

def cancelWatcher(code, token):
    global cancelFlag, runHeartbeat
    try:
        input()
        cancelFlag = True
        runHeartbeat = False
        try:
            requests.delete(serverUrl + f"/cleanup/{code}?token={token}")
        except:
            pass
    except EOFError:
        pass

def sendMode(kind, path):
    global cancelFlag, runHeartbeat, senderToken
    cancelFlag = False
    runHeartbeat = False
    senderToken = None

    if not os.path.exists(path):
        print("Path not found")
        pause()
        return

    print("Zipping...")
    zipFile, tmp = zipPath(path)

    with open(zipFile, "rb") as f:
        r = requests.post(serverUrl + "/send",
            data={"itemType": kind},
            files={"file": f}
        )
    shutil.rmtree(tmp)

    if r.status_code != 200:
        print("Error sending")
        pause()
        return

    code = r.json()["code"]
    senderToken = r.json()["token"]  # store token assigned by server
    print("Code:", code)
    print("Waiting. Press Enter to cancel or exit.")

    runHeartbeat = True
    threading.Thread(target=heartbeatThread, args=(code, senderToken), daemon=True).start()
    threading.Thread(target=cancelWatcher, args=(code, senderToken), daemon=True).start()

    try:
        while True:
            if cancelFlag:
                print("Cancelled.")
                time.sleep(1)
                return
            time.sleep(2)
    except KeyboardInterrupt:
        runHeartbeat = False
        try:
            requests.delete(serverUrl + f"/cleanup/{code}?token={senderToken}")
        except:
            pass
        return

def receiveMode(code):
    url = serverUrl + "/receive/" + code
    r = requests.get(url, stream=True)

    if r.status_code != 200:
        print("Transfer failed")
        pause()
        return

    tmp = tempfile.mkdtemp()
    zipFile = os.path.join(tmp, "recv.zip")

    with open(zipFile, "wb") as f:
        for chunk in r.iter_content(4096):
            f.write(chunk)

    print("Extracting...")
    with zipfile.ZipFile(zipFile, 'r') as zipf:
        zipf.extractall(".")

    shutil.rmtree(tmp)
    print("Transfer complete")
    pause()

def parseCommand(cmd):
    parts = shlex.split(cmd)
    if not parts: return
    act = parts[0].lower()

    if act in ("send", "s"):
        if len(parts) < 3:
            print("Usage: send file|folder path")
            pause()
            return
        kind = parts[1].lower()
        path = parts[2]
        sendMode(kind, path)
        return

    if act in ("receive", "r"):
        if len(parts) < 2:
            print("Usage: receive CODE")
            pause()
            return
        receiveMode(parts[1])
        return

    print("Unknown command")
    pause()

if __name__ == "__main__":
    checkForUpdate(0)
    try:
        while True:
            clear()
            cmd = input("Enter command: ").strip()
            parseCommand(cmd)
    except KeyboardInterrupt:
        print("Exiting...")