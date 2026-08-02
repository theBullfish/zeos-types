"""CfaClient wire-format tests.

These assert that the request bodies CfaClient produces match the schema the
Rust server actually deserializes (cfa-lib/src/server.rs `Request`). This is a
shape/round-trip test — it needs no live server.

The `SERVER_SCHEMA` below mirrors server.rs field-for-field and is the contract
the client must satisfy. If server.rs changes, this test must change with it.
"""

import json

from zeos_types.cfa_client import (
    TOPOLOGIES,
    build_delegate_request,
    build_derive_request,
    build_retrieve_request,
    build_store_request,
)

# Mirror of cfa-lib/src/server.rs — required and optional fields per op.
# `op` itself is always required. Every key a builder emits must appear in
# required | optional for that op, and every required key must be present.
SERVER_SCHEMA = {
    "derive": {
        "required": {"device_secret", "process_seed"},
        "optional": {"contexts", "topology"},
    },
    "delegate": {
        "required": {"parent_path", "scope_label"},
        "optional": set(),
    },
    "store": {
        "required": {"key", "data"},
        "optional": set(),
    },
    "vault_write": {
        "required": {"key", "data"},
        "optional": set(),
    },
    "retrieve": {
        "required": {"key"},
        "optional": set(),
    },
    "vault_read": {
        "required": {"key"},
        "optional": set(),
    },
}


def _assert_matches_server(payload: dict):
    """Assert a request payload is exactly what the server accepts for its op."""
    assert "op" in payload, "every request must carry an op"
    op = payload["op"]
    assert op in SERVER_SCHEMA, f"unknown op {op!r} — server would reject it"

    schema = SERVER_SCHEMA[op]
    allowed = schema["required"] | schema["optional"] | {"op"}
    keys = set(payload)

    # No stray fields the server does not model (e.g. the old data_id/tier/path).
    extra = keys - allowed
    assert not extra, f"op {op!r} sends fields the server does not accept: {extra}"

    # Every required field present.
    missing = schema["required"] - keys
    assert not missing, f"op {op!r} missing server-required fields: {missing}"

    # Must be JSON-serializable exactly as sent on the wire.
    json.loads(json.dumps(payload))


def test_derive_request_matches_server():
    p = build_derive_request(
        device_secret="ab" * 32, process_seed="proc", contexts=["a", "b"]
    )
    _assert_matches_server(p)
    assert p["op"] == "derive"
    assert p["topology"] == "sovereign"          # server default tier
    assert p["contexts"] == ["a", "b"]
    assert len(p["device_secret"]) == 64          # 32 bytes as hex


def test_derive_defaults_empty_contexts():
    p = build_derive_request(device_secret="00" * 32, process_seed="p")
    _assert_matches_server(p)
    assert p["contexts"] == []


def test_derive_rejects_bad_topology():
    import pytest

    with pytest.raises(ValueError):
        build_derive_request("00" * 32, "p", topology="root")


def test_all_topologies_accepted():
    for t in TOPOLOGIES:
        p = build_derive_request("00" * 32, "p", topology=t)
        _assert_matches_server(p)
        assert p["topology"] == t


def test_delegate_request_matches_server():
    p = build_delegate_request(parent_path="abababab/cdcdcdcd", scope_label="reader")
    _assert_matches_server(p)
    assert p["op"] == "delegate"


def test_store_and_vault_write_match_server():
    for op in ("store", "vault_write"):
        p = build_store_request(key="k1", data="Zm9v", op=op)
        _assert_matches_server(p)
        assert p["op"] == op
        assert set(p) == {"op", "key", "data"}


def test_retrieve_and_vault_read_match_server():
    for op in ("retrieve", "vault_read"):
        p = build_retrieve_request(key="k1", op=op)
        _assert_matches_server(p)
        assert p["op"] == op
        assert set(p) == {"op", "key"}


def test_old_broken_fields_are_gone():
    """Regression guard for the original defect: none of the builders may emit
    the legacy fields the server never had (data_id, tier, path, version)."""
    legacy = {"data_id", "tier", "path", "version"}
    payloads = [
        build_derive_request("00" * 32, "p", ["c"]),
        build_delegate_request("root", "scope"),
        build_store_request("k", "ZA==", op="store"),
        build_store_request("k", "ZA==", op="vault_write"),
        build_retrieve_request("k", op="retrieve"),
        build_retrieve_request("k", op="vault_read"),
    ]
    for p in payloads:
        assert not (set(p) & legacy), f"{p['op']} still emits legacy fields"
