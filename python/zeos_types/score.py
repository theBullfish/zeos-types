"""Score — TRISA 32-lane scoring result."""

from pydantic import BaseModel, Field
from typing import Literal


class Score(BaseModel):
    chunk_id: int = 0
    lanes: list[int] = Field(default_factory=list, min_length=32, max_length=32)
    max_score: int = Field(0, ge=0, le=255)
    mean_score: float = 0.0
    decision: Literal["IS", "ISNT"] = "ISNT"
    source_bytes: int = 0
    timestamp: float = 0.0
