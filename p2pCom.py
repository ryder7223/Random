# 1.2

import sys
import requests
import os
import time
import re
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

def checkForUpdate(force: int):
    localFile = os.path.abspath(__file__)
    repoUrl = "https://raw.githubusercontent.com/ryder7223/Random/refs/heads/main/p2pCom.py"
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


checkForUpdate(0)

import subprocess
import importlib

requiredModules = {
    "prompt_toolkit": {
        "package": "prompt_toolkit"
    },
    "cryptography": {
        "package": "cryptography"
    }
}

def installMissingModules(modules):
    installedSomething = False
    for importName, moduleInfo in modules.items():
        try:
            importlib.import_module(importName)
            
        except ImportError:
            packageName = moduleInfo["package"]
            extraArgs = moduleInfo.get("args", [])
            print(f"{packageName} is not installed. Installing...")
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                *extraArgs,
                packageName])
            installedSomething = True
    if installedSomething:
        subprocess.check_call([sys.executable] + sys.argv)
        sys.exit()

installMissingModules(requiredModules)

from typing import cast
import socket
import threading
import json
import uuid
import shutil
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from cryptography.fernet import Fernet

lastSize = shutil.get_terminal_size()
redrawEvent = threading.Event()

MESSAGE_PORT = 5000
DISCOVERY_PORT = 5001

PEER_TIMEOUT = 15
DISCOVERY_INTERVAL = 2
RESEND_INTERVAL = 2
HISTORY_CHUNK_SIZE = 50

SIGNATURE = "P2PMSG1"

def getIdentityKey():
    keyFile = "identity.key"

    if os.path.exists(keyFile):
        with open(keyFile, "rb") as file:
            return file.read()

    key = Fernet.generate_key()

    with open(keyFile, "wb") as file:
        file.write(key)

    return key


def generateId():
    identityFile = "identity.json.enc"

    cipher = Fernet(getIdentityKey())

    if os.path.exists(identityFile):
        try:
            with open(identityFile, "rb") as file:
                encrypted = file.read()

            data = cipher.decrypt(encrypted)
            identity = json.loads(data.decode())

            if "id" not in identity:
                raise ValueError()

            return identity["id"]

        except:
            print("Identity file invalid or corrupted.")
            sys.exit(1)

    identity = {
        "id": str(uuid.uuid4())[:8],
        "created": time.time()
    }

    encrypted = cipher.encrypt(
        json.dumps(identity).encode()
    )

    with open(identityFile, "wb") as file:
        file.write(encrypted)

    return identity["id"]

peerId = generateId()
nick = ""

peers = {}
messages = []
messageIds = set()
pendingPackets = {}
pendingHistory = {}
receivedHistory = {}

lock = threading.Lock()
running = True

session = PromptSession()

def getLocalIps():
    ips = {"127.0.0.1"}

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(cast(str, info[4][0]))
    except:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except:
        pass

    return ips

localIps = getLocalIps()

def clearScreen():
    os.system("cls" if os.name == "nt" else "clear")

def shortId(pid):
    return pid[:4]

def requestRedraw():
    redrawEvent.set()

def displayName(pid):
    if pid == peerId:
        base = nick or peerId
    elif pid in peers:
        base = peers[pid].get("nick") or pid
    else:
        base = pid

    return f"{base}#{shortId(pid)}"

def formatMessage(message):
    if len(message['text']) > 100:
        message['text'] = message['text'][:100]
    return f"[{displayName(message['sender'])}] {message['text']}"

def drawChat():
    with lock:
        clearScreen()
        names = [displayName(peerId)]

        for peer in peers.values():
            names.append(displayName(peer["id"]))

        print("Peers: " + ", ".join(names))
        print("-" * shutil.get_terminal_size().columns)
        height = shutil.get_terminal_size().lines - 4

        for message in messages[-height:]:
            print(formatMessage(message))

        print("-" * shutil.get_terminal_size().columns)

def redrawLoop():
    global lastSize

    while running:
        redrawEvent.wait(timeout=1)

        size = shutil.get_terminal_size()
        if size != lastSize:
            lastSize = size
        elif not redrawEvent.is_set():
            continue

        redrawEvent.clear()

        with patch_stdout():
            drawChat()

def addChat(sender, text, messageId=None, senderNick="", timestamp=None):
    if not messageId:
        messageId = str(uuid.uuid4())

    if timestamp is None:
        timestamp = time.time()

    if len(text) > 100:
        text = text[:100]

    with lock:
        if messageId in messageIds:
            return

        messageIds.add(messageId)
        messages.append({
            "id": messageId,
            "sender": sender,
            "nick": senderNick,
            "text": text,
            "timestamp": timestamp
        })

        messages.sort(key=lambda m: (m["timestamp"], m["id"]))

    requestRedraw()

