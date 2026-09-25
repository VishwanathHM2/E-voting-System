"""RFC 6238 TOTP via pyotp. Secrets are encrypted at rest with crypto.py (AES-256-GCM)."""
import json
import pyotp
import qrcode
import io
import base64
from . import crypto
from .config import settings


def generate_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    enc = crypto.encrypt(secret)
    return json.dumps(enc)


def decrypt_secret(encrypted_blob: str) -> str:
    enc = json.loads(encrypted_blob)
    return crypto.decrypt(enc["ciphertext"], enc["nonce"], enc["tag"])


def provisioning_uri(secret: str, account_name: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=settings.TOTP_ISSUER)


def qr_code_data_uri(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def verify_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    # valid_window=1 allows +-1 step (30s) for clock skew
    return totp.verify(code, valid_window=1)
