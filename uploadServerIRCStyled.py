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
/* ====== Web 1.0-ish look & feel ====== */
:root {
    --bg: #c0c0c0;
    --panel: #d4d0c8;
    --ink: #000;
    --link: #0000ee;
    --vlink: #551a8b;
    --hilite: #ffffff;
    --shadow: #808080;
    --darkshadow: #404040;
    --accent1: #2f5fbf;
    --accent2: #6fa0ff;
}

html, body {
    height: 100%;
}

body {
    background: var(--bg);
    color: var(--ink);
    margin: 0;
    padding: 18px 12px 28px;
    font-family: Tahoma, Verdana, Arial, sans-serif;
    font-size: 14px;
    line-height: 1.45;
}

/* A tiny dither-ish pattern to feel "old web"
body:before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,0,0,0.05) 1px, transparent 1px);
    background-size: 6px 6px;
    mix-blend-mode: multiply;
    opacity: 0.35;
}
*/

.window {
    width: min(960px, calc(100% - 16px));
    margin: 0 auto;
    background: var(--panel);
    border: 1px solid var(--darkshadow);
    box-shadow:
        inset 1px 1px 0 var(--hilite),
        inset -1px -1px 0 var(--shadow);
}

.titlebar {
    padding: 6px 10px;
    color: #fff;
    font-weight: bold;
    letter-spacing: 0.2px;
    font-size: clamp(14px, 4.3vw, 18px);
    background: linear-gradient(90deg, var(--accent1), var(--accent2));
    border-bottom: 1px solid var(--darkshadow);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.35);
}

.content {
    padding: 14px 14px 18px;
}

.toolbar {
    font-size: 12px;
    color: #111;
    background: #e7e4dc;
    border: 1px solid var(--shadow);
    box-shadow:
        inset 1px 1px 0 var(--hilite),
        inset -1px -1px 0 #b0b0b0;
    padding: 8px 10px;
    margin: 10px 0 14px;
}

.intro {
    background: linear-gradient(#ffffff, #f1efe9);
    border: 1px solid #6c7a96;
    border-radius: 12px;
    padding: 12px 12px 12px;
    box-shadow:
        inset 1px 1px 0 #ffffff,
        inset -1px -1px 0 #7a869e,
        0 2px 0 rgba(0,0,0,0.08),
        0 10px 18px rgba(0,0,0,0.06);
}

.intro p {
    margin: 0;
}

.section {
    margin: 14px 0;
    padding: 10px 10px 12px;
    background: #efeee9;
    border: 1px solid var(--shadow);
    box-shadow:
        inset 1px 1px 0 var(--hilite),
        inset -1px -1px 0 #b0b0b0;
}

.section h3 {
    margin: 0 0 12px;
    font-size: 14px;
    font-weight: bold;
    letter-spacing: 0.2px;
    color: #0b0b0b;
    padding-bottom: 6px;
    border-bottom: 1px solid #000; /* thin black line below titles */
}

hr {
    border: 0;
    height: 0;
    border-top: 1px solid var(--shadow);
    border-bottom: 1px solid var(--hilite);
    margin: 14px 0;
}

a:link { color: var(--link); text-decoration: underline; }
a:visited { color: var(--vlink); text-decoration: underline; }
a:hover { background: #fffdcf; }

/* Upload queue + returned-links panel (white only after first link) */
#outWrap {
    margin: 10px 0 0;
}

#out {
    list-style: none;
    margin: 0;
    padding: 0;
    background: transparent;
    border: 0;
    box-shadow: none;
}

#outWrap.hasLinks {
    padding: 10px;
    background: #fff;
    border: 1px solid #6c7a96;
    border-radius: 12px;
    box-shadow:
        inset 1px 1px 0 #ffffff,
        inset -1px -1px 0 #7a869e,
        0 2px 0 rgba(0,0,0,0.08);
}

#out li {
    margin: 8px 0 0;
    padding: 0;
    background: transparent;
    border: 0;
    box-shadow: none;
}

/* Make “result links” feel like clickable UI */
#out a {
    display: inline-block;
    padding: 4px 9px 5px;
    border-radius: 999px;
    text-decoration: none;
    color: #0b1a33;
    font-size: 12px;
    line-height: 1;
    vertical-align: middle;
    white-space: nowrap;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.75), rgba(255,255,255,0.12) 42%, rgba(0,0,0,0.06) 100%),
        linear-gradient(180deg, #f2f2f2, #cfcfcf);
    border: 1px solid #4a4a4a;
    box-shadow:
        0 0 0 2px #b9b9b9,
        inset 0 1px 0 rgba(255,255,255,0.85),
        inset 0 -2px 0 rgba(0,0,0,0.18),
        0 2px 0 rgba(0,0,0,0.18),
        0 6px 10px rgba(0,0,0,0.10);
    font-weight: 700;
    letter-spacing: 0.15px;
}

