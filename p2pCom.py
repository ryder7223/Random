import subprocess
import importlib
import sys

requiredModules = {
    "prompt_toolkit": {
        "package": "prompt_toolkit"
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

import socket
import threading
import json
import time
import uuid
import os
import shutil
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

MESSAGE_PORT = 5000
DISCOVERY_PORT = 5001

PEER_TIMEOUT = 15
DISCOVERY_INTERVAL = 2
RESEND_INTERVAL = 2
HISTORY_CHUNK_SIZE = 50

SIGNATURE = "P2PMSG1"

peerId = str(uuid.uuid4())[:8]
nick = ""

peers = {}
messages = []
messageIds = set()
pendingPackets = {}
pendingHistory = {}
receivedHistory = {}

lock = threading.Lock()
running = True
redrawNeeded = True

session = PromptSession()

def getLocalIps():
    ips = {"127.0.0.1"}

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(info[4][0])
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

def requestRedraw():
    global redrawNeeded
    redrawNeeded = True

def displayName(pid, storedNick=""):
    if pid == peerId:
        return nick or peerId

    if storedNick:
        return storedNick

    if pid in peers:
        return peers[pid].get("nick") or pid

    return pid

def formatMessage(message):
    return f"[{displayName(message['sender'], message.get('nick', ''))}] {message['text']}"

def drawChat():
    global redrawNeeded

    with lock:
        clearScreen()
        names = [nick or peerId]

        for peer in peers.values():
            names.append(peer.get("nick") or peer["id"])

        print("Peers: " + ", ".join(names))
        print("-" * shutil.get_terminal_size().columns)
        height = shutil.get_terminal_size().lines - 4

        for message in messages[-height:]:
            print(formatMessage(message))

        print("-" * shutil.get_terminal_size().columns)

    redrawNeeded = False

def redrawLoop():
    while running:
        if redrawNeeded:
            with patch_stdout():
                drawChat()

        time.sleep(0.2)

def addChat(sender, text, messageId=None, senderNick=""):
    if not messageId:
        messageId = str(uuid.uuid4())

    with lock:
        if messageId in messageIds:
            return

        messageIds.add(messageId)
        messages.append({"id": messageId,"sender": sender,"nick": senderNick,"text": text})

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

    with lock:
        if pid in peers:
            peers[pid]["ip"] = ip
            peers[pid]["time"] = time.time()

            if peerNick:
                peers[pid]["nick"] = peerNick

        else:
            peers[pid] = {"id": pid,"nick": peerNick,"ip": ip,"time": time.time()}

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
                updatePeer(ip,packet.get("id"),packet.get("nick", ""))
                discoveryResponse(ip)
                historyId = str(uuid.uuid4())

                with lock:
                    pendingHistory[historyId] = {"ip": ip,"time": time.time()}
                
                sendDirect(ip,{"type": "historyRequest","id": peerId,"requestId": historyId})

            elif packet.get("type") == "discoverResponse":
                updatePeer(ip, packet.get("id"), packet.get("nick", ""))
            
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
                        msg.get("nick", "")
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
        updatePeer(ip,packet.get("sender"),packet.get("nick", ""))
        addChat(packet["sender"],packet["text"],msgId,packet.get("nick", ""))
        sendDirect(ip,{"type": "ack","id": msgId})

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

        with lock:
            for pid in list(peers):
                if now - peers[pid]["time"] > PEER_TIMEOUT:
                    del peers[pid]

            for packetId in list(pendingPackets):
                if now - pendingPackets[packetId]["time"] > PEER_TIMEOUT:
                    del pendingPackets[packetId]

            for historyId in list(pendingHistory):
                if now - pendingHistory[historyId]["time"] > PEER_TIMEOUT:
                    del pendingHistory[historyId]
            """
            for historyId in list(receivedHistory):
                if historyId not in pendingHistory:
                    del receivedHistory[historyId]
            """
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
    msgId = str(uuid.uuid4())

    addChat(peerId,text,msgId,nick)

    broadcast({"type": "message","id": msgId,"sender": peerId,"nick": nick,"text": text})

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
