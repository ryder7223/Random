import os
import re
import secrets
import time
import math
import mimetypes
from flask import Flask, request, abort, render_template_string, Response, stream_with_context
from PIL import Image, ImageFile

app = Flask(__name__)

uploadDir = "uploads"
os.makedirs(uploadDir, exist_ok=True)

# ======================
# Limits & hardening
# ======================

maxFileSize = 1024 * 1024 * 1024 # 1GB
app.config["MAX_CONTENT_LENGTH"] = maxFileSize

Image.MAX_IMAGE_PIXELS = 40_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = False

minAge = 3 * 60 * 60 # 3 Hours
maxAge = 10 * 24 * 60 * 60 # 10 Days

cleanupInterval = 30
lastCleanup = 0

# ======================
# Helpers
# ======================

def generateFileId():
    return secrets.token_urlsafe(6)

def sanitizeFilename(name):
    name = os.path.basename(name)
    name = name.lower().strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^a-z0-9._-]", "", name)
    return name or "file"

def calculateExpiryTimestamp(fileSize):
    size = min(fileSize, maxFileSize)
    ratio = size / maxFileSize

    # Tiny files (<20MB) stay mostly full lifetime
    if ratio < 0.02:
        biasedRatio = ratio
    else:
        # Shifted & biased ratio for medium files
        shiftedRatio = (ratio - 0.02) / (1 - 0.02)  # normalize to 0–1
        biasedRatio = shiftedRatio ** 0.25          # smaller exponent -> more aggressive early

    # Stronger log multiplier to collapse medium files faster
    logRatio = math.log1p(biasedRatio * 100) / math.log1p(100)

    lifetime = maxAge - (maxAge - minAge) * logRatio
    return time.time() + lifetime

def cleanupExpiredFiles(force=False):
    global lastCleanup
    now = time.time()

    if not force and (now - lastCleanup) < cleanupInterval:
        return

    lastCleanup = now

    for name in os.listdir(uploadDir):
        if name.endswith(".meta"):
            continue

        filePath = os.path.join(uploadDir, name)
        metaPath = os.path.join(uploadDir, f".{name}.meta")

        if not os.path.isfile(filePath) or not os.path.isfile(metaPath):
            continue

        try:
            with open(metaPath, "r") as f:
                expiry = float(f.read().strip())
        except Exception:
            continue

        if now >= expiry:
            try:
                os.remove(filePath)
                os.remove(metaPath)
            except Exception:
                pass

def save(fileObj, outputPath):
    written = 0
    with open(outputPath, "wb") as out:
        while True:
            chunk = fileObj.stream.read(1024 * 1024)
            if not chunk:
                break

            written += len(chunk)
            if written > maxFileSize:
                out.close()
                os.remove(outputPath)
                abort(413)

            out.write(chunk)

def iterFileRange(filePath, start, end, chunkSize=1024 * 1024):
    with open(filePath, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = f.read(min(chunkSize, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data

# ======================
# Flask hooks
# ======================

@app.before_request
def enforceLimitsAndCleanup():
    cleanupExpiredFiles()
    if request.content_length and request.content_length > maxFileSize:
        abort(413)

# ======================
# Routes
# ======================

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/", methods=["GET"])
def index():
    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Upload</title>
<style>
body { font-family: sans-serif; padding: 40px; }
#drop {
    border: 2px dashed #888;
    padding: 40px;
    text-align: center;
    cursor: pointer;
}
#drop.hover {
    background: #eee;
}
a { text-decoration: none; }
</style>
</head>
<body>

<h2>IRC File Upload</h2>

<div id="drop">
Drag & drop files here<br><br>
<input type="file" id="fileInput" multiple>
</div>

<ul id="out"></ul>

<script>
const maxFileSize = {{ maxFileSize }}; // 1GB
const drop = document.getElementById("drop");
const input = document.getElementById("fileInput");
const out = document.getElementById("out");

function upload(file) {
    if (file.size > maxFileSize) {
        const li = document.createElement("li");
        li.textContent = `${file.name} rejected (file too large)`;
        out.appendChild(li);
        return;
    }

    const form = new FormData();
    form.append("file", file);

    fetch("/upload", { method: "POST", body: form })
        .then(r => {
            if (!r.ok) {
                throw new Error(`Upload failed (${r.status})`);
            }
            return r.text();
        })
        .then(url => {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = url.trim();
            a.textContent = url.trim();
            a.target = "_blank";
            li.appendChild(a);
            out.appendChild(li);
        })
        .catch(err => {
            const li = document.createElement("li");
            li.textContent = `${file.name} failed`;
            out.appendChild(li);
        });
}

drop.addEventListener("dragover", e => {
    e.preventDefault();
    drop.classList.add("hover");
});

drop.addEventListener("dragleave", () => {
    drop.classList.remove("hover");
});

drop.addEventListener("drop", e => {
    e.preventDefault();
    drop.classList.remove("hover");
    [...e.dataTransfer.files].forEach(upload);
});

drop.addEventListener("click", () => input.click());

input.addEventListener("change", () => {
    [...input.files].forEach(upload);
    input.value = "";
});
</script>

</body>
</html>
""", maxFileSize=maxFileSize)

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        abort(400)

    fileObj = request.files["file"]
    if fileObj.content_length and fileObj.content_length > maxFileSize:
        abort(413)
    ext = os.path.splitext(fileObj.filename)[1].lower()

    fileId = generateFileId()
    finalName = f"{fileId}{ext}"
    outputPath = os.path.join(uploadDir, finalName)

    save(fileObj, outputPath)

    fileSize = os.path.getsize(outputPath)
    expiry = calculateExpiryTimestamp(fileSize)

    with open(os.path.join(uploadDir, f".{finalName}.meta"), "w") as f:
        f.write(str(expiry))

    url = f"{request.host_url.rstrip('/')}/{fileId}"
    return url + "\n", 200, {"Content-Type": "text/plain"}

@app.route("/<fileId>")
def serveFile(fileId):
    cleanupExpiredFiles()

    for name in os.listdir(uploadDir):
        if os.path.splitext(name)[0] != fileId:
            continue

        filePath = os.path.join(uploadDir, name)
        fileSize = os.path.getsize(filePath)

        mimeType, _ = mimetypes.guess_type(filePath)
        mimeType = mimeType or "application/octet-stream"

        rangeHeader = request.headers.get("Range")

        if rangeHeader:
            try:
                unit, value = rangeHeader.split("=")
                if unit != "bytes":
                    abort(416)

                startStr, endStr = value.split("-")
                start = int(startStr) if startStr else 0
                end = int(endStr) if endStr else fileSize - 1

                if start >= fileSize or start > end:
                    abort(416)

                status = 206
            except Exception:
                abort(416)
        else:
            start = 0
            end = fileSize - 1
            status = 200

        length = end - start + 1

        response = Response(
            stream_with_context(iterFileRange(filePath, start, end)),
            status=status,
            mimetype=mimeType,
            direct_passthrough=True
        )

        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Content-Length"] = str(length)

        if status == 206:
            response.headers["Content-Range"] = f"bytes {start}-{end}/{fileSize}"

        return response

    abort(404)

# ======================
# Entrypoint
# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5014, debug=True)
