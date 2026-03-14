# Encryption stuff
# Small module avoids loading the keys and configs in the main library
# Important: this module does not come with any kind of database communications...
# It just deals with the cryptographical part of the equation...
import json
import tomllib
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# Job 1: load the keys once
def _load_keys():
    if not 'config.toml' in os.listdir():
        os.chdir(os.path.join(os.getcwd(), 'www/python/src'))
    with open('config.toml', 'rb') as f:
        config = tomllib.load(f)
    with open(config['SECRET_KEY_LOC'], 'r') as f:
        json_data = json.load(f)
    del config

    keys = {json_data['CURR_KEY']: base64.b64decode(json_data[f'KEY_{json_data["CURR_KEY"]}']),
            json_data['PREV_KEY']: base64.b64decode(json_data[f'KEY_{json_data["PREV_KEY"]}'])}

    if not keys:
        raise RuntimeError("No encryption keys configured")

    active = json_data['CURR_KEY']
    del json_data  # Discard any other information as soon as possible

    return keys, active


# Store the set of keys as global variables in the memory as soon as possible, will be needed
KEYS, ACTIVE_KEY_VERSION = _load_keys()  # Load the keys and discard any residual info asap

print(KEYS)
print([type(i) for i in KEYS.values()])


def encrypt_token(token: str) -> dict:
    """
    Encrypt a token using the active key.
    Returns a dict ready for database storage.
    In this specific instance of AES encryption, the nonce initializes some counting block.
    The nonce should be unique & contain exactly 12 bytes (96 bits)
    """

    key = KEYS[ACTIVE_KEY_VERSION]
    aes = AESGCM(key)

    nonce = os.urandom(12)

    ciphertext = aes.encrypt(
        nonce,
        token.encode(),
        None
    )

    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "version": ACTIVE_KEY_VERSION,  # Uses global variable
    }


def decrypt_token(ciphertext: str, nonce: str, key_version: int) -> str:
    """
    Decrypt a stored token.
    Nonce should be obtained from the database (but that happens in a separate module...)
    """

    key = KEYS[key_version]
    aes = AESGCM(key)

    ciphertext_bytes = base64.b64decode(ciphertext)
    nonce_bytes = base64.b64decode(nonce)

    plaintext = aes.decrypt(
        nonce_bytes,
        ciphertext_bytes,
        None
    )

    return plaintext.decode()
