import os
import re
import secrets
import time
import math
import json
import threading
import mimetypes
import heapq
import unicodedata
from collections import deque, OrderedDict
from flask import Flask, request, abort, render_template_string, Response, stream_with_context, send_file, jsonify, make_response
from PIL import Image, ImageFile
from urllib.parse import quote
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)

uploadDir = os.path.abspath("uploads")
os.makedirs(uploadDir, exist_ok=True)

# Only enable behind a trusted proxy; set PROXY_FOR_HOPS to match your chain.
trustProxy = os.environ.get("TRUST_PROXY") == "1"
proxyForHops = max(1, int(os.environ.get("PROXY_FOR_HOPS", "1")))
strictNoForwarded = os.environ.get("STRICT_NO_FORWARDED") == "1"
if trustProxy:
	app.wsgi_app = ProxyFix(
		app.wsgi_app,
		x_for=proxyForHops,
		x_proto=1,
		x_host=1,
	)

# ======================
# Limits & hardening
# ======================

maxFileSize = 1024 * 1024 * 1024 # 1 GiB
app.config["MAX_CONTENT_LENGTH"] = maxFileSize

Image.MAX_IMAGE_PIXELS = 40_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = False

minAge = 3 * 60 * 60 # 3 Hours
maxAge = 10 * 24 * 60 * 60 # 10 Days

maxSpeed = 200 / 1000 # 200% per 1000 ms
cleanupInterval = 120
lastCleanup = 0
chunkSize = 1024 * 1024
uploadRateGraceSeconds = 5
uploadRateWindowSeconds = 10
minUploadRateBytesPerSecond = 16 * 1024
uploadTimeoutSeconds = 20 * 60
maxStorageBytes = 10 * maxFileSize
tokenLength = 6
fileIdPattern = re.compile(
	r"^[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,20}$"
)
storageCounterPath = os.path.join(uploadDir, ".storage_total")
storageStatePath = os.path.join(uploadDir, ".storage_state")
storageLock = threading.RLock()
storageInitialized = False
storageTotalBytes = 0
expiryHeap = []
expiryHeapLock = threading.Lock()
expiryIndexBuilt = False
rateLimitWindow = 60
maxUploadsPerWindow = 50
maxRateLimitEntries = 10000
rateLock = threading.Lock()
rateLimitLog = OrderedDict()
uploadSessionCookie = "upload_session"
uploadSessionTtl = 24 * 60 * 60
maxUploadSessionEntries = 10000
sessionLock = threading.Lock()
uploadSessions = OrderedDict()
sessionIdPattern = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
activeUploads = OrderedDict()
activeLock = threading.Lock()
maxConcurrentUploadsPerClient = 50
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

def isValidSessionId(sessionId):
	return bool(sessionId and sessionIdPattern.fullmatch(sessionId))

def _pruneOrderedMap(mapping, maxEntries, ttlSeconds, now, isExpired):
	while len(mapping) > maxEntries:
		mapping.popitem(last=False)

	expiredKeys = [key for key, value in mapping.items() if isExpired(value, now, ttlSeconds)]
	for key in expiredKeys:
		mapping.pop(key, None)

def _touchSession(sessionId):
	now = time.time()
	uploadSessions[sessionId] = now
	uploadSessions.move_to_end(sessionId)
	_pruneOrderedMap(
		uploadSessions,
		maxUploadSessionEntries,
		uploadSessionTtl,
		now,
		lambda value, current, ttl: current - value > ttl,
	)

def createUploadSession():
	sessionId = secrets.token_urlsafe(32)

	with sessionLock:
		_touchSession(sessionId)

	return sessionId

def ensureUploadSessionForRequest():
	existing = request.cookies.get(uploadSessionCookie, "")

	if isValidSessionId(existing):
		with sessionLock:
			if existing in uploadSessions:
				_touchSession(existing)
				return existing

	return createUploadSession()

def setUploadSessionCookie(response, sessionId):
	response.set_cookie(
		uploadSessionCookie,
		sessionId,
		httponly=True,
		samesite="Strict",
		max_age=uploadSessionTtl,
		secure=request.is_secure,
	)

def getClientIdentity():
	headerSession = request.headers.get("X-Upload-Session", "").strip()
	cookieSession = request.cookies.get(uploadSessionCookie, "").strip()
	sessionId = headerSession or cookieSession

	if not isValidSessionId(sessionId):
		abort(403)

	with sessionLock:
		if sessionId not in uploadSessions:
			abort(403)
		_touchSession(sessionId)

	return sessionId

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
	with storageLock:
		return storageTotalBytes

