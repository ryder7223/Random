import minestat
import socket
from datetime import datetime
import re
import json

def extractMotdText(motd):
    try:
        motdData = json.loads(motd)
        texts = []

        def recurse(obj):
            if isinstance(obj, dict):
                if "text" in obj:
                    texts.append(obj["text"])
                if "extra" in obj:
                    for item in obj["extra"]:
                        recurse(item)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)

        recurse(motdData)
        return re.sub(r"§.", "", f"{''.join(texts)}")
    except Exception:
        # Not JSON, treat as plain text
        return motd

while  True:
    __import__("os").system("cls")
    ip = input("Enter IP: ")
    if ":" in ip:
        port = int(ip.split(":")[1])
        ip = ip.split(":")[0]
    else: port = 25565
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    s.connect((ip, port))
    s.send(b'\xFE\x01')
    while True:
        try:
            get = s.recv(1024)
            break
        except TimeoutError:
            pass
    if b'\xff' in get:
        get = get[16::]
    conv = get.decode('utf-16', errors='ignore')
    
    ms = minestat.MineStat(ip,port)
    ms.fullstat_query()
    if ms.online: # and ms.current_players > 0
        print("------------------------------------")
        print(f'Connected using protocol: %s' % ms.slp_protocol)
        print(f'Version: %s' % ms.version)
        print(f'Players: %s/%s' % (ms.current_players, ms.max_players))
        print(f'Player list: %s' % ms.player_list)
        #print(f'Plugins: %s' % ms.plugins)
        #print(ms.motd)
        #print(print(f'Raw version and description: %s' % conv))
        print(f'MOTD: %s' % extractMotdText(ms.motd))
        #print(f'Map: %s' % ms.map)
        print(f"Latency: %sms" % ms.latency)
        if ms.gamemode:
            print(f'Game mode: %s' % ms.gamemode)
        input("\nEnter to continue...")