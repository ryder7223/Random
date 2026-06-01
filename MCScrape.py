import socket
import minestat
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Style
import random
import threading
import sqlite3
import subprocess
import json
import time

PORT = 25565
TIMEOUT = 0.5
MAX_WORKERS = 1000

# ----------------------------
# WHITELIST SETTINGS
# ----------------------------
ENABLE_WHITELIST_CHECK = False

printLock = threading.Lock()
dbLock = threading.Lock()

# ----------------------------
# SQLite setup
# ----------------------------
dbConnection = sqlite3.connect("minecraft_servers.db", check_same_thread=False)
dbCursor = dbConnection.cursor()

dbCursor.execute("""
CREATE TABLE IF NOT EXISTS servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    port INTEGER,
    latency REAL,
    players INTEGER,
    max_players INTEGER,
    player_list TEXT,
    motd TEXT,
    version TEXT,
    gamemode TEXT,
    plugins TEXT,
    map TEXT,
    protocol TEXT,
    whitelist INTEGER,
    timestamp TEXT
)
""")
dbConnection.commit()


# ----------------------------
# NODE WHITELIST CHECK (WITH RETRIES)
# ----------------------------
def checkWhitelistNode(ip, port, maxRetries=3):
    for attempt in range(maxRetries):
        try:
            result = subprocess.run(
                ["node", "checkWhitelist.js", ip, str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20
            )

            output = result.stdout.strip()

            if not output:
                nodeResult = {"status": "error", "error": "no_output"}
            else:
                nodeResult = json.loads(output)

            status = nodeResult.get("status", "error")

            # Only retry on disconnect
            if status == "disconnected" and attempt < maxRetries - 1:
                time.sleep(0.5)
                continue

            return nodeResult

        except Exception as e:
            nodeResult = {"status": "error", "error": str(e)}

            if attempt < maxRetries - 1:
                time.sleep(0.5)
                continue

            return nodeResult

    return {"status": "error", "error": "max_retries_exceeded"}


# ----------------------------
# DATABASE SAVE
# ----------------------------
def saveToDatabase(ip, port, ms, whitelistStatus=None):

    # ----------------------------
    # WHITELIST VALUE HANDLING
    # ----------------------------
    if not ENABLE_WHITELIST_CHECK:
        whitelistStatus = "none"
        isWhitelisted = None

    else:
        if whitelistStatus in ("whitelist_allowed", "whitelist_blocked"):
            isWhitelisted = 1

        elif whitelistStatus in ("error", "disconnected"):
            isWhitelisted = 2

        else:
            isWhitelisted = 0

    with dbLock:
        dbCursor.execute("""
            INSERT INTO servers (
                ip, port, latency, players, max_players,
                player_list, motd, version, gamemode,
                plugins, map, protocol, whitelist, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ip,
            port,
            ms.latency,
            ms.current_players,
            ms.max_players,
            str(ms.player_list),
            ms.stripped_motd,
            ms.version,
            ms.gamemode,
            str(ms.plugins),
            ms.map,
            str(ms.slp_protocol),
            isWhitelisted,
            str(datetime.now())
        ))

        dbConnection.commit()


def isPrivateIp(firstOctet, secondOctet):
    if firstOctet == 10:
        return True

    if firstOctet == 172 and 16 <= secondOctet <= 31:
        return True

    if firstOctet == 192 and secondOctet == 168:
        return True

    return False


def generate_ip():
    while True:
        firstOctet = random.randint(1, 222)

        if firstOctet >= 127:
            firstOctet += 1

        secondOctet = random.randint(0, 255)

        if isPrivateIp(firstOctet, secondOctet):
            continue

        return f"{firstOctet}.{secondOctet}.{random.randint(0,255)}.{random.randint(0,255)}"


def checkMinecraftServer(ip: str, port: int):
    try:
        with socket.create_connection((ip, port), timeout=TIMEOUT) as sock:
            sock.sendall(b'\xFE\x01')
            data = sock.recv(1024)

        if not data:
            return

        if b'\xff' in data:
            data = data[16:]

        decoded = data.decode("utf-16", errors="ignore")

        if not decoded:
            return

        ms = minestat.MineStat(ip, port)
        ms.fullstat_query()

        if not ms.online:
            return

        # ----------------------------
        # WHITELIST CHECK
        # ----------------------------
        status = "none"

        if ENABLE_WHITELIST_CHECK:
            nodeResult = checkWhitelistNode(ip, port)
            status = nodeResult.get("status", "unknown")

            if status == "timeout":
                status = "joinable"

        # ----------------------------
        # SAVE TO DATABASE
        # ----------------------------
        saveToDatabase(ip, port, ms, status)

        # ----------------------------
        # OUTPUT
        # ----------------------------
        lines = []

        lines.append("------------------------------------")
        lines.append(f"{Fore.GREEN}[+] {ip}:{port} Minecraft server detected{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Latency: {ms.latency} ms{Style.RESET_ALL}")

        if ms.current_players:
            colour = Fore.LIGHTRED_EX if ms.current_players > 0 else Fore.YELLOW
            lines.append(f"{colour}Players: {ms.current_players}{Style.RESET_ALL}")

        lines.append(f"{Fore.YELLOW}Player list: {ms.player_list}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Max players: {ms.max_players}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Plugins: {ms.plugins}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Map: {ms.map}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}MOTD: {ms.stripped_motd}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Version: {ms.version}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Gamemode: {ms.gamemode}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Protocol: {ms.slp_protocol}{Style.RESET_ALL}")

        lines.append(f"{Fore.CYAN}Whitelist: {status}{Style.RESET_ALL}")
        lines.append(f"{Fore.YELLOW}Timestamp: {datetime.now()}{Style.RESET_ALL}")
        lines.append("------------------------------------")

        output = "\n".join(lines)

        with printLock:
            print(output)

    except (socket.timeout, ConnectionRefusedError, OSError):
        return

    except Exception as e:
        with printLock:
            print(f"{Fore.RED}[!] {ip}:{port} - {type(e).__name__}: {e}{Style.RESET_ALL}")


def main():
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(lambda ip: checkMinecraftServer(ip, PORT), targets)


if __name__ == "__main__":
    while True:
        targets = [generate_ip() for _ in range(100000)]
        main()