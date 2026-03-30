from flask import Flask, render_template_string, Response, request, redirect, url_for, send_file, jsonify
from flask_sock import Sock
import json, uuid, time, base64, os, io, zipfile
from functools import wraps

app = Flask(__name__)
sock = Sock(app)

clients = {}
pendingResponses = {}
AUTH_USERS = {"user": "pass"}

# -----------------------------
# Authentication
# -----------------------------
def checkAuthHeader(authHeader):
    if not authHeader: return False
    try:
        scheme, encoded = authHeader.split(" ", 1)
        if scheme.lower() != "basic": return False
        username, password = base64.b64decode(encoded).decode().split(":", 1)
        return AUTH_USERS.get(username) == password
    except: return False

def requireAuth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        authHeader = request.headers.get("Authorization")
        if not checkAuthHeader(authHeader):
            return Response("Auth required", 401, {"WWW-Authenticate": 'Basic realm="Protected"'})
        return func(*args, **kwargs)
    return wrapper

# -----------------------------
# HTML Templates
# -----------------------------
htmlTemplate = """
<h2>Connected Clients</h2>
<ul>
{% for client in clients %}
<li><a href="/browse/{{ client }}/">{{ client }}</a></li>
{% endfor %}
</ul>
"""

browseTemplate = """
<h2>{{ clientId }}/{{ reqPath }}</h2>

<ul>
{% if reqPath %}
<li><a href="/browse/{{ clientId }}/{{ parent }}">../</a></li>
{% endif %}

{% for item in items %}
    <li>
        {% if item.isDir %}
            📁 
            <a href="/browse/{{ clientId }}/{{ (reqPath ~ '/' if reqPath else '') ~ item.name }}">
                {{ item.name }}/
            </a>
            <a href="/download/{{ clientId }}/{{ (reqPath ~ '/' if reqPath else '') ~ item.name }}">
                [Download]
            </a>
        {% else %}
            📄 
            <a href="/file/{{ clientId }}/{{ (reqPath ~ '/' if reqPath else '') ~ item.name }}">
                {{ item.name }}
            </a>
            ({{ item.size }} bytes)

            <form style="display:inline" method="POST"
                  action="/delete/{{ clientId }}/{{ (reqPath ~ '/' if reqPath else '') ~ item.name }}">
                <button type="submit">Delete</button>
            </form>

            <a href="/download/{{ clientId }}/{{ (reqPath ~ '/' if reqPath else '') ~ item.name }}">
                [Download]
            </a>
        {% endif %}
    </li>
{% endfor %}
</ul>

<h3>Upload File to this folder</h3>
<form method="POST" action="/upload/{{ clientId }}/{{ reqPath }}" enctype="multipart/form-data">
    <input type="file" name="file" required>
    <button type="submit">Upload</button>
</form>

<h3>Run Command</h3>
<input type="text" id="commandInput" style="width:400px">
<label>
    <input type="checkbox" id="asyncCheck" checked> Async
</label>
<button onclick="runCommand()">Run</button>
<pre id="commandOutput"></pre>

<h3>Client Actions</h3>
<button onclick="takeScreenshot()">Take Screenshot</button>
<div id="screenshotContainer"></div>

<script>
window.onload = function() {
    let streaming = false;
    let streamInterval;
    const videoElem = document.createElement("img");
    videoElem.style.maxWidth = "800px";
    videoElem.style.border = "1px solid #000";
    document.getElementById("videoStream").appendChild(videoElem);

    document.getElementById("streamToggle").addEventListener("change", function() {
        streaming = this.checked;
        if (streaming) startStream();
        else stopStream();
    });

    function startStream() {
        streamInterval = setInterval(() => {
            fetch(`/stream/{{ clientId }}`, { method: "POST" })
              .then(res => res.json())
              .then(data => {
                  if (data.data) {
                      // Update existing image src
                      videoElem.src = `data:image/jpeg;base64,${data.data}`;
                  }
              });
        }, 200);
    }

    function stopStream() {
        clearInterval(streamInterval);
    }

    window.runCommand = function() {
        const command = document.getElementById("commandInput").value;
        const asyncRun = document.getElementById("asyncCheck").checked;

        fetch(`/command/{{ clientId }}/{{ reqPath }}`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({command, async: asyncRun})
        })
        .then(res => res.json())
        .then(data => {
            document.getElementById("commandOutput").innerText = data.output;
        });
    };

    window.takeScreenshot = function() {
        fetch(`/screenshot/{{ clientId }}/{{ reqPath }}`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (data.data) {
                document.getElementById("screenshotContainer").innerHTML =
                    `<img src="data:image/png;base64,${data.data}" style="max-width:800px;border:1px solid #000">`;
            }
        });
    };
};
</script>

<label>
    <input type="checkbox" id="streamToggle"> Live Stream
</label>

<div id="videoStream"></div>
"""

# -----------------------------
# WebSocket handling
# -----------------------------
@sock.route("/ws")
def websocket(ws):
    try:
        raw = ws.receive()
        msg = json.loads(raw)
        authHeader = msg.get("auth")
        if not checkAuthHeader(authHeader): ws.close(); return
        clientId = msg["id"]
        clients[clientId] = ws
        print(f"Client connected: {clientId}")

        while True:
            data = ws.receive()
            if not data: break
            msg = json.loads(data)
            requestId = msg.get("requestId")
            if requestId:
                pendingResponses[requestId] = msg
    finally:
        clients.pop(clientId, None)
        print(f"Client disconnected: {clientId}")