#out a:hover {
    filter: brightness(1.03) contrast(1.03);
}

#out a:active {
    transform: translateY(1px);
    box-shadow:
        0 0 0 2px #b9b9b9,
        inset 0 1px 0 rgba(255,255,255,0.70),
        inset 0 -1px 0 rgba(0,0,0,0.16),
        0 1px 0 rgba(0,0,0,0.20),
        0 3px 6px rgba(0,0,0,0.12);
}

pre, code {
    font-family: "Courier New", Courier, monospace;
    font-size: 13px;
}

pre {
    background:
        linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0.12) 45%, rgba(0,0,0,0.06) 100%),
        linear-gradient(180deg, #ffffff, #f3f3f3);
    border: 1px solid #4a4a4a;
    border-radius: 14px;
    box-shadow:
        0 0 0 1.5px #b9b9b9,
        inset 0 1px 0 rgba(255,255,255,0.85),
        inset 0 -2px 0 rgba(0,0,0,0.08),
        inset 2px 0 0 rgba(255,255,255,0.25),
        inset -2px 0 0 rgba(0,0,0,0.06),
        0 2px 0 rgba(0,0,0,0.12),
        0 10px 18px rgba(0,0,0,0.08);
    position: relative;
    color: #0b1a33;
    padding: 10px;
    overflow-x: auto;
    margin: 8px 0 10px;
}

pre:before {
    content: "";
    position: absolute;
    left: 12px;
    right: 12px;
    top: 6px;
    height: 36%;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0.10));
    pointer-events: none;
}

code {
    display: inline;
    padding: 1px 4px 1px;
    background: #fff7c7;
    border: 1px solid #9a8f55;
    box-shadow:
        inset 1px 1px 0 rgba(255,255,255,0.85),
        inset -1px -1px 0 rgba(0,0,0,0.10);
    font-weight: 700;
    letter-spacing: 0.15px;
    line-height: 1.2;
    vertical-align: baseline;
}

ul {
    margin: 8px 0 0 18px;
    padding: 0;
}

li {
    margin: 6px 0;
}

small {
    color: #222;
}

input[type="file"] {
    font-family: inherit;
    font-size: 13px;
    padding: 2px;
    background: #fff;
    border: 1px solid var(--shadow);
    box-shadow:
        inset 1px 1px 0 var(--hilite),
        inset -1px -1px 0 #b0b0b0;
}

/* ===== Progress Bar (already Web 1.0 style) ===== */

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

h2 {
    margin: 0;
    font-size: clamp(18px, 4.8vw, 22px);
    line-height: 1.15;
}

#drop {
    border: 1px solid var(--darkshadow);
    border-radius: 16px;
    padding: 16px 12px 14px;
    text-align: center;
    cursor: pointer;
    margin-top: 10px;
    background: linear-gradient(#ffffff, #f3f1ea);
    box-shadow:
        inset 1px 1px 0 var(--hilite),
        inset -1px -1px 0 #b0b0b0,
        inset 0 10px 18px rgba(255,255,255,0.55),
        inset 0 -10px 18px rgba(0,0,0,0.06);
}
#drop.hover {
    background: linear-gradient(#fffeea, #fff4b8);
}

.dropHint {
    display: block;
    margin-bottom: 10px;
}

/* Hide the real file input, keep it accessible via label/JS */
#fileInput {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}

