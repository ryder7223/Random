'''
This script is designed to be used in it's executable form, not source. This is because it requires you drag and drop a file onto it.
'''
import sys
import os
import hashlib
import subprocess

def hash_file(file_path):
    hashes = {'MD5': hashlib.md5(), 'SHA1': hashlib.sha1(), 'SHA256': hashlib.sha256()}
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                for h in hashes.values():
                    h.update(chunk)
    except Exception as e:
        return f"Error reading file: {e}"
    return {k: v.hexdigest() for k, v in hashes.items()}

def hash_folder(folder_path):
    file_hashes = []
    for root, _, files in os.walk(folder_path):
        for name in files:
            filepath = os.path.join(root, name)
            relative_path = os.path.relpath(filepath, folder_path)
            hashes = hash_file(filepath)
            if isinstance(hashes, dict):
                hash_string = f"{relative_path}:{hashes['SHA256']}"
                file_hashes.append(hash_string)
    file_hashes.sort()
    combined = '\n'.join(file_hashes).encode('utf-8')
    folder_hash = {
        'MD5': hashlib.md5(combined).hexdigest(),
        'SHA1': hashlib.sha1(combined).hexdigest(),
        'SHA256': hashlib.sha256(combined).hexdigest()
    }
    return folder_hash, file_hashes

def show_results(path):
    print("="*50)
    print(f"Target: {path}")
    print("="*50)
    if os.path.isfile(path):
        print("[ File Hashes ]")
        hashes = hash_file(path)
        if isinstance(hashes, dict):
            for k, v in hashes.items():
                print(f"{k}: {v}")
        else:
            print(hashes)
    elif os.path.isdir(path):
        print("[ Folder Hashes (Unique by structure+content) ]")
        folder_hash, detailed = hash_folder(path)
        for k, v in folder_hash.items():
            print(f"{k}: {v}")
        print("\n[ Individual File Hashes Used for Folder Hash ]")
        for line in detailed:
            print(line)
    else:
        print("Invalid path or inaccessible.")
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Drag and drop a file or folder onto this script to analyze.")
        input("Press Enter to exit...")
        sys.exit()

    path = sys.argv[1]
    if not os.path.exists(path):
        print("Path does not exist.")
        input("Press Enter to exit...")
        sys.exit()

    # Relaunch in terminal if not already in one
    if os.name == "nt":
        # Windows
        if not sys.stdout.isatty():
            subprocess.call(['start', 'cmd', '/k', f'python "{__file__}" "{path}"'], shell=True)
    else:
        # Linux/Mac - open new terminal window
        if not sys.stdout.isatty():
            terminal_cmds = [
                ['gnome-terminal', '--', 'python3', __file__, path],
                ['x-terminal-emulator', '-e', f'python3 "{__file__}" "{path}"'],
                ['konsole', '-e', 'python3', __file__, path],
                ['xterm', '-e', 'python3', __file__, path]
            ]
            for cmd in terminal_cmds:
                try:
                    subprocess.Popen(cmd)
                    break
                except Exception:
                    continue
    show_results(path)