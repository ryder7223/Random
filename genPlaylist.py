import os
import socket
import http.server
import socketserver
from pathlib import Path

audioExtensions = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"
}

chunkSize = 8192


def getLocalIp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        localIp = sock.getsockname()[0]
    finally:
        sock.close()
    return localIp


def findAudioFiles(directory):
    audioFiles = []
    for file in sorted(os.listdir(directory)):
        filePath = Path(directory) / file
        if filePath.is_file() and filePath.suffix.lower() in audioExtensions:
            audioFiles.append(file)
    return audioFiles


def generateM3u8(audioFiles, outputFile):
    with open(outputFile, "w", encoding="utf-8") as playlist:
        playlist.write("#EXTM3U\n")
        for file in audioFiles:
            playlist.write(f"#EXTINF:-1,{file}\n")
            playlist.write(f"{file}\n")


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):

    def sendHead(self):
        path = self.translate_path(self.path)

        if os.path.isdir(path):
            return super().send_head()

        if not os.path.exists(path):
            self.send_error(404, "File not found")
            return None

        fileSize = os.path.getsize(path)
        rangeHeader = self.headers.get("Range")

        file = open(path, "rb")

        if rangeHeader:
            rangeValue = rangeHeader.strip().lower().replace("bytes=", "")
            startStr, endStr = rangeValue.split("-")

            start = int(startStr) if startStr else 0
            end = int(endStr) if endStr else fileSize - 1

            if end >= fileSize:
                end = fileSize - 1

            length = end - start + 1

            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{fileSize}")
            self.send_header("Content-Length", str(length))
            self.end_headers()

            file.seek(start)
            self.wfile.write(file.read(length))
            file.close()
            return None

        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(fileSize))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        return file

    def copyfile(self, source, outputfile):
        while True:
            data = source.read(chunkSize)
            if not data:
                break
            outputfile.write(data)


def startServer(port):
    with socketserver.ThreadingTCPServer(("", port), RangeRequestHandler) as httpd:
        print(f"Serving on port {port}")
        httpd.serve_forever()


def main():
    port = 5016
    currentDirectory = os.getcwd()
    audioFiles = findAudioFiles(currentDirectory)

    if not audioFiles:
        print("No audio files found in directory.")
        return

    playlistName = "playlist.m3u8"
    generateM3u8(audioFiles, playlistName)

    localIp = getLocalIp()

    print("Playlist generated successfully.")
    print("Open this link on your local network:")
    print(f"http://{localIp}:{port}/{playlistName}")

    startServer(port)


if __name__ == "__main__":
    main()
