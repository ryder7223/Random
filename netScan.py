import socket
import threading
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

# === Configuration ===
show_progress = False
show_overall_progress = True
save_to_file = False
max_workers = 10000  # user input, but will be clamped

# === Globals ===
overall_pbar = None
file_lock = threading.Lock()
progress_lock = threading.Lock()
completed_count = 0

def print_above_progress(message):
    if not save_to_file:
        if overall_pbar:
            overall_pbar.clear()
            print(message)
            overall_pbar.refresh()
        else:
            print(message)

def scan_port(ip, port, timeout=0.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        if save_to_file:
            with file_lock:
                with open("open_ips80.txt", "a") as f:
                    f.write(f"{ip}:{port}\n")
        else:
            print_above_progress(f"[OPEN] {ip}:{port}")
    except:
        pass
    finally:
        s.close()

def scan_ip_ports(ip, ports):
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        if show_progress:
            with tqdm(ports, desc=f"Scanning {ip}", leave=False,
                      bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as port_pbar:
                for port in ports:
                    futures.append(executor.submit(scan_port, ip, port))
                for future in as_completed(futures):
                    port_pbar.update(1)
        else:
            for port in ports:
                futures.append(executor.submit(scan_port, ip, port))
            for future in as_completed(futures):
                pass

def main():
    global overall_pbar, completed_count

    ip_input = input("Enter the IP address (e.g., 192.168, 192.168.1, 192.168.1.1, 10, or leave blank for random): ").strip()
    if ip_input == '':
        num_ips = input("How many random IPs do you want to search? (default 256): ").strip()
        num_ips = int(num_ips) if num_ips.isdigit() and int(num_ips) > 0 else 256
        ips_to_scan = list({f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}" for _ in range(num_ips)})
    elif ip_input.count('.') == 3:
        ips_to_scan = [ip_input]
    elif ip_input.count('.') == 2:
        base_ip = ip_input
        ips_to_scan = [f"{base_ip}.{i}" for i in range(256)]
    elif ip_input.count('.') == 1:
        base_ip = ip_input
        ips_to_scan = [f"{base_ip}.{i}.{j}" for i in range(256) for j in range(256)]
    elif ip_input.isdigit():
        base_ip = ip_input
        ips_to_scan = [f"{base_ip}.{i}.{j}.{k}" for i in range(256) for j in range(256) for k in range(256)]
    else:
        print("Invalid input. Please enter a valid IP format, a single number, or leave blank for random.")
        return

    port_input = input("Enter port or port range (e.g., 80 or 20-25): ").strip()
    if '-' in port_input:
        start_port, end_port = map(int, port_input.split('-'))
        ports = list(range(start_port, end_port + 1))
    else:
        ports = [int(port_input)]

    # Clamp max_workers to 1000 to avoid thread explosion
    workers = max_workers if max_workers <= 1000 else 1000

    completed_count = 0

    def task_done_callback(future):
        global completed_count
        with progress_lock:
            completed_count += 1
            if show_overall_progress and overall_pbar:
                overall_pbar.update(1)

    futures = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        if show_overall_progress:
            overall_pbar = tqdm(total=len(ips_to_scan), desc="Overall Progress", leave=True, position=0)

        for ip in ips_to_scan:
            future = executor.submit(scan_ip_ports, ip, ports)
            future.add_done_callback(task_done_callback)
            futures.append(future)

        # Wait for all to complete
        for future in as_completed(futures):
            pass

        if show_overall_progress and overall_pbar:
            overall_pbar.close()

if __name__ == "__main__":
    main()