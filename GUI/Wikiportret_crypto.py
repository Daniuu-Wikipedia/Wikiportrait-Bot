# Encryption stuff
# Small module avoids loading the keys and configs in the main library
# Important: this module does not come with any kind of database communications...
# It just deals with the cryptographical part of the equation...
# How the keys are managed and checked: see Security_notes.md (internal, not in the repository)
import json
import base64
import os
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import Wikiportret_config

KEY_LENGTH = 32  # Bytes (AES-256)


class KeyConfigError(RuntimeError):
    """The configured keys can not be used safely: the process refuses to start rather than encrypt with a wrong key"""


class UndecryptableError(ValueError):
    """A stored secret can not be decrypted. Callers treat the secret as missing (the user logs in again)"""


def _checked_keys(current_version, current_key, previous_version=None, previous_key=None):
    """{version: key} for the current and (if any) previous key; raises KeyConfigError if they can not be used safely"""
    for name, key in (('current', current_key), ('previous', previous_key)):
        if key is not None and len(key) != KEY_LENGTH:
            raise KeyConfigError(f'The {name} encryption key has {len(key)} bytes instead of {KEY_LENGTH}')
    keys = {current_version: current_key}
    if previous_key is not None:
        if previous_version == current_version and previous_key != current_key:
            raise KeyConfigError(f'The current and previous encryption keys both have version {current_version}: '
                                 f'fix WPOR_ENC_KEY_*_VERSION (see Wikiportret_key_regen.py) before starting')
        keys.setdefault(previous_version, previous_key)
    return keys


# Job 1: load the keys once
# Preferred: the environment variables WPOR_ENC_KEY_CURRENT(_VERSION) & WPOR_ENC_KEY_PREVIOUS(_VERSION), which are
# managed by Wikiportret_key_regen.py. Fallback (local development): the json file in SECRET_KEY_LOC
def _load_keys():
    config = Wikiportret_config.load_config()
    if config.get('ENC_KEY_CURRENT'):
        if config.get('ENC_KEY_CURRENT_VERSION') is None:
            raise KeyConfigError('WPOR_ENC_KEY_CURRENT is set, but WPOR_ENC_KEY_CURRENT_VERSION is not')
        previous = None, None
        if config.get('ENC_KEY_PREVIOUS'):  # Not there before the first rotation
            if config.get('ENC_KEY_PREVIOUS_VERSION') is None:
                raise KeyConfigError('WPOR_ENC_KEY_PREVIOUS is set, but WPOR_ENC_KEY_PREVIOUS_VERSION is not')
            previous = config['ENC_KEY_PREVIOUS_VERSION'], base64.b64decode(config['ENC_KEY_PREVIOUS'])
        keys = _checked_keys(config['ENC_KEY_CURRENT_VERSION'], base64.b64decode(config['ENC_KEY_CURRENT']), *previous)
        return keys, config['ENC_KEY_CURRENT_VERSION']
    if not config.get('SECRET_KEY_LOC'):
        raise RuntimeError("No encryption keys configured (WPOR_ENC_KEY_CURRENT or SECRET_KEY_LOC)")

    # A relative path is relative to this file, not to the directory a job happens to start in
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), config['SECRET_KEY_LOC']), 'r') as f:
        json_data = json.load(f)
    del config

    keys = _checked_keys(json_data['CURR_KEY'], base64.b64decode(json_data[f'KEY_{json_data["CURR_KEY"]}']),
                         json_data['PREV_KEY'], base64.b64decode(json_data[f'KEY_{json_data["PREV_KEY"]}']))

    if not keys:
        raise RuntimeError("No encryption keys configured")

    active = json_data['CURR_KEY']
    del json_data  # Discard any other information as soon as possible

    return keys, active


# Store the set of keys as global variables in the memory as soon as possible, will be needed
KEYS, ACTIVE_KEY_VERSION = _load_keys()  # Load the keys and discard any residual info asap


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
    Raises UndecryptableError if it can not be decrypted
    """
    if key_version not in KEYS:
        raise UndecryptableError(f'Encryption key version {key_version} is not loaded (loaded: {sorted(KEYS)})')
    key = KEYS[key_version]
    aes = AESGCM(key)

    ciphertext_bytes = base64.b64decode(ciphertext)
    nonce_bytes = base64.b64decode(nonce)

    try:
        plaintext = aes.decrypt(
            nonce_bytes,
            ciphertext_bytes,
            None
        )
    except InvalidTag as error:
        raise UndecryptableError(f'Encryption key version {key_version} is not the key this token was '
                                 f'encrypted with') from error

    return plaintext.decode()
