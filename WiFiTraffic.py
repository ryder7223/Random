import subprocess
import importlib
import sys

requiredModules = ['psutil', 'tqdm']

def installMissingModules(modules):
    pip = 'pip'
    try:
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

installMissingModules(requiredModules)

import os
import psutil
from tqdm import tqdm
from collections import deque
import time

os.system('cls')

def get_size(bytes):
    """Convert bytes to a human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} PB"

def list_network_interfaces():
    """List all network interfaces."""
    return psutil.net_if_stats()

def monitor_traffic(interface):
    """Monitor network traffic on the selected interface."""
    os.system("cls" if os.name == "nt" else "clear")
    print(f"Monitoring network traffic on interface: {interface}")
    prev = psutil.net_io_counters(pernic=True)[interface]
    total_upload = 0
    total_download = 0

    # Buffers to store last 10 readings (for ~1 second smoothing)
    download_history = deque(maxlen=10)
    upload_history = deque(maxlen=10)

    pbar_live = tqdm(total=100, bar_format='{desc}', dynamic_ncols=True, position=0)
    pbar_total = tqdm(total=100, bar_format='{desc}', dynamic_ncols=True, position=1)

    while True:
        time.sleep(0.1)
        current = psutil.net_io_counters(pernic=True)[interface]
        upload = current.bytes_sent - prev.bytes_sent
        download = current.bytes_recv - prev.bytes_recv

        total_upload += upload
        total_download += download

        # Update rolling history
        download_history.append(download)
        upload_history.append(upload)

        # Sum over the last second
        download_per_sec = sum(download_history)
        upload_per_sec = sum(upload_history)

        live_download = f"↓ {get_size(download_per_sec)}/s"
        live_upload = f"↑ {get_size(upload_per_sec)}/s"
        total_download_str = f"Total ↓: {get_size(total_download):<10}"
        total_upload_str = f"Total ↑: {get_size(total_upload):<10}"

        pbar_live.set_description_str(f"[{time.strftime('%H:%M:%S')}] {live_download:<15} | {live_upload:<15}")
        pbar_total.set_description_str(f"  {total_download_str} | {total_upload_str}")

        prev = current

if __name__ == "__main__":
    try:
        interfaces = list_network_interfaces()
        print("Available network interfaces:")
        for i, interface in enumerate(interfaces.keys(), 1):
            print(f"{i}. {interface}")

        selected = input(f"Please choose an interface to monitor (1-{len(interfaces)}): ").strip()

        try:
            selected_index = int(selected) - 1
            if 0 <= selected_index < len(interfaces):
                selected_interface = list(interfaces.keys())[selected_index]
            else:
                print("Invalid selection, exiting...")
                sys.exit(1)
        except ValueError:
            print("Invalid input, exiting...")
            sys.exit(1)

        monitor_traffic(selected_interface)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)