def writeStorageState(total, reserved):
	tmpPath = storageStatePath + ".tmp"
	payload = json.dumps({"total": total, "reserved": reserved})

	with open(tmpPath, "w", encoding="utf-8") as f:
		f.write(payload)
		f.flush()
		os.fsync(f.fileno())

	os.replace(tmpPath, storageStatePath)

	legacyPath = storageCounterPath + ".tmp"
	with open(legacyPath, "w", encoding="utf-8") as f:
		f.write(str(total))
		f.flush()
		os.fsync(f.fileno())
	os.replace(legacyPath, storageCounterPath)

def _persistStorageStateLocked():
	writeStorageState(storageTotalBytes, reservedStorageBytes)

def _readStorageStateFromDisk():
	try:
		with open(storageStatePath, "r", encoding="utf-8") as f:
			data = json.load(f)
		return (
			max(0, int(data.get("total", 0))),
			max(0, int(data.get("reserved", 0))),
		)
	except Exception:
		return max(0, _readStorageTotalFromDisk()), 0

def _readStorageTotalFromDisk():
	try:
		with open(storageCounterPath, "r", encoding="utf-8") as f:
			return max(0, int(f.read().strip()))
	except Exception:
		return 0

def addStorageBytes(delta):
	global storageTotalBytes

	with storageLock:
		initializeStorageIfNeeded()
		storageTotalBytes = max(0, storageTotalBytes + delta)
		_persistStorageStateLocked()
		return storageTotalBytes

def checkRateLimit(clientKey):
	now = time.time()

	with rateLock:
		window = rateLimitLog.get(clientKey)

		if window is None:
			window = deque()
			rateLimitLog[clientKey] = window

		while window and now - window[0] > rateLimitWindow:
			window.popleft()

		if len(window) >= maxUploadsPerWindow:
			return False

		window.append(now)
		rateLimitLog.move_to_end(clientKey)

		_pruneOrderedMap(
			rateLimitLog,
			maxRateLimitEntries,
			rateLimitWindow * 2,
			now,
			lambda value, current, ttl: not value or current - value[-1] > ttl,
		)

		return True

def acquireUploadSlot(clientKey):
	with activeLock:
		count = activeUploads.get(clientKey, 0)
		if count >= maxConcurrentUploadsPerClient:
			return False
		activeUploads[clientKey] = count + 1
		activeUploads.move_to_end(clientKey)
		return True


def releaseUploadSlot(clientKey):
	with activeLock:
		if clientKey in activeUploads:
			activeUploads[clientKey] -= 1
			if activeUploads[clientKey] <= 0:
				del activeUploads[clientKey]

def getStorageTotalLocked():
	with storageLock:
		initializeStorageIfNeeded()
		return storageTotalBytes

def initializeStorageIfNeeded():
	global storageInitialized, storageTotalBytes, reservedStorageBytes

	with storageLock:
		if storageInitialized:
			return

		if os.path.isfile(storageStatePath) or os.path.isfile(storageCounterPath):
			try:
				total, _reserved = _readStorageStateFromDisk()
				storageTotalBytes = total
				# In-flight reservations cannot survive a process restart.
				reservedStorageBytes = 0
				storageInitialized = True
				_persistStorageStateLocked()
				return
			except Exception:
				pass

		total = 0

		for root, _, files in os.walk(uploadDir):
			for name in files:
				if name.endswith(".meta") or name in (".storage_total", ".storage_state"):
					continue

				path = os.path.join(root, name)

				try:
					total += os.path.getsize(path)
				except OSError:
					continue

		storageTotalBytes = total
		reservedStorageBytes = 0
		storageInitialized = True
		_persistStorageStateLocked()

def tryReserveStorage(bytesToReserve):
	global reservedStorageBytes, storageTotalBytes

	with storageLock:
		initializeStorageIfNeeded()

		projected = storageTotalBytes + reservedStorageBytes + bytesToReserve

		if projected < 0:
			projected = 0

		if projected > maxStorageBytes:
			return False

		reservedStorageBytes += bytesToReserve
		_persistStorageStateLocked()
		return True

def commitUploadedFile(reservedAmount, actualSize):
	global reservedStorageBytes, storageTotalBytes

	with storageLock:
		reservedStorageBytes = max(0, reservedStorageBytes - reservedAmount)
		storageTotalBytes += actualSize
		_persistStorageStateLocked()


