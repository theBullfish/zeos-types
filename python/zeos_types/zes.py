"""ZES — Zeos Event Stream. Thin wrapper around Redis Streams."""

import json
import time
from typing import Any

import redis.asyncio as aioredis

_client: aioredis.Redis | None = None

REDIS_URL = "redis://localhost:6379"


async def connect(url: str = REDIS_URL) -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(url, decode_responses=True)
    return _client


async def publish(service_id: str, category: str, data: dict[str, Any]) -> str:
    """Publish an event to zeos:{service_id}:{category} stream.
    Returns the stream entry ID."""
    client = await connect()
    stream = f"zeos:{service_id}:{category}"
    entry = {
        "service": service_id,
        "category": category,
        "timestamp": str(time.time()),
        "data": json.dumps(data),
    }
    return await client.xadd(stream, entry, maxlen=10000)


async def subscribe(stream: str, last_id: str = "$", count: int = 10, block: int = 1000):
    """Read new entries from a stream. Blocks up to `block` ms.
    Returns list of (entry_id, fields) tuples."""
    client = await connect()
    result = await client.xread({stream: last_id}, count=count, block=block)
    if not result:
        return []
    # result format: [[stream_name, [(id, fields), ...]]]
    return result[0][1]


async def subscribe_all(streams: list[str], last_ids: dict[str, str] | None = None,
                        count: int = 10, block: int = 1000):
    """Read from multiple streams at once."""
    client = await connect()
    if last_ids is None:
        last_ids = {s: "$" for s in streams}
    result = await client.xread(last_ids, count=count, block=block)
    if not result:
        return {}
    return {entry[0]: entry[1] for entry in result}


async def close():
    global _client
    if _client:
        await _client.aclose()
        _client = None
