"""The provider-neutral vocabulary the rest of the app speaks.

Nothing outside `app.ai.providers` imports a vendor SDK; adapters translate
between these shapes and each vendor's own.
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

Feature = Literal["vision", "tools", "image_gen"]
StopReason = Literal["end", "tool_calls", "max_tokens", "refusal"]


class ImageInput(BaseModel):
    media_type: str
    data_base64: str


class ToolSpec(BaseModel):
    """A tool the model may call. `parameters` is a JSON Schema object."""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False


class ProviderState(BaseModel):
    """A provider's own copy of an assistant turn, kept so it can be replayed exactly.

    Some models attach reasoning data to a turn (Claude's thinking blocks,
    Gemini's thought signatures) that must be sent back unchanged with the tool
    results, or the next request is rejected. The neutral fields on ChatMessage
    cannot carry that, so the adapter stashes its native form here and prefers
    it when the same provider and model see the message again.
    """

    provider: str
    model: str
    payload: Any


class ChatMessage(BaseModel):
    """One turn. A `tool` message carries every result for one round of tool calls."""

    role: Literal["user", "assistant", "tool"]
    text: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    provider_state: ProviderState | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    # Filled in by AIService from the pricing table; None if the model is not priced.
    cost_usd: Decimal | None = None


class ModerationResult(BaseModel):
    flagged: bool
    categories: list[str] = Field(default_factory=list)
    # False when the check itself could not be completed (provider down,
    # unparseable verdict). Callers decide whether that blocks the message.
    checked: bool = True


# --- Stream events -----------------------------------------------------------


class TextDelta(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    call: ToolCall


class UsageEvent(BaseModel):
    type: Literal["usage"] = "usage"
    usage: Usage


class Done(BaseModel):
    type: Literal["done"] = "done"
    stop_reason: StopReason
    # The complete assistant turn, ready to append to the history.
    message: ChatMessage


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    # Safe to show to a learner.
    message: str
    retryable: bool = False


ProviderEvent = TextDelta | ToolCallEvent | UsageEvent | Done | ErrorEvent
