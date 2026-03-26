"""CfaClient — async client for CFA-lib Unix socket server."""

from __future__ import annotations

import asyncio
import json

CFA_SOCKET = "/run/zeos/cfa.sock"


class CfaClient:
    """Async client for the CFA fractal addressing service.

    Communicates via newline-delimited JSON over a Unix domain socket.
    Requires cfa-server to be running.
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

    async def derive(self, data_id: str, tier: str = "internal") -> dict:
        return await self._request({"op": "derive", "data_id": data_id, "tier": tier})

    async def store(self, data_id: str, data: bytes, tier: str = "internal") -> dict:
        import base64
        return await self._request({
            "op": "store", "data_id": data_id,
            "data": base64.b64encode(data).decode(), "tier": tier,
        })

    async def retrieve(self, data_id: str) -> dict:
        return await self._request({"op": "retrieve", "data_id": data_id})

    async def vault_write(self, path: str, data: bytes, tier: str = "internal") -> dict:
        import base64
        return await self._request({
            "op": "vault_write", "path": path,
            "data": base64.b64encode(data).decode(), "tier": tier,
        })

    async def vault_read(self, path: str, version: int | None = None) -> dict:
        return await self._request({
            "op": "vault_read", "path": path, "version": version,
        })

    async def close(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
