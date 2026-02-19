import os
import uuid
import time
from flask import Flask, request, Response, abort

app = Flask(__name__)

uploadDir = "uploads"
chunkSize = 8192

os.makedirs(uploadDir, exist_ok=True)

cleanupInterval = 30
lastCleanup = 0


def getFilePath(fileId):
    return os.path.join(uploadDir, fileId)


def getMetaPath(fileId):
    return os.path.join(uploadDir, f".{fileId}.meta")


def parseExpiration(expirationValue):
    unit = expirationValue[-1]
    amount = float(expirationValue[:-1])

    if unit == "s":
        return amount
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 3600
    if unit == "d":
        return amount * 86400

    return None


def cleanupExpiredFiles(force=False):
    global lastCleanup
    now = time.time()

    if not force and (now - lastCleanup) < cleanupInterval:
        return

    lastCleanup = now

    for name in os.listdir(uploadDir):
        if not name.startswith(".") or not name.endswith(".meta"):
            continue

        metaPath = os.path.join(uploadDir, name)
        fileId = name[1:-5]
        filePath = getFilePath(fileId)

        try:
            with open(metaPath, "r") as f:
                expiresAt = float(f.read().strip())
        except Exception:
            continue

        if now >= expiresAt:
            try:
                if os.path.exists(filePath):
                    os.remove(filePath)
                os.remove(metaPath)
            except Exception:
                pass


def isExpired(fileId):
    metaPath = getMetaPath(fileId)
    if not os.path.isfile(metaPath):
        return True

    try:
        with open(metaPath, "r") as f:
            expiresAt = float(f.read().strip())
    except Exception:
        return True

    if time.time() >= expiresAt:
        cleanupExpiredFiles(force=True)
        return True

    return False


@app.before_request
def runCleanup():
    cleanupExpiredFiles()


@app.route("/", methods=["GET"])
def indexPage():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Stream Generator</title>
<style>
body {
    font-family: Arial, sans-serif;
    background: #0f0f0f;
    color: #e0e0e0;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
}

.container {
    background: #1e1e1e;
    padding: 20px;
    border-radius: 8px;
    width: 420px;
}

select, input, button {
    width: 100%;
    margin-top: 10px;
}

.progressContainer {
    margin-top: 15px;
    height: 6px;
    background: #0b0b0b;
    border-radius: 999px;
    overflow: hidden;
    display: none;
}

.progressBar {
    height: 100%;
    width: 0%;
    border-radius: 999px;
    background: linear-gradient(
        to bottom,
        #6bb8ff 0%,
        #2f89ff 50%,
        #1e6fe3 100%
    );
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.35);
    transition: width 0.1s linear;
}

.result {
    margin-top: 15px;
    word-break: break-all;
}

.result a {
    color: #6bb8ff;
    text-decoration: none;
}

.result a:hover {
    text-decoration: underline;
}

</style>
</head>
<body>
<div class="container">
    <h2>Upload File</h2>

    <input type="file" id="fileInput" required>

    <select id="expiration">
        <option value="10s">10 seconds</option>
        <option value="60s">1 minute</option>
        <option value="30m">30 minutes</option>
        <option value="1h">1 hour</option>
        <option value="12h">12 hours</option>
        <option value="1d">1 day</option>
    </select>

    <button onclick="upload()">Upload</button>

    <div class="progressContainer" id="progressContainer">
        <div class="progressBar" id="progressBar"></div>
    </div>

    <div class="result" id="result"></div>
</div>

<script>
function upload() {
    const fileInput = document.getElementById("fileInput");
    if (!fileInput.files.length) {
        return;
    }

    const progressContainer = document.getElementById("progressContainer");
    const progressBar = document.getElementById("progressBar");
    const result = document.getElementById("result");

    result.textContent = "";
    progressBar.style.width = "0%";
    progressContainer.style.display = "block";

    const form = new FormData();
    form.append("file", fileInput.files[0]);
    form.append("expiration", document.getElementById("expiration").value);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload", true);

    xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
            progressBar.style.width = (e.loaded / e.total * 100).toFixed(2) + "%";
        }
    };

    xhr.onload = function () {
        if (xhr.status === 200) {
            const url = xhr.responseText.trim();
            result.innerHTML = `<a href="${url}" target="_blank">${url}</a>`;
        } else {
            alert("Upload failed");
        }
        progressContainer.style.display = "none";
    };

    xhr.onerror = function () {
        progressContainer.style.display = "none";
        alert("Upload error");
    };

    xhr.send(form);
}
</script>
</body>
</html>
"""


@app.route("/upload", methods=["POST"])
def uploadFile():
    if "file" not in request.files:
        abort(400)

    uploadedFile = request.files["file"]
    if uploadedFile.filename == "":
        abort(400)

    fileId = str(uuid.uuid4())
    filePath = getFilePath(fileId)
    uploadedFile.save(filePath)

    expirationValue = request.form.get("expiration", "1d")
    expiresInSeconds = parseExpiration(expirationValue)

    if not expiresInSeconds:
        abort(400)

    expiresAt = time.time() + int(expiresInSeconds)

    with open(getMetaPath(fileId), "w") as f:
        f.write(str(expiresAt))

    return f"{request.host_url.rstrip('/')}/stream/{fileId}\n", 200, {
        "Content-Type": "text/plain"
    }


@app.route("/stream/<fileId>")
def streamFile(fileId):
    if isExpired(fileId):
        abort(410)

    filePath = getFilePath(fileId)
    if not os.path.isfile(filePath):
        abort(404)

    fileSize = os.path.getsize(filePath)
    rangeHeader = request.headers.get("Range")

    if rangeHeader:
        rangeValue = rangeHeader.replace("bytes=", "")
        startStr, endStr = rangeValue.split("-")
        start = int(startStr)
        end = int(endStr) if endStr else fileSize - 1
        length = end - start + 1

        def generate():
            with open(filePath, "rb") as file:
                file.seek(start)
                remaining = length
                while remaining > 0:
                    data = file.read(min(chunkSize, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        response = Response(generate(), status=206, mimetype="application/octet-stream")
        response.headers["Content-Range"] = f"bytes {start}-{end}/{fileSize}"
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Content-Length"] = str(length)
        return response

    def generate():
        with open(filePath, "rb") as file:
            while True:
                data = file.read(chunkSize)
                if not data:
                    break
                yield data

    response = Response(generate(), mimetype="application/octet-stream")
    response.headers["Content-Length"] = str(fileSize)
    response.headers["Accept-Ranges"] = "bytes"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5013, debug=True, threaded=True)