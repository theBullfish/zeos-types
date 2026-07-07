"""HMAC spine token auth tests. Uses a temp key file via SPINE_KEY_PATH env.

spine_auth caches the key in a module global (_key); each test resets it so the
temp key is (re)loaded.
"""

import time

import pytest

from zeos_types import spine_auth


@pytest.fixture
def key_file(tmp_path, monkeypatch):
    kf = tmp_path / "spine.key"
    kf.write_text("super-secret-shared-key\n")
    monkeypatch.setenv("SPINE_KEY_PATH", str(kf))
    monkeypatch.setattr(spine_auth, "_key", None)  # force reload
    return kf


def test_generate_and_verify_roundtrip(key_file):
    ts, mac = spine_auth.generate_token("/palace/file")
    assert spine_auth.verify_token("/palace/file", ts, mac) is True


def test_wrong_path_fails(key_file):
    ts, mac = spine_auth.generate_token("/palace/file")
    assert spine_auth.verify_token("/palace/OTHER", ts, mac) is False


def test_tampered_mac_fails(key_file):
    ts, mac = spine_auth.generate_token("/x")
    bad = ("0" if mac[0] != "0" else "1") + mac[1:]
    assert spine_auth.verify_token("/x", ts, bad) is False


def test_expired_timestamp_fails(key_file):
    old_ts = str(int(time.time()) - (spine_auth.TOKEN_MAX_AGE + 5))
    # Recompute a valid MAC for the old timestamp so only age is at fault.
    import hashlib, hmac
    key = spine_auth._load_key()
    mac = hmac.new(key, f"/x:{old_ts}".encode(), hashlib.sha256).hexdigest()
    assert spine_auth.verify_token("/x", old_ts, mac) is False


def test_non_numeric_timestamp_fails(key_file):
    assert spine_auth.verify_token("/x", "not-a-number", "deadbeef") is False


def test_wrong_key_fails(key_file, tmp_path, monkeypatch):
    ts, mac = spine_auth.generate_token("/x")
    # Swap in a different key and re-load; the old MAC must no longer verify.
    other = tmp_path / "other.key"
    other.write_text("a-totally-different-key")
    monkeypatch.setenv("SPINE_KEY_PATH", str(other))
    monkeypatch.setattr(spine_auth, "_key", None)
    assert spine_auth.verify_token("/x", ts, mac) is False


def test_auth_header_format(key_file):
    hdr = spine_auth.auth_header("/palace/search")
    assert "Authorization" in hdr
    scheme, _, rest = hdr["Authorization"].partition(" ")
    assert scheme == "Bearer"
    kind, ts, mac = rest.split(":")
    assert kind == "spine"
    # The emitted header must verify.
    assert spine_auth.verify_token("/palace/search", ts, mac) is True
