import os
import re
import secrets
import time
import math
import json
import threading
import mimetypes
from flask import Flask, request, abort, render_template_string, Response, stream_with_context, send_file, jsonify
from PIL import Image, ImageFile
from urllib.parse import quote
import hashlib
from collections import deque
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)

uploadDir = os.path.abspath("uploads")
os.makedirs(uploadDir, exist_ok=True)

# Only enable if actually behind a trusted proxy
if os.environ.get("TRUST_PROXY") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# ======================
# Limits & hardening
# ======================

maxFileSize = 1024 * 1024 * 1024 # 1 GiB
app.config["MAX_CONTENT_LENGTH"] = maxFileSize

Image.MAX_IMAGE_PIXELS = 40_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = False

minAge = 3 * 60 * 60 # 3 Hours
maxAge = 10 * 24 * 60 * 60 # 10 Days

cleanupInterval = 120
lastCleanup = 0
chunkSize = 1024 * 1024
uploadRateGraceSeconds = 5
minUploadRateBytesPerSecond = 16 * 1024
uploadTimeoutSeconds = 20 * 60
maxStorageBytes = 10 * maxFileSize
tokenLength = 6
fileIdPattern = re.compile(
    r"^[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,20}$"
)
storageCounterPath = os.path.join(uploadDir, ".storage_total")
storageLock = threading.RLock()
storageInitialized = False
rateLimitWindow = 60
maxUploadsPerWindow = 20
rateLock = threading.Lock()
rateLimitLog = {}
activeUploads = {}
activeLock = threading.Lock()
maxConcurrentUploadsPerIp = 3
reservedStorageBytes = 0
multipartAllowance = 1024 * 1024
dangerousExts = {
    # active web content
    ".html", ".htm", ".xhtml", ".xht",
    ".svg",
    ".js", ".mjs", ".cjs",
    ".css",
    ".json", ".jsonp",
    ".mhtml", ".mht",

    # xml / transformation
    ".xml", ".xsl", ".xslt", ".kml", ".gpx",

    # server-side execution risks
    ".php", ".phtml", ".asp", ".aspx", ".jsp", ".cgi", ".do",

    # frontend source formats
    ".ts", ".tsx", ".jsx", ".vue",

    # optional high-risk binary/web formats
    ".wasm",
    ".map",
}


# ======================
# Helpers
# ======================

def getClientIp():
    return request.remote_addr or "unknown"

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

