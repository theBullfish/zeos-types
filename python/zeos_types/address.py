"""CfaAddress — fractal address from CFA-lib."""

from pydantic import BaseModel, Field
from typing import Literal


class CfaAddress(BaseModel):
    segments: list[int] = Field(default_factory=list)
    topology_config: Literal["sovereign", "internal", "reference"] = "internal"
    path_string: str = ""
