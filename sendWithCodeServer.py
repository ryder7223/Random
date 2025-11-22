'''
Port forward this to the open internet for the client to work, I use cloudflared for this,
replace the placeholder url in the client script with the url it gives you.
'''

from flask import Flask, request, send_file, jsonify
import os, shutil, tempfile, string, random, zipfile, time, threading

app = Flask(__name__)

storageDir = tempfile.mkdtemp()
activeCodes = {}  # code -> {"lastSeen": timestamp, "token": str}

def generateCode(length=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generateToken(length=16):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

@app.route("/send", methods=["POST"])
def sendFile():
    if "file" not in request.files or "itemType" not in request.form:
        return "Invalid request", 400

    itemType = request.form["itemType"]
    uploadedFile = request.files["file"]

    code = generateCode()
    token = generateToken()

    codeDir = os.path.join(storageDir, code)
    os.makedirs(codeDir, exist_ok=True)

    zipPath = os.path.join(codeDir, "payload.zip")
    uploadedFile.save(zipPath)

    with open(os.path.join(codeDir, "type.txt"), "w") as f:
        f.write(itemType)

    activeCodes[code] = {"lastSeen": time.time(), "token": token}
    return jsonify({"code": code, "token": token})

@app.route("/receive/<code>", methods=["GET"])
def receiveFile(code):
    codeDir = os.path.join(storageDir, code)
    if not os.path.exists(codeDir):
        return "Invalid code", 404

    zipPath = os.path.join(codeDir, "payload.zip")
    if not os.path.exists(zipPath):
        return "Not ready", 400

    return send_file(zipPath, as_attachment=True, download_name="transfer.zip")

@app.route("/cleanup/<code>", methods=["DELETE"])
def cleanup(code):
    token = request.args.get("token", "")
    if code not in activeCodes or activeCodes[code]["token"] != token:
        return "Unauthorized", 403

    codeDir = os.path.join(storageDir, code)
    if os.path.exists(codeDir):
        shutil.rmtree(codeDir)
    del activeCodes[code]
    return "OK"

@app.route("/heartbeat/<code>", methods=["POST"])
def heartbeat(code):
    if code not in activeCodes:
        return "Invalid code", 404
    activeCodes[code]["lastSeen"] = time.time()
    return "OK"

def monitorCodes():
    while True:
        now = time.time()
        stale = []
        for code, data in list(activeCodes.items()):
            if now - data["lastSeen"] > 15:
                stale.append(code)
        for code in stale:
            codeDir = os.path.join(storageDir, code)
            if os.path.exists(codeDir):
                shutil.rmtree(codeDir)
            del activeCodes[code]
        time.sleep(5)

threading.Thread(target=monitorCodes, daemon=True).start()

if __name__ == "__main__":
    print(f"Storage dir: {storageDir}")
    app.run(host="0.0.0.0", port=5003)