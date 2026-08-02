"""CfaClient — async client for the CFA-lib Unix socket server.

WIRE CONTRACT (authoritative source: cfa-lib/src/server.rs `Request`/`Response`)
-------------------------------------------------------------------------------
Transport: newline-delimited JSON over a Unix domain socket
           (default /run/zeos/cfa.sock, override with CFA_SOCKET).

Every request is a single JSON object with an `op` string plus the fields that
op requires. The server's `Request` struct accepts exactly these fields
(unknown fields are ignored; missing required fields return an error response):

    op = "derive"
        device_secret : str  — 64 hex chars (32 bytes), REQUIRED
        process_seed  : str  — REQUIRED
        contexts      : list[str]  — one entry per extra depth level (optional)
        topology      : "sovereign" | "internal" | "reference"  (optional,
                        server default = "sovereign")

    op = "delegate"
        parent_path  : str  — path_string of an already-derived parent, REQUIRED
        scope_label  : str  — REQUIRED

    op = "store" | "vault_write"
        key   : str  — REQUIRED
        data  : str  — REQUIRED (base64 of the raw bytes, by convention)

    op = "retrieve" | "vault_read"
        key   : str  — REQUIRED

Every response is a single JSON object:
        ok      : bool
        address : object | absent   — a serialized CfaAddress on derive/delegate
        data    : str | absent      — stored payload on retrieve/vault_read
        error   : str | absent      — present (with ok=false) on failure

NOTE: the earlier client sent {op, data_id, tier} / {path, version}. The server
never had those fields, so no request could succeed. This client now matches
server.rs field-for-field.
"""

from __future__ import annotations

import asyncio
import base64
import json

CFA_SOCKET = "/run/zeos/cfa.sock"

# Topology tiers the server accepts (see server.rs handle_derive).
TOPOLOGIES = ("sovereign", "internal", "reference")


# --------------------------------------------------------------------------
# Pure request builders — the single source of truth for wire shape. These are
# what the round-trip/shape test asserts against, and what the methods below
# send. Keeping them pure (dict in, dict out) makes the contract testable
# without a live server.
# --------------------------------------------------------------------------

def build_derive_request(
    device_secret: str,
    process_seed: str,
    contexts: list[str] | None = None,
    topology: str = "sovereign",
) -> dict:
    if topology not in TOPOLOGIES:
        raise ValueError(f"topology must be one of {TOPOLOGIES}, got {topology!r}")
    return {
        "op": "derive",
        "device_secret": device_secret,
        "process_seed": process_seed,
        "contexts": list(contexts) if contexts is not None else [],
        "topology": topology,
    }


def build_delegate_request(parent_path: str, scope_label: str) -> dict:
    return {
        "op": "delegate",
        "parent_path": parent_path,
        "scope_label": scope_label,
    }


def build_store_request(key: str, data: str, op: str = "store") -> dict:
    if op not in ("store", "vault_write"):
        raise ValueError(f"store op must be 'store' or 'vault_write', got {op!r}")
    return {"op": op, "key": key, "data": data}


def build_retrieve_request(key: str, op: str = "retrieve") -> dict:
    if op not in ("retrieve", "vault_read"):
        raise ValueError(f"retrieve op must be 'retrieve' or 'vault_read', got {op!r}")
    return {"op": op, "key": key}


class CfaClient:
    """Async client for the CFA fractal addressing service.

    Communicates via newline-delimited JSON over a Unix domain socket.
    Requires cfa-server to be running. See the module docstring for the
    exact wire contract.
    """

    def __init__(self, socket_path: str = CFA_SOCKET):
        self.socket_path = socket_path
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self):
        self._reader, self._writer = await asyncio.open_unix_connection(
            self.socket_path
        )

    async def _request(self, payload: dict) -> dict:
        if self._writer is None:
            await self.connect()
        line = json.dumps(payload) + "\n"
        self._writer.write(line.encode())
        await self._writer.drain()
        resp = await self._reader.readline()
        return json.loads(resp)

    async def derive(
        self,
        device_secret: str,
        process_seed: str,
        contexts: list[str] | None = None,
        topology: str = "sovereign",
    ) -> dict:
        """Derive a CFA address from a device secret + process seed + contexts."""
        return await self._request(
            build_derive_request(device_secret, process_seed, contexts, topology)
        )

    async def delegate(self, parent_path: str, scope_label: str) -> dict:
        """Derive a scoped delegation of an already-derived parent address."""
        return await self._request(build_delegate_request(parent_path, scope_label))

    async def store(self, key: str, data: bytes) -> dict:
        """Store raw bytes under `key` (base64-encoded into the `data` field)."""
        payload = build_store_request(key, base64.b64encode(data).decode(), op="store")
        return await self._request(payload)

    async def retrieve(self, key: str) -> dict:
        """Retrieve the payload previously stored under `key`."""
        return await self._request(build_retrieve_request(key, op="retrieve"))

    async def vault_write(self, key: str, data: bytes) -> dict:
        """Alias of `store` using the vault op name."""
        payload = build_store_request(
            key, base64.b64encode(data).decode(), op="vault_write"
        )
        return await self._request(payload)

    async def vault_read(self, key: str) -> dict:
        """Alias of `retrieve` using the vault op name."""
        return await self._request(build_retrieve_request(key, op="vault_read"))

    async def close(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
