"""Spine token auth — HMAC-based service-to-service authentication."""

import hashlib
import hmac
import time
import os

SPINE_KEY_PATH = "/etc/zeos/spine.key"
TOKEN_MAX_AGE = 30  # seconds

_key: bytes | None = None

def _load_key() -> bytes:
    global _key
    if _key is None:
        key_path = os.environ.get("SPINE_KEY_PATH", SPINE_KEY_PATH)
        with open(key_path) as f:
            _key = f.read().strip().encode()
    return _key

def generate_token(path: str) -> tuple[str, str]:
    """Generate a spine auth token. Returns (timestamp, hmac_hex)."""
    key = _load_key()
    ts = str(int(time.time()))
    msg = f"{path}:{ts}".encode()
    mac = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return ts, mac

def verify_token(path: str, timestamp: str, mac_hex: str) -> bool:
    """Verify a spine token. Returns True if valid and not expired."""
    key = _load_key()
    # Check age
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > TOKEN_MAX_AGE:
        return False
    # Check HMAC
    msg = f"{path}:{timestamp}".encode()
    expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac_hex, expected)

def auth_header(path: str) -> dict[str, str]:
    """Generate Authorization header for an outbound request."""
    ts, mac = generate_token(path)
    return {"Authorization": f"Bearer spine:{ts}:{mac}"}
