"""Token-based auth middleware."""
from __future__ import annotations
import hmac
import hashlib
import secrets
import time


def generate_token(secret: bytes, subject: str, ttl_seconds: int = 3600) -> str:
    """Generate a signed token of form 'subject.expiry.signature'."""
    expiry = int(time.time()) + ttl_seconds
    payload = f"{subject}.{expiry}".encode()
    sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:32]
    return f"{subject}.{expiry}.{sig}"


def verify_token(secret: bytes, token: str) -> str | None:
    """Verify a token and return its subject, or None if invalid/expired."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    subject, expiry_str, sig = parts
    try:
        expiry = int(expiry_str)
    except ValueError:
        return None
    if time.time() > expiry:
        return None
    payload = f"{subject}.{expiry}".encode()
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        return None
    return subject


def random_secret(n_bytes: int = 32) -> bytes:
    """Generate a cryptographically-strong random secret."""
    return secrets.token_bytes(n_bytes)
