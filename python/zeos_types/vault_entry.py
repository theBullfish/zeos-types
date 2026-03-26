"""VaultEntry — bridges Z-OS vault_inode and CFA-lib VaultEntry."""

from pydantic import BaseModel
from typing import Literal


class VaultEntry(BaseModel):
    path: str
    tier: Literal["sovereign", "internal", "reference"] = "internal"
    entry_type: Literal["file", "directory", "signal", "link"] = "file"
    version: int = 0
    data_id: str = ""
    size: int = 0
    timestamp: int = 0
    prev_version: int | None = None
