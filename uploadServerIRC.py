import os
import re
import secrets
import time
from flask import Flask, request, send_file, abort, jsonify, render_template_string
from PIL import Image, ImageFile

app = Flask(__name__)

uploadDir = "uploads"
os.makedirs(uploadDir, exist_ok=True)

# ======================
# Limits & hardening
# ======================

maxFileSize = 512 * 1024 * 1024  # 512 MB

# Pillow bomb protection
Image.MAX_IMAGE_PIXELS = 40_000_000  # ~40MP hard limit
ImageFile.LOAD_TRUNCATED_IMAGES = False

# Max dimensions (secondary guard)
maxImageWidth = 10000
maxImageHeight = 10000

# Retention policy (seconds)
minAge = 1 * 24 * 60 * 60        # 1 day
maxAge = 10 * 24 * 60 * 60       # 10 days

allowedImageExts = {".jpg", ".jpeg", ".png", ".webp"}

# Cleanup throttling
cleanupInterval = 30  # seconds
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
    ratio = min(fileSize / maxFileSize, 1.0)
    lifetime = maxAge - (maxAge - minAge) * ratio
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

# ======================
# Image processing (safe)
# ======================

def stripMetadataAndSave(fileObj, outputPath, ext):
    if ext not in allowedImageExts:
        # Stream copy to avoid memory spikes
        with open(outputPath, "wb") as out:
            while True:
                chunk = fileObj.stream.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        return

    # Verify image without decoding pixel data
    try:
        img = Image.open(fileObj)
        img.verify()
    except Exception:
        abort(400, "Invalid or corrupted image")

    fileObj.stream.seek(0)

    try:
        img = Image.open(fileObj)
        width, height = img.size

        if width > maxImageWidth or height > maxImageHeight:
            abort(413, "Image dimensions too large")

        img = img.convert("RGB")
        cleanImage = Image.new(img.mode, img.size)
        cleanImage.putdata(list(img.getdata()))
        cleanImage.save(outputPath, optimize=True)
    except Exception:
        abort(400, "Image processing failed")

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
#drop { border: 2px dashed #888; padding: 40px; text-align: center; }
a { text-decoration: none; }
</style>
</head>
<body>

<h2>IRC File Upload</h2>

<div id="drop">
Drag & drop file here<br><br>
<input type="file" id="fileInput">
</div>

<ul id="out"></ul>

<script>
function upload(file) {
    const form = new FormData();
    form.append("file", file);

    fetch("/upload", { method: "POST", body: form })
        .then(r => r.text())
        .then(url => {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = url;
            a.textContent = url;
            a.target = "_blank";
            li.appendChild(a);
            document.getElementById("out").appendChild(li);
        });
}

const drop = document.getElementById("drop");
const input = document.getElementById("fileInput");

drop.ondragover = e => { e.preventDefault(); drop.style.background="#eee"; };
drop.ondragleave = () => drop.style.background="";
drop.ondrop = e => {
    e.preventDefault();
    drop.style.background="";
    [...e.dataTransfer.files].forEach(upload);
};

input.onchange = () => [...input.files].forEach(upload);
</script>

</body>
</html>
""")

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        abort(400)

    fileObj = request.files["file"]
    originalName = sanitizeFilename(fileObj.filename)
    ext = os.path.splitext(originalName)[1].lower()

    fileId = generateFileId()
    finalName = f"{fileId}{ext}"
    outputPath = os.path.join(uploadDir, finalName)

    stripMetadataAndSave(fileObj, outputPath, ext)

    fileSize = os.path.getsize(outputPath)
    expiry = calculateExpiryTimestamp(fileSize)

    with open(os.path.join(uploadDir, f".{finalName}.meta"), "w") as f:
        f.write(str(expiry))

    url = f"{request.host_url.rstrip('/')}/{fileId}"

    if request.headers.get("Accept") == "application/json":
        return jsonify({"url": url})

    return url + "\n", 200, {"Content-Type": "text/plain"}

@app.route("/<fileId>")
def serveFile(fileId):
    cleanupExpiredFiles()

    for name in os.listdir(uploadDir):
        if os.path.splitext(name)[0] == fileId:
            return send_file(os.path.join(uploadDir, name), as_attachment=False)

    abort(404)

# ======================
# Entrypoint
# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5014, debug=True)