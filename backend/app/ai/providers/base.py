from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from app.ai.types import ChatMessage, Feature, ModerationResult, ProviderEvent, ToolSpec


class ProviderError(Exception):
    """A failed provider call, normalised across vendors.

    `retryable` covers rate limits, timeouts, dropped connections and 5xx
    responses: failures where the same request may well succeed a moment later.
    """

    def __init__(
        self, message: str, *, code: str = "provider_error", retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def error_from_status(status: int, detail: str) -> ProviderError:
    """Maps an HTTP status from any vendor to the shared error shape."""
    if status == 429:
        return ProviderError(detail, code="rate_limited", retryable=True)
    if status in (401, 403):
        return ProviderError(detail, code="auth")
    if status == 408 or status >= 500:
        return ProviderError(detail, code="unavailable", retryable=True)
    return ProviderError(detail, code="bad_request")


class ProviderHealth(Protocol):
    ok: bool
    detail: str


class AIProvider(Protocol):
    name: str

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system: str,
        model: str,
        temperature: float | None,
        max_tokens: int,
    ) -> AsyncIterator[ProviderEvent]:
        """Streams one model response.

        Yields TextDelta as text arrives, then any ToolCallEvents, a
        UsageEvent, and finally exactly one Done. Raises ProviderError on
        failure (AIService turns that into an ErrorEvent after retrying).
        """
        ...

    async def moderate(self, text: str, *, with_title: bool = False) -> ModerationResult:
        """Checks text for content unsafe for minors.

        With `with_title`, the text opens a conversation and the result may
        also carry a title for it. Providers that cannot name it leave the
        title as None and the caller asks for one separately.
        """
        ...

    def supports(self, feature: Feature) -> bool: ...

    async def check(self, model: str | None) -> str:
        """Verifies the credentials (and the model, if given). Returns a short
        description on success; raises ProviderError otherwise."""
        ...
