from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from app.core.config import settings


def generate_password_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000)
    return digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    current_hash = hash_password(password, salt)
    return hmac.compare_digest(current_hash, expected_hash)


def hash_email_code(email: str, purpose: str, code: str) -> str:
    secret = settings.auth_token_secret
    raw = f"{email}:{purpose}:{code}:{secret}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(f"{token}{padding}".encode("utf-8"))


def create_access_token(*, user_id: int, email: str, expires_in_seconds: int, is_admin: bool = False) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "email": email,
        "is_admin": is_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(
        settings.auth_token_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        payload_part, signature_part = token.split(".", 1)
        expected_signature = hmac.new(
            settings.auth_token_secret.encode("utf-8"),
            payload_part.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_signature = _b64url_decode(signature_part)
        if not hmac.compare_digest(actual_signature, expected_signature):
            raise ValueError("Invalid token signature")
        payload_raw = _b64url_decode(payload_part)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid token format") from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(datetime.utcnow().timestamp()):
        raise ValueError("Token expired")
    return payload
