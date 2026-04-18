import socket, threading, os, random, string, struct, time, shlex

broadcastPort = 44555
transferPort = 44556
activeCodes = {}
bufferSize = 4096

def pause():
    try:
        input("Press Enter to continue...")
    except EOFError:
        pass

def clear():
    try:
        os.system('cls')
    except Exception:
        pass

def generateCode(length=6):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

def recvExact(conn, length):
    data = b""
    while len(data) < length:
        chunk = conn.recv(length - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def broadcastListener():
    udpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udpSock.bind(("", broadcastPort))
    while True:
        data, addr = udpSock.recvfrom(1024)
        if data.decode().strip() == "DISCOVER_FILE_TRANSFER":
            udpSock.sendto("TRANSFER_AVAILABLE".encode(), addr)

def sendFileStream(conn, filePath, relPath):
    relEnc = relPath.encode()
    conn.send(b"FILE__")
    conn.send(struct.pack("!I", len(relEnc)))
    conn.send(relEnc)

    fileSize = os.path.getsize(filePath)
    conn.send(struct.pack("!Q", fileSize))

    with open(filePath, "rb") as f:
        while True:
            chunk = f.read(bufferSize)
            if not chunk:
                break
            conn.send(chunk)

def sendFolder(conn, folderPath):
    baseFolder = os.path.basename(folderPath)
    for root, _, files in os.walk(folderPath):
        for f in files:
            filePath = os.path.join(root, f)
            relPath = os.path.relpath(filePath, folderPath)
            relPath = os.path.join(baseFolder, relPath)
            sendFileStream(conn, filePath, relPath)
    conn.send(b"END___")

def recvFileStream(conn, destFolder):
    raw = recvExact(conn, 4)
    if raw is None:
        return False
    pathLen = struct.unpack("!I", raw)[0]

    relPathBytes = recvExact(conn, pathLen)
    if relPathBytes is None:
        return False
    relPath = relPathBytes.decode()

    raw = recvExact(conn, 8)
    if raw is None:
        return False
    fileLen = struct.unpack("!Q", raw)[0]

    fullPath = os.path.join(destFolder, relPath)
    os.makedirs(os.path.dirname(fullPath), exist_ok=True)

    remaining = fileLen
    with open(fullPath, "wb") as f:
        while remaining > 0:
            chunk = conn.recv(min(bufferSize, remaining))
            if not chunk:
                return False
            f.write(chunk)
            remaining -= len(chunk)
    return True

def recvFolder(conn, destFolder):
    while True:
        flag = recvExact(conn, 6)
        if flag is None:
            return
        if flag == b"END___":
            return
        if flag == b"FILE__":
            if not recvFileStream(conn, destFolder):
                return

def tcpServer():
    serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSock.bind(("", transferPort))
    serverSock.listen(5)

    while True:
        conn, _ = serverSock.accept()
        try:
            raw = recvExact(conn, 4)
            if raw is None:
                conn.close()
                continue
            codeLen = struct.unpack("!I", raw)[0]

            codeBytes = recvExact(conn, codeLen)
            if codeBytes is None:
                conn.close()
                continue
            code = codeBytes.decode()

            if code not in activeCodes:
                conn.close()
                continue

            path = activeCodes[code]

            if os.path.isfile(path):
                conn.send(b"FILE__")
                name = os.path.basename(path).encode()
                conn.send(struct.pack("!I", len(name)))
                conn.send(name)

                fileSize = os.path.getsize(path)
                conn.send(struct.pack("!Q", fileSize))
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(bufferSize)
                        if not chunk:
                            break
                        conn.send(chunk)
            else:
                conn.send(b"FOLDER")  # 6 bytes
                name = os.path.basename(path).encode()
                conn.send(struct.pack("!I", len(name)))
                conn.send(name)
                sendFolder(conn, path)
        except:
            pass
        finally:
            conn.close()

def startNetworking():
    threading.Thread(target=broadcastListener, daemon=True).start()
    threading.Thread(target=tcpServer, daemon=True).start()

def discoverHosts():
    udpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpSock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udpSock.settimeout(1)
    udpSock.sendto("DISCOVER_FILE_TRANSFER".encode(), ("255.255.255.255", broadcastPort))
    hosts = []
    try:
        while True:
            msg, addr = udpSock.recvfrom(1024)
            if msg.decode().strip() == "TRANSFER_AVAILABLE":
                hosts.append(addr[0])
    except socket.timeout:
        pass
    return list(set(hosts))

def sendMode(kind, path):
    if not os.path.exists(path):
        print("Path not found.")
        pause()
        return

    code = generateCode()
    activeCodes[code] = os.path.abspath(path)
    print("Code:", code)

    while True:
        time.sleep(1)

def receiveMode(code):
    hosts = discoverHosts()
    if not hosts:
        print("No senders found")
        pause()
        return

    for host in hosts:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, transferPort))

            codeEnc = code.encode()
            sock.send(struct.pack("!I", len(codeEnc)))
            sock.send(codeEnc)

            flag = recvExact(sock, 6)
            if flag is None:
                continue

            if flag == b"FILE__":
                raw = recvExact(sock, 4)
                if raw is None:
                    continue
                nameLen = struct.unpack("!I", raw)[0]

                nameBytes = recvExact(sock, nameLen)
                if nameBytes is None:
                    continue
                name = nameBytes.decode()

                raw = recvExact(sock, 8)
                if raw is None:
                    continue
                fileLen = struct.unpack("!Q", raw)[0]

                remaining = fileLen
                with open(name, "wb") as f:
                    while remaining > 0:
                        chunk = sock.recv(min(bufferSize, remaining))
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)
                print("Received file:", name)
                pause()
                return

            if flag == b"FOLDER":
                raw = recvExact(sock, 4)
                if raw is None:
                    continue
                nameLen = struct.unpack("!I", raw)[0]

                nameBytes = recvExact(sock, nameLen)
                if nameBytes is None:
                    continue
                baseFolder = nameBytes.decode()

                os.makedirs(baseFolder, exist_ok=True)
                recvFolder(sock, ".")
                print("Received folder:", baseFolder)
                pause()
                return
        except:
            pass
        finally:
            if sock:
                sock.close()

    print("Transfer failed")
    pause()

def parseCommand(cmd):
    try:
        parts = shlex.split(cmd)
    except:
        print("Invalid command")
        pause()
        return

    if not parts:
        return

    action = parts[0].lower()

    if action in ("send", "s"):
        if len(parts) < 3:
            print("Usage: send file|folder path")
            pause()
            return
        kind = parts[1].lower()
        path = parts[2]
        if kind in ("file", "fi"):
            sendMode("file", path)
        elif kind in ("folder", "fo"):
            sendMode("folder", path)
        else:
            print("Unknown send type")
            pause()
        return

    if action in ("receive", "r"):
        if len(parts) < 2:
            print("Usage: receive CODE")
            pause()
            return
        code = parts[1]
        receiveMode(code)
        return
    if action in ("help", "h"):
        print("\nSend usage: send file|folder path")
        print("\nReceive usage: receive CODE\n")
        pause()
        return

    print("Unknown command")
    pause()

if __name__ == "__main__":
    startNetworking()
    try:
        while True:
            clear()
            cmd = input("Enter command: ").strip()
            parseCommand(cmd)
    except KeyboardInterrupt:
        print("\nExiting...")
