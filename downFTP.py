import os
from ftplib import FTP
from urllib.parse import urlparse

def download_ftp_file(ftp_url):
    # Parse the URL
    parsed = urlparse(ftp_url)
    if parsed.scheme != "ftp":
        raise ValueError("Only ftp:// URLs are supported.")

    host = parsed.hostname
    port = parsed.port or 21
    username = parsed.username or "anonymous"
    password = parsed.password or "anonymous@"
    path = parsed.path

    # Extract remote directory and filename
    remote_dir = os.path.dirname(path)
    filename = os.path.basename(path)
    if not filename:
        raise ValueError("The URL must point to a specific file.")

    # Connect and download
    with FTP() as ftp:
        print(f"Connecting to {host}:{port}...")
        ftp.connect(host, port)
        ftp.login(username, password)
        print("Connected. Navigating to directory...")

        if remote_dir:
            ftp.cwd(remote_dir)

        print(f"Downloading: {filename}")
        with open(filename, "wb") as f:
            ftp.retrbinary(f"RETR {filename}", f.write)

        print(f"Download complete. File saved as: {filename}")

if __name__ == "__main__":
    # Example FTP file
    url = input("Enter a url: ")
    download_ftp_file(url)