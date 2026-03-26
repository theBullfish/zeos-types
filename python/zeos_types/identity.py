"""Identity — ZAuth universal identity."""

from pydantic import BaseModel, Field


class Identity(BaseModel):
    user_id: str
    email: str
    name: str
    role: str = "user"
    session_token: str = ""
    service_tokens: dict[str, str] = Field(default_factory=dict)