def releaseReservedStorage(bytesToRelease):
	global reservedStorageBytes

	with storageLock:
		reservedStorageBytes = max(
			0,
			reservedStorageBytes - bytesToRelease
		)
		_persistStorageStateLocked()

def generateFileId():
	global tokenLength
	return secrets.token_urlsafe(tokenLength)

def safeJoin(base, path):
	baseReal = os.path.realpath(base)
	fullPath = os.path.realpath(os.path.join(baseReal, path))

	try:
		if os.path.commonpath([fullPath, baseReal]) != baseReal:
			abort(403)
	except ValueError:
		abort(403)

	return fullPath

def sanitizeFilename(name):
	name = os.path.basename(name)
	name = unicodedata.normalize("NFC", name)
	name = name.casefold().strip()
	name = re.sub(r"\s+", "-", name)
	name = re.sub(r"[^a-z0-9._-]", "", name)
	name = re.sub(r"\.+", ".", name)
	name = name.encode("ascii", "ignore").decode("ascii")
	name = name[:200]
	return name or "file"

def registerFileExpiry(expiry, filePath, metaPath):
	with expiryHeapLock:
		heapq.heappush(expiryHeap, (expiry, filePath, metaPath))

def buildExpiryIndexIfNeeded():
	global expiryIndexBuilt

	if expiryIndexBuilt:
		return

	with expiryHeapLock:
		if expiryIndexBuilt:
			return

		expiryHeap.clear()

		try:
			shardEntries = list(os.scandir(uploadDir))
		except OSError:
			expiryIndexBuilt = True
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
				if name.endswith(".meta") or not entry.is_file():
					continue

				metaPath = os.path.join(shardEntry.path, f".{name}.meta")
				if not os.path.isfile(metaPath):
					continue

				try:
					with open(metaPath, "r", encoding="utf-8") as f:
						data = json.load(f)
					expiry = float(data["expiry"])
				except Exception:
					continue

				heapq.heappush(expiryHeap, (expiry, entry.path, metaPath))

		expiryIndexBuilt = True

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
		shiftedRatio = (ratio - 0.02) / (1 - 0.02)  # normalize to 0-1
		biasedRatio = shiftedRatio ** 0.25		  # smaller exponent -> more aggressive early

	# Stronger log multiplier to collapse medium files faster
	logRatio = math.log1p(biasedRatio * 100) / math.log1p(100)

	lifetime = maxAge - (maxAge - minAge) * logRatio
	return time.time() + lifetime

def getClientKey():
	return getClientIdentity()

def cleanupExpiredFiles(force=False):
	global lastCleanup

	buildExpiryIndexIfNeeded()
	now = time.time()

	if not force and (now - lastCleanup) < cleanupInterval:
		return

	lastCleanup = now
	toDelete = []

	with expiryHeapLock:
		while expiryHeap and expiryHeap[0][0] <= now:
			expiry, filePath, metaPath = heapq.heappop(expiryHeap)
			toDelete.append((expiry, filePath, metaPath))

	bytesFreed = 0

	for expiry, filePath, metaPath in toDelete:
		if not os.path.isfile(filePath) or not os.path.isfile(metaPath):
			continue

		try:
			with open(filePath, "rb"):
				pass
		except OSError:
			continue

		try:
			with open(metaPath, "r", encoding="utf-8") as f:
				data = json.load(f)
			metaExpiry = float(data["expiry"])
		except Exception:
			try:
				os.remove(metaPath)
			except OSError:
				pass
			continue

		if metaExpiry > now:
			registerFileExpiry(metaExpiry, filePath, metaPath)
			continue

		try:
			fileSize = os.path.getsize(filePath)
			os.remove(filePath)
			bytesFreed += fileSize
		except OSError:
			pass

		try:
			os.remove(metaPath)
		except OSError:
			pass

		shardDir = os.path.dirname(filePath)
		try:
			if os.path.isdir(shardDir) and not os.listdir(shardDir):
				os.rmdir(shardDir)
		except OSError:
			pass

	if bytesFreed:
		addStorageBytes(-bytesFreed)