def sendUdp(ip, packet, retry=False):
    packet["signature"] = SIGNATURE
    data = json.dumps(packet).encode()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(data, (ip, MESSAGE_PORT))
        s.close()

        if retry and packet.get("id"):
            with lock:
                pendingPackets[packet["id"]] = {"ip": ip,"packet": packet,"time": time.time()}

    except:
        pass

def broadcast(packet):
    with lock:
        targets = list(peers.values())

    for peer in targets:
        threading.Thread(target=sendUdp,args=(peer["ip"], packet, True),daemon=True).start()

def updatePeer(ip, pid, peerNick=""):
    if not pid or pid == peerId:
        return

    changed = False

    with lock:
        peer = peers.get(pid)

        if peer is None:
            peers[pid] = {
                "id": pid,
                "nick": peerNick,
                "ip": ip,
                "time": time.time()
            }
            changed = True
        else:
            if peer["ip"] != ip:
                peer["ip"] = ip
                changed = True

            if peer["nick"] != peerNick:
                peer["nick"] = peerNick
                changed = True

            peer["time"] = time.time()

    if changed:
        requestRedraw()

def sendDiscovery():
    sendBroadcast({"type": "discover","id": peerId,"nick": nick})

def sendBroadcast(packet):
    data = json.dumps({"signature": SIGNATURE,**packet}).encode()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(data, ("<broadcast>", DISCOVERY_PORT))
        s.close()
    except:
        pass

def sendDirect(ip, packet, port=MESSAGE_PORT):
    try:
        packet["signature"] = SIGNATURE
        data = json.dumps(packet).encode()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(data, (ip, port))
        s.close()

    except:
        pass

def discoveryResponse(ip):
    sendDirect(ip,{"type": "discoverResponse","id": peerId,"nick": nick},DISCOVERY_PORT)

def discoveryServer():
    server = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)

    try:
        server.bind(("0.0.0.0",DISCOVERY_PORT))
    except:
        return

    while running:
        try:
            data, addr = server.recvfrom(65535)
            packet = json.loads(data.decode())

            if packet.get("signature") != SIGNATURE:
                continue

            ip = addr[0]

            if ip in localIps:
                continue

            if packet.get("type") == "discover":
                updatePeer(ip, packet.get("id"), packet.get("nick", ""))
                discoveryResponse(ip)
            
                with lock:
                    alreadyPending = any(r["ip"] == ip for r in pendingHistory.values())
            
                if not alreadyPending:
                    historyId = str(uuid.uuid4())
            
                    with lock:
                        pendingHistory[historyId] = {
                            "ip": ip,
                            "time": time.time()
                        }
            
                    sendDirect(
                        ip,
                        {
                            "type": "historyRequest",
                            "id": peerId,
                            "requestId": historyId
                        }
                    )

            elif packet.get("type") == "discoverResponse":
                updatePeer(ip, packet.get("id"), packet.get("nick", ""))
            
                with lock:
                    alreadyPending = any(r["ip"] == ip for r in pendingHistory.values())
            
                if not alreadyPending:
                    historyId = str(uuid.uuid4())
            
                    with lock:
                        pendingHistory[historyId] = {
                            "ip": ip,
                            "time": time.time()
                        }
                
                    sendDirect(
                        ip,
                        {
                            "type": "historyRequest",
                            "id": peerId,
                            "requestId": historyId
                        }
                    )

        except:
            pass

def messageServer():
    server = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)

    try:
        server.bind(("0.0.0.0",MESSAGE_PORT))
    except:
        return

    while running:
        try:
            data, addr = server.recvfrom(65535)
            packet = json.loads(data.decode())

            if packet.get("signature") == SIGNATURE:
                handlePacket(packet,addr)

        except:
            pass

