"""Telemetry — hardware readings from any service/device."""

from pydantic import BaseModel, Field


class Telemetry(BaseModel):
    source_service: str
    source_device: str
    timestamp: float = 0.0
    readings: dict[str, float] = Field(default_factory=dict)
