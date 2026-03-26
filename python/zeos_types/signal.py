"""Signal — maps to Z-OS struct sig_data + sig_node."""

from pydantic import BaseModel, Field
from typing import Literal


class Signal(BaseModel):
    id: str
    chain_id: str
    node_id: str
    data: bytes | None = None
    size: int = 0
    type_tag: int = 0
    state: Literal["idle", "ready", "running", "done", "error"] = "idle"
    tsc_start: int = 0
    tsc_end: int = 0
    edges: list[str] = Field(default_factory=list)