def handlePacket(packet, addr):
    ip = addr[0]
    packetType = packet.get("type")

    if packetType == "historyRequest":
        historyId = packet.get("requestId")
    
        if not historyId:
            return
    
        with lock:
            history = list(messages)
    
        chunks = [
            history[i:i + HISTORY_CHUNK_SIZE]
            for i in range(0, len(history), HISTORY_CHUNK_SIZE)
        ]
    
        if not chunks:
            chunks = [[]]
    
        total = len(chunks)

        for index, chunk in enumerate(chunks):
            sendDirect(
                ip,
                {
                    "type": "history",
                    "historyId": historyId,
                    "chunk": index,
                    "total": total,
                    "messages": chunk
                }
            )

    elif packetType == "history":
        historyId = packet.get("historyId")
    
        if not historyId:
            return
    
        chunk = packet.get("chunk", 0)
        total = packet.get("total", 1)
    
        with lock:
            if historyId not in receivedHistory:
                receivedHistory[historyId] = {}
    
            receivedHistory[historyId][chunk] = packet.get("messages", [])
            complete = len(receivedHistory[historyId]) == total
    
        if complete:
            with lock:
                chunks = receivedHistory.pop(historyId)
    
            for i in range(total):
                for msg in chunks.get(i, []):
                    addChat(
                        msg["sender"],
                        msg["text"],
                        msg["id"],
                        msg.get("nick", ""),
                        msg.get("timestamp")
                    )
    
            sendDirect(
                ip,
                {
                    "type": "historyAck",
                    "historyId": historyId
                }
            )

    elif packetType == "historyAck":
        with lock:
            pendingHistory.pop(packet.get("historyId"),None)

    elif packetType == "message":
        msgId = packet.get("id")
        updatePeer(ip, packet.get("sender"), packet.get("nick", ""))
        addChat(
            packet["sender"],
            packet["text"],
            msgId,
            packet.get("nick", ""),
            packet.get("timestamp")
        )
        sendDirect(ip, {"type": "ack", "id": msgId})

    elif packetType == "ack":
        with lock:
            pendingPackets.pop(packet.get("id"),None)

    elif packetType == "nick":
        updatePeer(ip,packet.get("id"),packet.get("nick", ""))

    elif packetType == "heartbeat":
        updatePeer(ip,packet.get("id"),packet.get("nick", ""))

def heartbeat():
    while running:
        broadcast({"type": "heartbeat","id": peerId,"nick": nick})
        time.sleep(5)

def resendLoop():
    while running:
        now = time.time()
        with lock:
            packets = list(pendingPackets.values())

        for item in packets:
            if now - item["time"] > RESEND_INTERVAL:
                sendUdp(item["ip"],item["packet"])

                with lock:
                    if item["packet"]["id"] in pendingPackets:
                        pendingPackets[item["packet"]["id"]]["time"] = now

        time.sleep(1)

def historyResendLoop():
    while running:
        now = time.time()
        with lock:
            requests = list(pendingHistory.items())

        for historyId, request in requests:
            if now - request["time"] > RESEND_INTERVAL:
                sendDirect(request["ip"],{"type": "historyRequest","id": peerId,"requestId": historyId})

                with lock:
                    if historyId in pendingHistory:
                        pendingHistory[historyId]["time"] = now

        time.sleep(1)

def discoveryLoop():
    while running:
        sendDiscovery()
        time.sleep(DISCOVERY_INTERVAL)

def cleanupPeers():
    while running:
        now = time.time()
        changed = False

        with lock:
            for pid in list(peers):
                if now - peers[pid]["time"] > PEER_TIMEOUT:
                    del peers[pid]
                    changed = True

            for packetId in list(pendingPackets):
                if now - pendingPackets[packetId]["time"] > PEER_TIMEOUT:
                    del pendingPackets[packetId]
                    changed = True

            for historyId in list(pendingHistory):
                if now - pendingHistory[historyId]["time"] > PEER_TIMEOUT:
                    del pendingHistory[historyId]
                    changed = True
            """
            for historyId in list(receivedHistory):
                if historyId not in pendingHistory:
                    del receivedHistory[historyId]
            """
        if changed:
            requestRedraw()

        time.sleep(2)

def setNick(name):
    global nick
    nick = name
    broadcast({"type": "nick","id": peerId,"nick": nick})
    requestRedraw()

def removeNick():
    global nick
    nick = ""
    broadcast({"type": "nick","id": peerId,"nick": ""})
    requestRedraw()

def sendChat(text):
    if len(text) > 100:
        text = text[:100]
    msgId = str(uuid.uuid4())
    timestamp = time.time()

    addChat(peerId, text, msgId, nick, timestamp)

    broadcast({
        "type": "message",
        "id": msgId,
        "sender": peerId,
        "nick": nick,
        "text": text,
        "timestamp": timestamp
    })

def inputLoop():
    global running
    while running:
        try:
            with patch_stdout():
                command = session.prompt("> ")

            if command.startswith("/nick "):
                setNick(command[6:].strip())

            elif command == "/nonick":
                removeNick()

            elif command.strip():
                sendChat(command)

        except KeyboardInterrupt:
            running = False

        except EOFError:
            running = False

threading.Thread(target=messageServer,daemon=True).start()
threading.Thread(target=discoveryServer,daemon=True).start()
threading.Thread(target=discoveryLoop,daemon=True).start()
threading.Thread(target=heartbeat,daemon=True).start()
threading.Thread(target=resendLoop,daemon=True).start()
threading.Thread(target=cleanupPeers,daemon=True).start()
threading.Thread(target=redrawLoop,daemon=True).start()
threading.Thread(target=historyResendLoop,daemon=True).start()

requestRedraw()

inputLoop()

print("\nDisconnected.")
