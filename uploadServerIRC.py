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

maxFileSize = 1024 * 1024 * 1024 # 1 GiB
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

def formatBytes(num):
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    for unit in units:
        if num < 1024:
            return f"{num:.0f} {unit}"
        num /= 1024
    return f"{num:.0f} PiB"

def formatDuration(seconds):
    units = [
        ("day", 24 * 60 * 60),
        ("hour", 60 * 60),
        ("minute", 60),
        ("second", 1),
    ]

    parts = []
    for name, unitSeconds in units:
        value = seconds // unitSeconds
        if value:
            parts.append(f"{int(value)} {name}{'' if value == 1 else 's'}")
            seconds -= value * unitSeconds

    if not parts:
        return "0 seconds"

    if len(parts) == 1:
        return parts[0]

    return " ".join(parts[:-1]) + " and " + parts[-1]

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

@app.route("/", methods=["GET", "POST"])
def indexOrUpload():
    if request.method == "POST":
        return handleUpload()
    maxFileSizeHuman = formatBytes(maxFileSize)
    minAgeHuman = formatDuration(minAge)
    maxAgeHuman = formatDuration(maxAge)
    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>File Upload</title>
<style>
body {
    font-family: sans-serif;
    padding: 40px;
    max-width: 900px;
    margin: auto;
    line-height: 1.5;
}
h2, h3 {
    margin-top: 1.5em;
}
pre {
    background: #f5f5f5;
    padding: 12px;
    overflow-x: auto;
}
#drop {
    border: 2px dashed #888;
    padding: 40px;
    text-align: center;
    cursor: pointer;
    margin-top: 30px;
}
#drop.hover {
    background: #eee;
}
a {
    text-decoration: none;
}
small {
    color: #555;
}
</style>
</head>
<body>

<h2>File Upload</h2>

<p>
This service allows you to upload files and receive a short, shareable URL.
No account is required. Files are stored temporarily and are deleted automatically
after their retention period expires.
</p>

<h3>How To Upload</h3>

<p>You can upload files in several ways, e.g. using curl:</p>

<pre>
curl -F "file=@/path/to/your/file.bin" {{ host }}
</pre>

<p>Or piping data into curl with a file extension:</p>

<pre>
echo "hello" | curl -F "file=@-;filename=.txt" {{ host }}
</pre>

<p>
You can also paste a file directly from your clipboard.<br>
Or, simply choose a file and upload it using the web interface below.
</p>

<div id="drop">
Drag & drop files here<br><br>
<input type="file" id="fileInput" multiple>
</div>

<ul id="out"></ul>

<h3>File Size Limits</h3>

<p>
The maximum allowed file size is <strong>{{ maxFileSizeHuman }}</strong>.
Uploads exceeding this limit will be rejected.
</p>

<h3>File Retention</h3>

<p>
Files are stored for a <strong>minimum of {{ minAgeHuman }}</strong> and a
<strong>maximum of {{ maxAgeHuman }}</strong>.
</p>

<p>
How long a file is kept depends on its size. Smaller files are retained longer,
while larger files expire sooner. This relationship is biased in
favor of small files.
</p>

<p>The lifetime is calculated using the following formula:</p>

<pre>
expiry = now + ( maxAge - (maxAge - minAge) * f(size / maxSize))
</pre>

<p>
Where:
</p>

<ul>
<li><code>minAge</code> = {{ minAgeHuman }}</li>
<li><code>maxAge</code> = {{ maxAgeHuman }}</li>
<li><code>maxSize</code> = {{ maxFileSizeHuman }}</li>
<li><code>f()</code> is a non-linear, logarithmically biased function</li>
</ul>

<p>
In practice this means very small files stay close to the maximum lifetime,
while medium and large files expire progressively faster.
</p>

<h3>Privacy</h3>

<p>
Files are accessible only to anyone who knows the generated URL.
There is no directory listing.
</p>

<script>
const maxFileSize = {{ maxFileSize }};
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
        .catch(() => {
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

document.addEventListener("paste", e => {
    if (!e.clipboardData) {
        return;
    }

    const items = e.clipboardData.items;
    if (!items) {
        return;
    }

    for (let i = 0; i < items.length; i++) {
        const item = items[i];

        if (item.kind === "file") {
            const file = item.getAsFile();
            if (!file) {
                continue;
            }

            // Some clipboard images have empty names
            if (!file.name) {
                const ext = file.type ? file.type.split("/")[1] : "bin";
                const timestamp = Date.now();
                Object.defineProperty(file, "name", {
                    value: `pasted-${timestamp}.${ext}`,
                });
            }

            upload(file);
        }
    }
});
</script>

</body>
</html>
""", maxFileSize=maxFileSize, maxFileSizeHuman=maxFileSizeHuman, minAgeHuman=minAgeHuman, maxAgeHuman=maxAgeHuman, host=request.host_url.rstrip("/"))


@app.route("/upload", methods=["POST"])
def handleUpload():
    if "file" not in request.files:
        abort(400)

    fileObj = request.files["file"]
    if fileObj.content_length and fileObj.content_length > maxFileSize:
        abort(413)
    # splitext accepts str|bytes whilst fileObj.filename is str|none
    ext = os.path.splitext(fileObj.filename or "")[1].lower()
    fileId = generateFileId()
    finalName = f"{fileId}{ext}"
    outputPath = os.path.join(uploadDir, finalName)

    save(fileObj, outputPath)

    fileSize = os.path.getsize(outputPath)
    expiry = calculateExpiryTimestamp(fileSize)

    with open(os.path.join(uploadDir, f".{finalName}.meta"), "w") as f:
        f.write(str(expiry))

    url = f"{request.host_url.rstrip('/')}/{finalName}"
    return url + "\n", 200, {"Content-Type": "text/plain"}

@app.route("/<path:filename>")
def serveFile(filename):
    cleanupExpiredFiles()

    filePath = os.path.join(uploadDir, filename)
    metaPath = os.path.join(uploadDir, f".{filename}.meta")

    if not os.path.isfile(filePath) or not os.path.isfile(metaPath):
        abort(404)

    fileSize = os.path.getsize(filePath)

    mimeType, _ = mimetypes.guess_type(filePath)
    mimeType = mimeType or "application/octet-stream"

    downloadRequested = request.args.get("download") == "true"

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

    if downloadRequested:
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response

# ======================
# Entrypoint
# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5014, debug=True)