def save(fileObj, tempFd, tempPath, outputPath):
	written = 0
	startedAt = time.time()
	recentChunks = deque()

	try:
		with os.fdopen(tempFd, "wb") as out:
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

				recentChunks.append((now, len(chunk)))
				while recentChunks and now - recentChunks[0][0] > uploadRateWindowSeconds:
					recentChunks.popleft()

				if recentChunks and elapsed > uploadRateGraceSeconds:
					windowStart = recentChunks[0][0]
					windowDuration = max(now - windowStart, 0.001)
					windowBytes = sum(size for _, size in recentChunks)
					if windowBytes / windowDuration < minUploadRateBytesPerSecond:
						abort(408)

				out.write(chunk)

			out.flush()
			os.fsync(out.fileno())

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
		not trustProxy and
		strictNoForwarded and
		(
			request.headers.get("X-Forwarded-For") or
			request.headers.get("X-Real-IP") or
			request.headers.get("Forwarded")
		)
	):
		abort(400)

	if (
		request.content_length and
		request.content_length > maxFileSize + multipartAllowance
	):
		abort(413)

@app.after_request
def applySecurityHeaders(response):
	response.headers["X-Content-Type-Options"] = "nosniff"
	response.headers["Cache-Control"] = "no-store"
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
	sessionId = ensureUploadSessionForRequest()
	maxFileSizeHuman = formatBytes(maxFileSize)
	minAgeHuman = formatDuration(minAge)
	maxAgeHuman = formatDuration(maxAge)
	response = make_response(render_template_string("""
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

/* Make â€œresult linksâ€ feel like clickable UI */
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

  <p>You can upload files in several ways, e.g. using curl (session required):</p>
<pre>
curl -c cookies.txt -s {{ host }}/api/upload-session
curl -b cookies.txt -F "file=@/path/to/your/file.bin" {{ host }}/upload
</pre>

<p>Or piping data into curl with a file extension:</p>

<pre>
curl -s {{ host }}/api/upload-session
curl -H "X-Upload-Session: YOUR_SESSION_ID" -F "file=@-;filename=.txt" {{ host }}/upload
</pre>

<p>
You can also paste a file directly from your clipboard.<br>
Or, simply choose a file and upload it using the web interface below.
</p>

<div id="drop">
<span class="dropHint">Drag &amp; drop files here</span>
<label class="fileBtn" for="fileInput"><span class="fileBtnText">Choose file(s)</span></label>
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
	const maxSpeed = {{maxSpeed}} //60 / 1000; // % per ms (60% in 1s)

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
""", maxFileSize=maxFileSize, maxFileSizeHuman=maxFileSizeHuman, minAgeHuman=minAgeHuman, maxAgeHuman=maxAgeHuman, host=request.host_url.rstrip("/"), maxSpeed=maxSpeed))
	setUploadSessionCookie(response, sessionId)
	return response


@app.route("/api/upload-session", methods=["GET"])
def createUploadSessionRoute():
	sessionId = ensureUploadSessionForRequest()
	response = jsonify({"session": sessionId})
	setUploadSessionCookie(response, sessionId)
	return response


@app.route("/upload", methods=["POST"])
def handleUpload():
	clientKey = getClientIdentity()
	
	if not checkRateLimit(clientKey):
		abort(429)

	if not acquireUploadSlot(clientKey):
		abort(429)

	reservedAmount = 0
	tempFd = None
	tempPath = None

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

		if ext in dangerousExts:
			abort(400)

		if name.startswith(".") and ext == "":
			ext = name.lower()

		finalName = None
		outputPath = None
		metaPath = None

		while True:
			fileId = generateFileId()
			finalName = f"{fileId}{ext}"
			shardDir, outputPath, metaPath = getPathsForFilename(finalName)
			os.makedirs(shardDir, exist_ok=True)
			tempPath = outputPath + ".part"

			try:
				tempFd = os.open(tempPath, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
				break
			except FileExistsError:
				continue

		try:
			save(fileObj, tempFd, tempPath, outputPath)
		finally:
			tempFd = None

		tempPath = None

		fileSize = os.path.getsize(outputPath)
		commitUploadedFile(reservedAmount, fileSize)
		reservedAmount = 0

		expiry = calculateExpiryTimestamp(fileSize)

		try:
			with open(metaPath, "x", encoding="utf-8") as f:
				json.dump({"expiry": expiry}, f)
		except FileExistsError:
			abort(500)

		registerFileExpiry(expiry, outputPath, metaPath)

		url = f"{request.host_url.rstrip('/')}/{finalName}"
		return jsonify({"url": url})

	finally:
		if tempPath and os.path.exists(tempPath):
			try:
				os.remove(tempPath)
			except OSError:
				pass

		if reservedAmount > 0:
			releaseReservedStorage(reservedAmount)

		releaseUploadSlot(clientKey)

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
