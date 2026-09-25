"""
AES-256-GCM authenticated encryption service.
Used for: ballot encryption, TOTP secret at-rest encryption.
Key is loaded from env/settings, or generated once and persisted to a local
key file for local/dev runs (NOT for production - use a real secrets manager there).
"""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .config import settings

KEY_FILE = os.path.join(os.path.dirname(__file__), "..", ".local_enc_key")


def _load_or_create_key() -> bytes:
    if settings.BALLOT_ENC_KEY:
        return base64.b64decode(settings.BALLOT_ENC_KEY)
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    key = AESGCM.generate_key(bit_length=256)
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    return key


_KEY = _load_or_create_key()
_aesgcm = AESGCM(_KEY)


def encrypt(plaintext: str) -> dict:
    nonce = os.urandom(12)
    data = plaintext.encode("utf-8")
    ct = _aesgcm.encrypt(nonce, data, None)  # ciphertext includes GCM tag at the end
    ciphertext, tag = ct[:-16], ct[-16:]
    integrity_hash = hashlib.sha256(ciphertext + nonce + tag).hexdigest()
    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "tag": base64.b64encode(tag).decode(),
        "integrity_hash": integrity_hash,
    }


def decrypt(ciphertext_b64: str, nonce_b64: str, tag_b64: str) -> str:
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    tag = base64.b64decode(tag_b64)
    pt = _aesgcm.decrypt(nonce, ciphertext + tag, None)
    return pt.decode("utf-8")


def verify_integrity(ciphertext_b64: str, nonce_b64: str, tag_b64: str, expected_hash: str) -> bool:
    ciphertext = base64.b64decode(ciphertext_b64)
    nonce = base64.b64decode(nonce_b64)
    tag = base64.b64decode(tag_b64)
    return hashlib.sha256(ciphertext + nonce + tag).hexdigest() == expected_hash