/* Tactile Web 1.0 pill button with metallic rim */
.fileBtn {
    display: inline-block;
    user-select: none;
    cursor: pointer;
    font-family: Tahoma, Verdana, Arial, sans-serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.2px;
    color: #0a0a0a;

    padding: 8px 18px 9px;
    border-radius: 999px; /* semi-circle sides */

    /* border radius-safe metallic rim */
    border: 1px solid #4a4a4a;

    /* blue button body with top highlight + bottom shade */
    background:
        linear-gradient(180deg, rgba(255,255,255,0.75), rgba(255,255,255,0.10) 38%, rgba(0,0,0,0.08) 100%),
        linear-gradient(180deg, #8fb6ff, #3c6fd7);

    /* subtle diagonal sheen like your progress bar */
    box-shadow:
        0 0 0 2px #b9b9b9,
        inset 0 1px 0 rgba(255,255,255,0.75),
        inset 0 -2px 0 rgba(0,0,0,0.28),
        inset 2px 0 0 rgba(255,255,255,0.25),
        inset -2px 0 0 rgba(0,0,0,0.12),
        0 2px 0 rgba(0,0,0,0.25),
        0 6px 10px rgba(0,0,0,0.15);

    position: relative;
}

/* Metallic/etched label styling */
.fileBtnText {
    display: inline-block;
    position: relative;
    z-index: 1; /* above glossy strip */

    /* Darker colored "metal" gradient text (flat, not embossed) */
    color: #10223d; /* fallback for browsers without background-clip:text */
    background: linear-gradient(180deg, #0b1a33 0%, #415a7a 35%, #162a47 70%, #0b1a33 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;

    /* Slight "curved to pill" feel */
    transform: perspective(700px) rotateX(7deg);
    transform-origin: center;
    letter-spacing: 0.3px;
}

/* glossy top strip */
.fileBtn:before {
    content: "";
    position: absolute;
    left: 10px;
    right: 10px;
    top: 4px;
    height: 42%;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(255,255,255,0.75), rgba(255,255,255,0.10));
    pointer-events: none;
}

.fileBtn:hover {
    filter: brightness(1.03) contrast(1.03);
}

.fileBtn:active {
    transform: translateY(1px);
    box-shadow:
        0 0 0 2px #b9b9b9,
        inset 0 1px 0 rgba(255,255,255,0.55),
        inset 0 -1px 0 rgba(0,0,0,0.25),
        inset 2px 0 0 rgba(255,255,255,0.18),
        inset -2px 0 0 rgba(0,0,0,0.10),
        0 1px 0 rgba(0,0,0,0.28),
        0 3px 6px rgba(0,0,0,0.18);
}

.fileBtn:focus-visible {
    outline: none;
    box-shadow:
        0 0 0 2px #b9b9b9,
        0 0 0 4px rgba(0,0,0,0.18),
        inset 0 1px 0 rgba(255,255,255,0.75),
        inset 0 -2px 0 rgba(0,0,0,0.28),
        inset 2px 0 0 rgba(255,255,255,0.25),
        inset -2px 0 0 rgba(0,0,0,0.12),
        0 2px 0 rgba(0,0,0,0.25),
        0 6px 10px rgba(0,0,0,0.15);
}
</style>
</head>
<body>

<div class="window">
  <div class="titlebar">File Upload</div>
  <div class="content">

<div class="intro">
<p>
This service allows you to upload files and receive a short, shareable URL.
No account is required. Files are stored temporarily and are deleted automatically
after their retention period expires.
</p>
</div>

<!--div class="toolbar">
  <strong>Tip:</strong> Drag &amp; drop, click to choose files, or paste from clipboard. Multiple uploads are supported.
</div-->

<div class="section">
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
<span class="dropHint">Drag &amp; drop files here</span>
<label class="fileBtn" for="fileInput"><span class="fileBtnText">Choose file(s)…</span></label>
<input type="file" id="fileInput" multiple>
</div>

<div id="outWrap"><ul id="out"></ul></div>
</div>

<div class="section">
  <h3>File Size Limits</h3>

<p>
The maximum allowed file size is <strong>{{ maxFileSizeHuman }}</strong>.
Uploads exceeding this limit will be rejected.
</p>
</div>

<div class="section">
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
</div>

<div class="section">
  <h3>Privacy</h3>

<p>
Files are accessible only to anyone who knows the generated URL.
There is no directory listing.
</p>
</div>

<script>
const maxFileSize = {{ maxFileSize }};
const drop = document.getElementById("drop");
const input = document.getElementById("fileInput");
const out = document.getElementById("out");
const outWrap = document.getElementById("outWrap");

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
        if (displayProgress > 100) displayProgress = 100;

        progressBar.style.width = displayProgress + "%";

        // Completion condition
        if (uploadDone && displayProgress >= 100) {
            const a = document.createElement("a");
            a.href = responseUrl;
            a.textContent = responseUrl;
            a.target = "_blank";

            li.innerHTML = "";
            li.appendChild(a);
            outWrap.classList.add("hasLinks");
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
            responseUrl = xhr.responseText.trim();
            realProgress = 100; // force target to 100
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

  </div>
</div>

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
    name = sanitizeFilename(fileObj.filename or "")
    ext = os.path.splitext(name)[1].lower()
    name = name.strip()
    
    # Handle "filename=.txt" case
    if name.startswith(".") and name.count(".") == 1:
        ext = name.lower()
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
