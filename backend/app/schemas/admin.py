from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ProviderStatusOut(BaseModel):
    name: str
    active: bool
    configured: bool
    model: str | None
    fast_model: str | None
    # Present only when a health check was requested.
    healthy: bool | None = None
    detail: str | None = None


class TestChatRequest(BaseModel):
    message: Annotated[str, Field(min_length=1, max_length=2000)] = "Say hello in five words."
    task: Literal["chat", "title"] = "chat"


class TestChatResponse(BaseModel):
    provider: str
    model: str
    ok: bool
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None
    error: str | None = None
