"""JSON Schema tests: every schema file is valid Draft 2020-12, and example
objects validate (or fail to validate) as expected.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
SCHEMA_FILES = sorted(SCHEMA_DIR.glob("*.schema.json"))


def _load(name):
    return json.loads((SCHEMA_DIR / name).read_text())


def test_schema_dir_has_files():
    assert SCHEMA_FILES, "no schema files found"


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_is_valid_jsonschema(path):
    schema = json.loads(path.read_text())
    # Raises SchemaError if the schema itself is malformed.
    Draft202012Validator.check_schema(schema)


# --- valid example objects ---

VALID_EXAMPLES = {
    "address.schema.json": {
        "segments": [0, 1, 2], "topology_config": "internal", "path_string": "/0/1/2",
    },
    "device.schema.json": {
        "device_id": "d1", "name": "Goya", "device_type": "accelerator",
        "vendor": "Habana", "memory_bytes": 8589934592, "capabilities": ["gemm"],
    },
    "identity.schema.json": {
        "user_id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
        "email": "brad@z.io", "name": "Brad", "role": "admin",
        "service_tokens": {"mde": "tok"},
    },
    "score.schema.json": {
        "chunk_id": 0, "lanes": list(range(32)), "max_score": 31,
        "mean_score": 12.5, "decision": "IS",
    },
    "signal.schema.json": {
        "id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
        "chain_id": "c1", "node_id": "n1", "size": 10, "type_tag": 1, "state": "ready",
    },
    "telemetry.schema.json": {
        "source_service": "mde", "source_device": "hl0",
        "timestamp": 123.4, "readings": {"temp_c": 65.0},
    },
    "vault_entry.schema.json": {
        "path": "/a/b", "tier": "sovereign", "entry_type": "file", "version": 2,
    },
}


@pytest.mark.parametrize("name,obj", VALID_EXAMPLES.items())
def test_valid_example_passes(name, obj):
    schema = _load(name)
    Draft202012Validator(schema).validate(obj)  # raises on failure


def test_every_schema_has_an_example():
    names = {p.name for p in SCHEMA_FILES}
    assert names == set(VALID_EXAMPLES), "add an example for every schema file"


# --- invalid objects must be rejected ---

INVALID_EXAMPLES = {
    # wrong enum value
    "device.schema.json": {"device_id": "d", "name": "x", "device_type": "quantum"},
    # decision not in enum
    "score.schema.json": {"chunk_id": 0, "lanes": list(range(32)), "max_score": 1,
                          "mean_score": 1.0, "decision": "MAYBE"},
    # too few lanes
    "score.schema.json#lanes": {"chunk_id": 0, "lanes": [1, 2], "max_score": 1,
                                "mean_score": 1.0, "decision": "IS"},
    # missing required field (name)
    "device.schema.json#required": {"device_id": "d", "device_type": "cpu"},
    # bad tier enum
    "vault_entry.schema.json": {"path": "/a", "tier": "classified",
                                "entry_type": "file", "version": 1},
    # lane value out of 0..255 range
    "score.schema.json#range": {"chunk_id": 0, "lanes": [999] + list(range(31)),
                                "max_score": 1, "mean_score": 1.0, "decision": "IS"},
}


@pytest.mark.parametrize("key,obj", INVALID_EXAMPLES.items())
def test_invalid_example_fails(key, obj):
    name = key.split("#")[0]
    schema = _load(name)
    assert not Draft202012Validator(schema).is_valid(obj)