def readStorageTotal():
    initializeStorageIfNeeded()

    try:
        with open(storageCounterPath, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def writeStorageTotal(value):
    tmpPath = storageCounterPath + ".tmp"
    with open(tmpPath, "w", encoding="utf-8") as f:
        f.write(str(value))
    os.replace(tmpPath, storageCounterPath)


def addStorageBytes(delta):
    with storageLock:
        initializeStorageIfNeeded()

        try:
            with open(storageCounterPath, "r", encoding="utf-8") as f:
                total = int(f.read().strip())
        except Exception:
            total = 0

        total = max(0, total + delta)
        writeStorageTotal(total)
        return total

def checkRateLimit(clientKey):
    now = time.time()

    with rateLock:
        window = rateLimitLog.get(clientKey)

        if window is None:
            window = deque()
            rateLimitLog[clientKey] = window

        # remove old timestamps
        while window and now - window[0] > rateLimitWindow:
            window.popleft()

        if len(window) >= maxUploadsPerWindow:
            return False

        window.append(now)

        # cleanup stale entries occasionally
        if len(rateLimitLog) > 10000 and secrets.randbelow(100) == 0:
            expired = [
                k for k, v in rateLimitLog.items()
                if not v or now - v[-1] > rateLimitWindow * 2
            ]

            for k in expired:
                del rateLimitLog[k]

        return True

def acquireUploadSlot(ip):
    with activeLock:
        count = activeUploads.get(ip, 0)
        if count >= maxConcurrentUploadsPerIp:
            return False
        activeUploads[ip] = count + 1
        return True


def releaseUploadSlot(ip):
    with activeLock:
        if ip in activeUploads:
            activeUploads[ip] -= 1
            if activeUploads[ip] <= 0:
                del activeUploads[ip]

def getStorageTotalLocked():
    with storageLock:
        try:
            with open(storageCounterPath, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            return 0

def initializeStorageIfNeeded():
    global storageInitialized

    with storageLock:
        if storageInitialized:
            return

        if os.path.isfile(storageCounterPath):
            try:
                with open(storageCounterPath, "r", encoding="utf-8") as f:
                    int(f.read().strip())
        
                storageInitialized = True
                return
        
            except Exception:
                pass

        total = 0

        for root, _, files in os.walk(uploadDir):
            for name in files:
                if name.endswith(".meta") or name == ".storage_total":
                    continue

                path = os.path.join(root, name)

                try:
                    total += os.path.getsize(path)
                except OSError:
                    continue

        writeStorageTotal(total)
        storageInitialized = True

def tryReserveStorage(bytesToReserve):
    global reservedStorageBytes

    with storageLock:
        current = readStorageTotal()

        projected = current + (reservedStorageBytes + bytesToReserve)

        if projected < 0:
            projected = 0

        if projected > maxStorageBytes:
            return False

        reservedStorageBytes += bytesToReserve
        return True


def releaseReservedStorage(bytesToRelease):
    global reservedStorageBytes

    with storageLock:
        reservedStorageBytes = max(
            0,
            reservedStorageBytes - bytesToRelease
        )

def generateFileId():
    global tokenLength
    return secrets.token_urlsafe(tokenLength)

def safeJoin(base, path):
    fullPath = os.path.realpath(os.path.join(base, path))
    if not fullPath.startswith(os.path.abspath(base) + os.sep):
        abort(403)
    return fullPath

def sanitizeFilename(name):
    name = os.path.basename(name)
    name = name.lower().strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^a-z0-9._-]", "", name)
    name = re.sub(r"\.+", ".", name)
    return name or "file"

def getShardDirForFilename(filename):
    fileId = filename.split(".", 1)[0]
    return fileId[:2]

def getPathsForFilename(filename):
    shardDir = safeJoin(uploadDir, getShardDirForFilename(filename))
    filePath = safeJoin(shardDir, filename)
    metaPath = safeJoin(shardDir, f".{filename}.meta")
    return shardDir, filePath, metaPath

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

def getClientKey():
    ip = getClientIp()
    userAgent = request.headers.get("User-Agent", "")
    accept = request.headers.get("Accept", "")

    raw = f"{ip}|{userAgent}|{accept}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def cleanupExpiredFiles(force=False):
    global lastCleanup
    now = time.time()

    if not force and (now - lastCleanup) < cleanupInterval:
        return

    lastCleanup = now

    try:
        shardEntries = list(os.scandir(uploadDir))
    except OSError:
        return

    if not shardEntries:
        return

    for shardEntry in shardEntries:
        if not shardEntry.is_dir():
            continue
        try:
            fileEntries = list(os.scandir(shardEntry.path))
        except OSError:
            continue
        for entry in fileEntries:
            name = entry.name
            if name.endswith(".meta") or name == ".storage_total" or not entry.is_file():
                continue

            filePath = entry.path
            metaPath = os.path.join(shardEntry.path, f".{name}.meta")

            if not os.path.isfile(metaPath):
                continue

            try:
                with open(filePath, "rb"):
                    pass
            except OSError:
                continue

            try:
                with open(metaPath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                expiry = float(data["expiry"])
            except Exception:
                try:
                    os.remove(metaPath)
                except OSError:
                    pass
                continue

            if now >= expiry:
                try:
                    fileSize = os.path.getsize(filePath)
                    os.remove(filePath)
                    addStorageBytes(-fileSize)
                except OSError:
                    pass
                try:
                    os.remove(metaPath)
                except OSError:
                    pass

        try:
            if not os.listdir(shardEntry.path):
                os.rmdir(shardEntry.path)
        except OSError:
            pass

def save(fileObj, outputPath):
    written = 0
    startedAt = time.time()
    tempPath = outputPath + ".tmp"
    try:
        with open(tempPath, "wb") as out:
            while True:
                chunk = fileObj.stream.read(chunkSize)
                if not chunk:
                    break

                now = time.time()
                written += len(chunk)
                elapsed = max(now - startedAt, 0.001)

                if written > maxFileSize:
                    abort(413)
                if elapsed > uploadTimeoutSeconds:
                    abort(408)
                if elapsed > uploadRateGraceSeconds:
                    if written < minUploadRateBytesPerSecond * (elapsed - uploadRateGraceSeconds):
                        abort(408)

                out.write(chunk)

        os.replace(tempPath, outputPath)
    finally:
        if os.path.exists(tempPath):
            try:
                os.remove(tempPath)
            except OSError:
                pass

def iterFileRange(filePath, start, end, chunkSizeValue=1024 * 1024):
    try:
        with open(filePath, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(chunkSizeValue, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data
    except OSError:
        return

# ======================
# Flask hooks
# ======================

@app.before_request
def enforceLimits():
    if (
        request.content_length and
        request.content_length > maxFileSize + multipartAllowance
    ):
        abort(413)

@app.after_request
def applySecurityHeaders(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

def cleanupLoop():
    while True:
        cleanupExpiredFiles(force=False)
        time.sleep(cleanupInterval)

cleanupThread = threading.Thread(target=cleanupLoop, daemon=True)
cleanupThread.start()

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
/* ===== Progress Bar (Web 1.0 style) ===== */

.progressWrap {
    width: 100%;
    height: 10px;
    border-radius: 999px;
    background: linear-gradient(#d0d8e8, #aab7cf);
    border: 1px solid #6c7a96;
    box-shadow:
        inset 1px 1px 0 #ffffff,
        inset -1px -1px 0 #7a869e;
    overflow: hidden;
    margin-top: 6px;
}

.progressBar {
    height: 100%;
    width: 0%;
    border-radius: 999px;
    background:
        linear-gradient(
            135deg,
            rgba(255,255,255,0.25) 25%,
            rgba(0,0,0,0.05) 25%,
            rgba(0,0,0,0.05) 50%,
            rgba(255,255,255,0.25) 50%,
            rgba(255,255,255,0.25) 75%,
            rgba(0,0,0,0.05) 75%
        ),
        linear-gradient(#6fa0ff, #2f5fbf);

    background-size: 20px 20px, 100% 100%;
    animation: moveStripes 1s linear infinite;

    box-shadow:
        inset 1px 1px 0 rgba(255,255,255,0.6),
        inset -1px -1px 0 rgba(0,0,0,0.3);
}

/* Moving diagonal stripes */
@keyframes moveStripes {
    from { background-position: 0 0, 0 0; }
    to   { background-position: -20px 0, 0 0; }
}

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

    const li = document.createElement("li");
    li.textContent = file.name;

    const progressWrap = document.createElement("div");
    progressWrap.className = "progressWrap";

    const progressBar = document.createElement("div");
    progressBar.className = "progressBar";

    progressWrap.appendChild(progressBar);
    li.appendChild(progressWrap);
    out.appendChild(li);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload");

    // =========================
    // Artificial progress state
    // =========================
    let realProgress = 0;
    let displayProgress = 0;
    let uploadDone = false;
    let responseUrl = null;

    // Max catch-up movement speed for the *displayed* progress.
    // Kept deliberately low to avoid visible "jumps" when real progress leaps.
    const maxSpeed = 60 / 1000; // % per ms (60% in 1s)

    // When the tab is throttled/backgrounded, RAF can resume with a large delta.
    // Clamp delta so we don't fast-forward the animation.
    const maxDeltaMs = 80; // hard cap on per-frame delta used for animation

    let lastTime = performance.now();

    function tick(now) {
        const rawDelta = now - lastTime;
        lastTime = now;

        // Max allowed movement this frame
        const delta = Math.min(rawDelta, maxDeltaMs);
        const maxStep = maxSpeed * delta;

        // Move toward real progress
        const diff = realProgress - displayProgress;

        if (diff > 0) {
            displayProgress += Math.min(diff, maxStep);
        }

        // Clamp
        if (displayProgress > 100) {
            displayProgress = 100;
        }

        progressBar.style.width = displayProgress + "%";

        // Completion condition
        if (uploadDone && displayProgress >= 100) {
            const a = document.createElement("a");
            a.href = responseUrl;
            a.textContent = responseUrl;
            a.target = "_blank";

            li.innerHTML = "";
            li.appendChild(a);
            return;
        }

        requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);

    // =========================
    // Real progress tracking
    // =========================
    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            realProgress = (e.loaded / e.total) * 100;
        }
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            try {
                const payload = JSON.parse(xhr.responseText);
                responseUrl = payload.url;
            } catch {
                li.textContent = `${file.name} failed (bad server response)`;
                return;
            }

            if (!responseUrl) {
                li.textContent = `${file.name} failed (missing URL)`;
                return;
            }

            realProgress = 100;
            uploadDone = true;
        } else {
            li.textContent = `${file.name} failed (${xhr.status})`;
        }
    };

    xhr.onerror = () => {
        li.textContent = `${file.name} failed`;
    };

    const form = new FormData();
    form.append("file", file);

    xhr.send(form);
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
    clientIp = getClientIp()

    clientKey = getClientKey()
    
    if not checkRateLimit(clientKey):
        abort(429)

    if not acquireUploadSlot(clientIp):
        abort(429)

    reservedAmount = 0

    try:
        announcedSize = request.content_length

        # Flask multipart includes form overhead,
        # so only trust positive reasonable values.
        if announcedSize and announcedSize > 0:
            reserveSize = min(announcedSize, maxFileSize)
        else:
            reserveSize = maxFileSize

        reservedAmount = reserveSize
        
        if not tryReserveStorage(reserveSize):
            reservedAmount = 0
            abort(507)

        if "file" not in request.files:
            abort(400)

        fileObj = request.files["file"]

        if (
            fileObj.content_length and
            fileObj.content_length > maxFileSize + multipartAllowance
        ):
            abort(413)

        name = fileObj.filename or "file"

        if len(name) > 200:
            abort(400)

        name = sanitizeFilename(name)
        ext = os.path.splitext(name)[1].lower()
        name = name.strip()

        #if ext in dangerousExts:abort(400)

        if name.startswith(".") and ext == "":
            ext = name.lower()

        while True:
            fileId = generateFileId()
            finalName = f"{fileId}{ext}"
        
            shardDir, outputPath, metaPath = getPathsForFilename(finalName)
        
            if not os.path.exists(outputPath):
                break
        
        os.makedirs(shardDir, exist_ok=True)

        if getStorageTotalLocked() >= maxStorageBytes:
            abort(507)

        save(fileObj, outputPath)

        fileSize = os.path.getsize(outputPath)

        if reservedAmount > fileSize:
            releaseReservedStorage(reservedAmount - fileSize)
            reservedAmount = fileSize

        addStorageBytes(fileSize)

        expiry = calculateExpiryTimestamp(fileSize)

        with open(metaPath, "w", encoding="utf-8") as f:
            json.dump({"expiry": expiry}, f)

        url = f"{request.host_url.rstrip('/')}/{finalName}"
        return jsonify({"url": url})

    finally:
        if reservedAmount > 0:
            releaseReservedStorage(reservedAmount)

        releaseUploadSlot(clientIp)

@app.route("/<path:filename>", methods=["GET", "HEAD"])
def serveFile(filename):
    if not fileIdPattern.fullmatch(filename):
        abort(404)

    _, filePath, metaPath = getPathsForFilename(filename)

    if not os.path.isfile(filePath) or not os.path.isfile(metaPath):
        abort(404)

    fileSize = os.path.getsize(filePath)

    mimeType, _ = mimetypes.guess_type(filePath)
    mimeType = mimeType or "application/octet-stream"
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    isDangerous = ext in dangerousExts
    downloadRequested = request.args.get("download") == "true"

    asAttachment = downloadRequested or isDangerous

    status = 200
    rangeHeader = request.headers.get("Range")

    if rangeHeader:
        try:
            unit, value = rangeHeader.split("=")
            if unit != "bytes":
                abort(416)

            startStr, endStr = value.split("-")
            if startStr == "":
                suffixLength = int(endStr)
                if suffixLength <= 0:
                    abort(416)
                start = fileSize - suffixLength
                end = fileSize - 1
            elif endStr == "":
                start = int(startStr)
                end = fileSize - 1
            else:
                start = int(startStr)
                end = int(endStr)

            start = max(0, start)
            end = min(fileSize - 1, end)

            if start >= fileSize or start > end:
                abort(416)

            status = 206
        except Exception:
            abort(416)
    else:
        if request.method == "HEAD":
            response = Response(status=200, mimetype=mimeType)

            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Length"] = str(fileSize)
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                "script-src 'none'; "
                "style-src 'none'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "base-uri 'none'; "
                "form-action 'self'; "
                "frame-ancestors 'none'"
            )

            if downloadRequested:
                quoted = quote(filename)
                response.headers["Content-Disposition"] = (
                    f"attachment; filename*=UTF-8''{quoted}"
                )

                response.headers["Cache-Control"] = "private, max-age=0, no-cache"

            return response
        return send_file(filePath, mimetype=mimeType, as_attachment=asAttachment, download_name=filename)

    length = end - start + 1

    response = Response(
        stream_with_context(iterFileRange(filePath, start, end)),
        status=status,
        mimetype=mimeType,
        direct_passthrough=True
    )

    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Content-Length"] = str(length)
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "script-src 'none'; "
        "style-src 'none'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    if status == 206:
        response.headers["Content-Range"] = f"bytes {start}-{end}/{fileSize}"

    if downloadRequested:
        quoted = quote(filename)
        response.headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{quoted}"
        )

        response.headers["Cache-Control"] = "private, max-age=0, no-cache"

    return response

# ======================
# Entrypoint
# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5014, debug=True)
