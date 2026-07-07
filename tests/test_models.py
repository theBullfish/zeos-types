"""Pydantic model tests: valid construction, invalid input, JSON round-trip.

Note: cfa_client.py is intentionally NOT tested here (owned by another agent).
"""

import pytest
from pydantic import ValidationError

from zeos_types import (
    Signal, Score, CfaAddress, DeviceProfile, Telemetry, Identity,
    VaultEntry, ServiceEntry,
)


def _roundtrip(model):
    """Serialize to JSON and parse back; assert equality."""
    cls = type(model)
    restored = cls.model_validate_json(model.model_dump_json())
    assert restored == model
    return restored


# --------------------------------------------------------------------------
# Score — 32-lane fixed-width scoring result
# --------------------------------------------------------------------------

def test_score_valid_and_roundtrip():
    s = Score(chunk_id=1, lanes=list(range(32)), max_score=31,
              mean_score=15.5, decision="IS", source_bytes=1024, timestamp=1.0)
    assert s.decision == "IS"
    _roundtrip(s)


def test_score_requires_exactly_32_lanes():
    with pytest.raises(ValidationError):
        Score(lanes=list(range(5)))          # too few
    with pytest.raises(ValidationError):
        Score(lanes=list(range(33)))         # too many


def test_score_lane_and_max_bounds():
    with pytest.raises(ValidationError):
        Score(lanes=list(range(32)), max_score=256)  # > 255


def test_score_decision_literal_enforced():
    with pytest.raises(ValidationError):
        Score(lanes=list(range(32)), decision="MAYBE")


# --------------------------------------------------------------------------
# Signal
# --------------------------------------------------------------------------

def test_signal_valid_and_roundtrip():
    sig = Signal(id="s1", chain_id="c1", node_id="n1", data=b"payload",
                 size=7, type_tag=2, state="running", edges=["s2", "s3"])
    assert sig.data == b"payload"
    _roundtrip(sig)


def test_signal_requires_ids():
    with pytest.raises(ValidationError):
        Signal(chain_id="c1", node_id="n1")  # missing id


def test_signal_state_literal_enforced():
    with pytest.raises(ValidationError):
        Signal(id="s", chain_id="c", node_id="n", state="frozen")


def test_signal_default_state_idle():
    sig = Signal(id="s", chain_id="c", node_id="n")
    assert sig.state == "idle"
    assert sig.data is None


# --------------------------------------------------------------------------
# CfaAddress
# --------------------------------------------------------------------------

def test_cfa_address_valid_and_roundtrip():
    a = CfaAddress(segments=[1, 2, 3], topology_config="sovereign", path_string="/1/2/3")
    _roundtrip(a)


def test_cfa_address_topology_literal_enforced():
    with pytest.raises(ValidationError):
        CfaAddress(topology_config="galactic")


def test_cfa_address_defaults():
    a = CfaAddress()
    assert a.segments == []
    assert a.topology_config == "internal"


# --------------------------------------------------------------------------
# DeviceProfile
# --------------------------------------------------------------------------

def test_device_profile_valid_and_roundtrip():
    d = DeviceProfile(device_id="d1", name="Goya", device_type="accelerator",
                      vendor="Habana", memory_bytes=8 * 1024**3,
                      compute_tflops=100.0, capabilities=["gemm"])
    _roundtrip(d)


def test_device_profile_type_literal_enforced():
    with pytest.raises(ValidationError):
        DeviceProfile(device_id="d", name="x", device_type="quantum")


def test_device_profile_requires_core_fields():
    with pytest.raises(ValidationError):
        DeviceProfile(name="x")  # missing device_id


def test_device_profile_optional_nulls():
    d = DeviceProfile(device_id="d", name="x")
    assert d.compute_tflops is None
    assert d.device_type == "cpu"


# --------------------------------------------------------------------------
# Telemetry
# --------------------------------------------------------------------------

def test_telemetry_valid_and_roundtrip():
    t = Telemetry(source_service="mde", source_device="hl0", timestamp=123.4,
                  readings={"temp_c": 65.0, "power_w": 120.0})
    _roundtrip(t)


def test_telemetry_requires_source():
    with pytest.raises(ValidationError):
        Telemetry(source_device="hl0")  # missing source_service


def test_telemetry_readings_must_be_numeric():
    with pytest.raises(ValidationError):
        Telemetry(source_service="s", source_device="d",
                  readings={"temp": "hot"})


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

def test_identity_valid_and_roundtrip():
    i = Identity(user_id="u1", email="a@z.io", name="A", role="admin",
                 service_tokens={"mde": "tok"})
    _roundtrip(i)


def test_identity_requires_fields():
    with pytest.raises(ValidationError):
        Identity(email="a@z.io", name="A")  # missing user_id


def test_identity_defaults():
    i = Identity(user_id="u", email="a@z.io", name="A")
    assert i.role == "user"
    assert i.service_tokens == {}


# --------------------------------------------------------------------------
# VaultEntry
# --------------------------------------------------------------------------

def test_vault_entry_valid_and_roundtrip():
    v = VaultEntry(path="/a/b", tier="sovereign", entry_type="file",
                   version=3, data_id="blob1", size=42, prev_version=2)
    _roundtrip(v)


def test_vault_entry_tier_literal_enforced():
    with pytest.raises(ValidationError):
        VaultEntry(path="/a", tier="classified", entry_type="file", version=1)


def test_vault_entry_type_literal_enforced():
    with pytest.raises(ValidationError):
        VaultEntry(path="/a", tier="internal", entry_type="socket", version=1)


def test_vault_entry_prev_version_optional():
    v = VaultEntry(path="/a", version=0)
    assert v.prev_version is None
    assert v.tier == "internal"


# --------------------------------------------------------------------------
# ServiceEntry (registry)
# --------------------------------------------------------------------------

def test_service_entry_valid_and_roundtrip():
    e = ServiceEntry(service_id="zauth", kind="auth", base_url="http://zauth:8710",
                     capabilities=["auth", "identity"], registered_at=1.0)
    _roundtrip(e)


def test_service_entry_requires_service_id():
    with pytest.raises(ValidationError):
        ServiceEntry(kind="auth")


def test_service_entry_defaults():
    e = ServiceEntry(service_id="x")
    assert e.health_path == "/health"
    assert e.ws_url is None
    assert e.capabilities == []
