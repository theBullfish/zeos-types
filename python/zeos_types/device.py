"""DeviceProfile — canonical hardware device type aligned with MDE."""

from pydantic import BaseModel, Field
from typing import Literal


class DeviceProfile(BaseModel):
    device_id: str
    name: str
    device_type: Literal["cpu", "gpu", "tpu", "fpga", "accelerator", "dpu", "npu"] = "cpu"
    vendor: str = ""
    memory_bytes: int = 0
    compute_tflops: float | None = None
    bandwidth_gbps: float | None = None
    thermal_c: float | None = None
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