# -----------------------------
# Send Request helper
# -----------------------------
def sendRequest(clientId, payload, timeout=10):
    ws = clients.get(clientId)
    if not ws: return None
    requestId = str(uuid.uuid4())
    payload["requestId"] = requestId
    ws.send(json.dumps(payload))
    start = time.time()
    while time.time() - start < timeout:
        if requestId in pendingResponses:
            return pendingResponses.pop(requestId)
        time.sleep(0.01)
    return None

@app.route("/stream/<clientId>", methods=["POST"])
@requireAuth
def stream(clientId):
    result = sendRequest(clientId, {"type": "stream"})
    return jsonify(result or {})

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
@requireAuth
def index():
    return render_template_string(htmlTemplate, clients=clients.keys())

@app.route("/browse/<clientId>/", defaults={"reqPath": ""}, methods=["GET"])
@app.route("/browse/<clientId>/<path:reqPath>", methods=["GET"])
@requireAuth
def browse(clientId, reqPath):
    result = sendRequest(clientId, {"type": "browse", "path": reqPath})
    if not result: return "Client offline or timeout", 404
    if result.get("error"): return f"Client error: {result['error']}", 500
    if result.get("type") == "file": return getFile(clientId, reqPath)
    parent = "/".join(reqPath.split("/")[:-1])
    return render_template_string(
        browseTemplate,
        clientId=clientId,
        reqPath=reqPath,
        parent=parent,
        items=result.get("items", []),
        commandOutput=None
    )

@app.route("/file/<clientId>/<path:reqPath>")
@requireAuth
def getFile(clientId, reqPath):
    download = request.args.get("download")
    result = sendRequest(clientId, {"type": "file", "path": reqPath})
    if not result: return "Client offline or timeout", 404
    data = bytes.fromhex(result["data"])
    if download:
        return Response(data, content_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={os.path.basename(reqPath)}"})
    return Response(data, content_type=result.get("contentType", "application/octet-stream"))

@app.route("/download/<clientId>/<path:reqPath>")
@requireAuth
def downloadFolder(clientId, reqPath):
    result = sendRequest(clientId, {"type": "browse", "path": reqPath})
    if not result:
        return "Client offline or timeout", 404

    # -------------------------
    # FILE → direct download
    # -------------------------
    if result.get("type") == "file":
        fileRes = sendRequest(clientId, {"type": "file", "path": reqPath})
        if not fileRes:
            return "Failed to fetch file", 500

        data = bytes.fromhex(fileRes["data"])
        return Response(
            data,
            content_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={os.path.basename(reqPath)}"
            }
        )

    # -------------------------
    # FOLDER → zip download
    # -------------------------
    zipBuffer = io.BytesIO()
    includeEmpty = request.args.get("includeEmpty", "true").lower() == "true"
    def addToZip(remotePath, zipPath, folderResult, zipFile, includeEmpty):
        items = folderResult.get("items", [])
    
        # -------------------------
        # CREATE EMPTY DIRECTORY
        # -------------------------
        if includeEmpty and not items:
            zipFile.writestr(zipPath + "/", "")
            return
    
        for item in items:
            childRemote = remotePath + "/" + item["name"] if remotePath else item["name"]
            childZip = zipPath + "/" + item["name"] if zipPath else item["name"]
    
            if item["isDir"]:
                subRes = sendRequest(clientId, {"type": "browse", "path": childRemote})
                if subRes:
                    # Ensure directory exists in zip (even if not empty)
                    if includeEmpty:
                        zipFile.writestr(childZip + "/", "")
    
                    addToZip(childRemote, childZip, subRes, zipFile, includeEmpty)
            else:
                fileRes = sendRequest(clientId, {"type": "file", "path": childRemote})
                if fileRes:
                    zipFile.writestr(childZip, bytes.fromhex(fileRes["data"]))
    
    with zipfile.ZipFile(zipBuffer, "w", zipfile.ZIP_DEFLATED) as zipFile:
        addToZip(reqPath, "", result, zipFile, includeEmpty)

    zipBuffer.seek(0)

    return send_file(
        zipBuffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=(os.path.basename(reqPath) or "download") + ".zip"
    )

@app.route("/upload/<clientId>/<path:reqPath>", methods=["POST"])
@requireAuth
def uploadFile(clientId, reqPath):
    file = request.files.get("file")
    if not file: return "No file uploaded", 400
    dataHex = file.read().hex()
    filename = file.filename
    result = sendRequest(clientId, {"type": "upload", "path": reqPath, "data": dataHex, "filename": filename})
    return redirect(url_for("browse", clientId=clientId, reqPath=reqPath))

@app.route("/delete/<clientId>/<path:reqPath>", methods=["POST"])
@requireAuth
def deleteFile(clientId, reqPath):
    sendRequest(clientId, {"type": "delete", "path": reqPath})
    parent = "/".join(reqPath.split("/")[:-1])
    return redirect(url_for("browse", clientId=clientId, reqPath=parent))

from flask import jsonify, request

@app.route("/command/<clientId>/<path:reqPath>", methods=["POST"])
@requireAuth
def runCommand(clientId, reqPath):
    data = request.get_json()
    command = data.get("command")
    asyncRun = data.get("async", True)
    payload = {"type": "command", "command": command, "async": asyncRun}
    
    if asyncRun:
        sendRequest(clientId, payload)
        output = "Command launched asynchronously"
    else:
        result = sendRequest(clientId, payload)
        output = result.get("output") if result else "Client offline or timeout"
    
    return jsonify({"output": output})

@app.route("/screenshot/<clientId>/<path:reqPath>", methods=["POST"])
@requireAuth
def takeScreenshot(clientId, reqPath):
    result = sendRequest(clientId, {"type": "screenshot"})
    return jsonify(result or {})

# -----------------------------
# Start server
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5015, threaded=True, debug=True)