import os
import socket
from ftplib import FTP, error_perm
from urllib.parse import urlparse

class FTPClientShell:
    def __init__(self, ftp_url):
        parsed = urlparse(ftp_url)
        if parsed.scheme != "ftp":
            raise ValueError("Only ftp:// URLs are supported.")

        self.host = parsed.hostname
        self.port = parsed.port or 21
        self.username = parsed.username or "anonymous"
        self.password = parsed.password or "anonymous@"
        self.initial_path = parsed.path if parsed.path else None
        self.ftp = FTP()
        self.ftp.encoding = "latin-1"  # Force latin-1 encoding

    def connect(self):
        print(f"Connecting to {self.host}:{self.port}...")
        self.ftp.connect(self.host, self.port)
        self.ftp.login(self.username, self.password)
        print("Connected.")
        if self.initial_path:
            self.ftp.cwd(self.initial_path)
        else:
            try:
                self.initial_path = self.ftp.pwd()
            except Exception:
                self.initial_path = None

    def run_shell(self):
        self.print_help()
        while True:
            try:
                cwd = self.ftp.pwd()
                full_input = input(f"ftp:{cwd}> ").strip()
                if not full_input:
                    continue
    
                commands = [cmd.strip() for cmd in full_input.split("&&")]
    
                for cmd in commands:
                    if not cmd:
                        continue
    
                    if cmd == "exit":
                        self.ftp.quit()
                        print("Disconnected.")
                        return
                    elif cmd == "ls":
                        self.list_dir()
                    elif cmd == "pwd":
                        print(self.ftp.pwd())
                    elif cmd.startswith("cd "):
                        self.change_dir(cmd[3:].strip())
                    elif cmd == "up":
                        self.ftp.cwd("..")
                    elif cmd.startswith("get "):
                        self.download_file(cmd[4:].strip())
                    elif cmd.startswith("mget "):
                        self.download_dir(cmd[5:].strip(), ".")
                    elif cmd.startswith("put "):
                        self.upload_file(cmd[4:].strip())
                    elif cmd.startswith("delete "):
                        self.delete_file(cmd[7:].strip())
                    elif cmd.startswith("rename "):
                        args = cmd[7:].split()
                        if len(args) == 2:
                            self.rename_file(args[0], args[1])
                        else:
                            print("Usage: rename <old> <new>")
                            break
                    elif cmd.startswith("mkdir "):
                        self.make_dir(cmd[6:].strip())
                    elif cmd.startswith("rmdir "):
                        self.remove_dir(cmd[6:].strip())
                    elif cmd.startswith("cat "):
                        self.display_file_contents(cmd[4:].strip())
                    elif cmd == "help":
                        self.print_help()
                    else:
                        print(f"Unknown command: {cmd}")
                        break

            except (socket.error, ConnectionResetError, ConnectionAbortedError, EOFError, OSError) as e:
                print(f"\nConnection lost: {e}")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

        self.ftp.quit()
        print("Disconnected.")

    def print_help(self):
        print("Available commands:")
        print("  ls                 - List directory contents")
        print("  cd <dir>           - Change directory")
        print("  up                 - Go up one directory")
        print("  pwd                - Show current directory")
        print("  get <file>         - Download file")
        print("  mget <dir>         - Download directory recursively")
        print("  put <file>         - Upload file")
        print("  delete <file>      - Delete file")
        print("  rename <old> <new> - Rename file")
        print("  mkdir <dir>        - Create directory")
        print("  rmdir <dir>        - Remove directory")
        print("  cat <file>         - View file contents (text only)")
        print("  help               - Show this help message")
        print("  exit               - Exit the shell")

    def list_dir(self):
        try:
            self.ftp.retrlines("LIST")
        except Exception as e:
            print(f"Failed to list directory: {e}")

    def change_dir(self, path):
        try:
            self.ftp.cwd(path)
        except Exception as e:
            print(f"Failed to change directory: {e}")

    def download_file(self, filename):
        try:
            with open(filename, "wb") as f:
                self.ftp.retrbinary(f"RETR {filename}", f.write)
            print(f"Downloaded: {filename}")
        except Exception as e:
            print(f"Failed to download {filename}: {e}")

    def download_dir(self, remote_dir, local_dir):
        try:
            original_dir = self.ftp.pwd()
            self.ftp.cwd(remote_dir)
            os.makedirs(os.path.join(local_dir, remote_dir), exist_ok=True)
            file_list = self.ftp.nlst()

            for item in file_list:
                try:
                    self.ftp.cwd(item)
                    self.ftp.cwd("..")
                    self.download_dir(os.path.join(remote_dir, item), local_dir)
                except error_perm:
                    local_path = os.path.join(local_dir, remote_dir, item)
                    with open(local_path, "wb") as f:
                        self.ftp.retrbinary(f"RETR " + item, f.write)
                    print(f"Downloaded: {os.path.join(remote_dir, item)}")

            self.ftp.cwd(original_dir)
        except Exception as e:
            print(f"Failed to download directory {remote_dir}: {e}")

    def upload_file(self, filename):
        try:
            with open(filename, "rb") as f:
                self.ftp.storbinary(f"STOR {os.path.basename(filename)}", f)
            print(f"Uploaded: {filename}")
        except Exception as e:
            print(f"Failed to upload {filename}: {e}")

    def delete_file(self, filename):
        try:
            self.ftp.delete(filename)
            print(f"Deleted: {filename}")
        except Exception as e:
            print(f"Failed to delete {filename}: {e}")

    def rename_file(self, old, new):
        try:
            self.ftp.rename(old, new)
            print(f"Renamed: {old} -> {new}")
        except Exception as e:
            print(f"Failed to rename: {e}")

    def make_dir(self, dirname):
        try:
            self.ftp.mkd(dirname)
            print(f"Directory created: {dirname}")
        except Exception as e:
            print(f"Failed to create directory: {e}")

    def remove_dir(self, dirname):
        try:
            self.ftp.rmd(dirname)
            print(f"Directory removed: {dirname}")
        except Exception as e:
            print(f"Failed to remove directory: {e}")

    def display_file_contents(self, filename):
        try:
            self.ftp.retrlines(f"RETR {filename}")
        except Exception as e:
            print(f"Failed to display contents: {e}")

if __name__ == "__main__":
    enterURL = input("Enter a url: ")
    url = f"ftp://{enterURL}"
    client = FTPClientShell(url)
    try:
        client.connect()
        client.run_shell()
    except Exception as e:
        print(f"Connection error: {e}")
    input()