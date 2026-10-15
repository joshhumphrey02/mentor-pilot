"""The app's single entry point to AI: model choice, retries, usage, moderation."""

import time
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.ai.pricing import Pricing
from app.ai.providers.base import ProviderError
from app.ai.registry import ProviderRegistry
from app.ai.types import (
    ChatMessage,
    Done,
    ErrorEvent,
    ModerationResult,
    ProviderEvent,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    Usage,
    UsageEvent,
)
from app.core.config import Settings
from app.models import AIUsage

logger = structlog.get_logger(__name__)

Task = Literal["chat", "title", "summary", "classify", "moderation", "test"]

# Everything except the main conversation runs on the cheaper model.
_FAST_TASKS: frozenset[str] = frozenset({"title", "summary", "classify", "moderation"})

# Shown to learners, so no vendor names, status codes or jargon.
FRIENDLY_ERRORS = {
    "rate_limited": "Your mentor is very busy right now. Please try again in a minute.",
    "unavailable": "Your mentor couldn't be reached. Please try again in a moment.",
    "not_configured": "Your mentor isn't set up yet. Please let your teacher or an admin know.",
    "auth": "Your mentor isn't set up correctly. Please let your teacher or an admin know.",
    "quota_exhausted": "Your mentor has reached its limit for now. Please try again later, "
    "or let your teacher know.",
}
DEFAULT_FRIENDLY_ERROR = "Something went wrong on our side. Please try again."


@dataclass(frozen=True)
class UsageContext:
    """Who an AI call is for, so it can be attributed and billed."""

    user_id: uuid.UUID | None = None
    school_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


@dataclass
class Completion:
    """A whole response, for callers that do not need to stream."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = "end"
    message: ChatMessage | None = None
    error: ErrorEvent | None = None


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, ProviderError) and exc.retryable


def _error_event(exc: ProviderError) -> ErrorEvent:
    return ErrorEvent(
        code=exc.code,
        message=FRIENDLY_ERRORS.get(exc.code, DEFAULT_FRIENDLY_ERROR),
        retryable=exc.retryable,
    )


class AIService:
    def __init__(
        self,
        settings: Settings,
        registry: ProviderRegistry,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.pricing = Pricing(settings)
        self._session_factory = session_factory

    def bind(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Attaches the database once the app has started."""
        self._session_factory = session_factory

    def model_for(self, task: Task) -> str:
        settings = self.settings
        override = settings.ai_task_models.get(task)
        if override:
            return override
        if task in _FAST_TASKS and settings.ai_fast_model:
            return settings.ai_fast_model
        return settings.ai_model

    async def stream_chat(
        self,
        *,
        messages: Sequence[ChatMessage],
        system: str = "",
        tools: Sequence[ToolSpec] = (),
        task: Task = "chat",
        temperature: float | None = None,
        max_tokens: int | None = None,
        context: UsageContext | None = None,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        """Streams one model response, never raising.

        Transient failures are retried with backoff, but only until the first
        event has been yielded: after that the caller has already shown part of
        an answer, and replaying would duplicate it. Any failure that survives
        ends the stream with an ErrorEvent carrying a learner-friendly message.
        """
        provider_name = provider_name or self.registry.active_name
        model = model or self.model_for(task)
        started = time.perf_counter()
        usage = Usage()
        failure: ProviderError | None = None
        stream: AsyncIterator[ProviderEvent] | None = None

        try:
            if not model:
                raise ProviderError("AI_MODEL is not set", code="not_configured")
            provider = self.registry.get(provider_name)

            async def open_stream() -> tuple[ProviderEvent, AsyncIterator[ProviderEvent]]:
                stream = provider.stream_chat(
                    messages,
                    tools,
                    system,
                    model,
                    self.settings.ai_temperature if temperature is None else temperature,
                    max_tokens or self.settings.ai_max_output_tokens,
                )
                # Awaiting the first event is what actually sends the request,
                # so this is the part worth retrying.
                return await anext(stream), stream

            opened: tuple[ProviderEvent, AsyncIterator[ProviderEvent]] = await AsyncRetrying(
                retry=retry_if_exception(_is_retryable),
                stop=stop_after_attempt(self.settings.ai_max_attempts),
                wait=wait_exponential_jitter(initial=0.5, max=8),
                reraise=True,
            )(open_stream)
            first, stream = opened

            event: ProviderEvent | None = first
            while event is not None:
                if isinstance(event, UsageEvent):
                    usage = event.usage.model_copy(
                        update={
                            "cost_usd": self.pricing.cost(
                                provider_name,
                                model,
                                event.usage.input_tokens,
                                event.usage.output_tokens,
                            )
                        }
                    )
                    event = UsageEvent(usage=usage)
                yield event
                event = await anext(stream, None)
        except ProviderError as exc:
            failure = exc
            logger.warning(
                "ai.request_failed",
                provider=provider_name,
                model=model,
                task=task,
                code=exc.code,
                detail=str(exc),
            )
            yield _error_event(exc)
        finally:
            # If the caller stopped listening early (the learner closed the
            # tab), close the provider stream so the connection is released.
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()
            await self._record(
                context=context,
                provider=provider_name,
                model=model,
                task=task,
                usage=usage,
                latency_ms=round((time.perf_counter() - started) * 1000),
                error_code=failure.code if failure else None,
            )

    async def complete(
        self,
        *,
        messages: Sequence[ChatMessage],
        system: str = "",
        tools: Sequence[ToolSpec] = (),
        task: Task = "chat",
        temperature: float | None = None,
        max_tokens: int | None = None,
        context: UsageContext | None = None,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> Completion:
        """Collects a streamed response into one object."""
        result = Completion()
        parts: list[str] = []
        async for event in self.stream_chat(
            messages=messages,
            system=system,
            tools=tools,
            task=task,
            temperature=temperature,
            max_tokens=max_tokens,
            context=context,
            provider_name=provider_name,
            model=model,
        ):
            if isinstance(event, TextDelta):
                parts.append(event.text)
            elif isinstance(event, ToolCallEvent):
                result.tool_calls.append(event.call)
            elif isinstance(event, UsageEvent):
                result.usage = event.usage
            elif isinstance(event, Done):
                result.stop_reason = event.stop_reason
                result.message = event.message
            elif isinstance(event, ErrorEvent):
                result.error = event
        result.text = "".join(parts)
        return result

    async def moderate(self, text: str, *, with_title: bool = False) -> ModerationResult:
        """Checks text for content unsafe for minors, optionally naming the
        conversation it opens in the same call (see AIProvider.moderate).

        Never raises: if the check cannot be completed the result says so
        (`checked=False`), and the caller applies MODERATION_FAIL_CLOSED.
        """
        if not text.strip():
            return ModerationResult(flagged=False)
        try:
            provider = self.registry.get()

            async def call() -> ModerationResult:
                return await provider.moderate(text, with_title=with_title)

            return await AsyncRetrying(
                retry=retry_if_exception(_is_retryable),
                stop=stop_after_attempt(self.settings.ai_max_attempts),
                wait=wait_exponential_jitter(initial=0.5, max=8),
                reraise=True,
            )(call)
        except ProviderError as exc:
            logger.warning("ai.moderation_failed", code=exc.code)
            return ModerationResult(flagged=False, checked=False)

    def blocks(self, result: ModerationResult) -> bool:
        """Whether a moderation result should stop a message from going through."""
        if not result.checked:
            return self.settings.moderation_fail_closed
        return result.flagged

    async def _record(
        self,
        *,
        context: UsageContext | None,
        provider: str,
        model: str,
        task: str,
        usage: Usage,
        latency_ms: int,
        error_code: str | None,
    ) -> None:
        if self._session_factory is None:
            return
        context = context or UsageContext()
        try:
            # Its own session and transaction: usage must be recorded even when
            # the request that triggered the call fails or is abandoned.
            async with self._session_factory() as session:
                session.add(
                    AIUsage(
                        user_id=context.user_id,
                        school_id=context.school_id,
                        project_id=context.project_id,
                        provider=provider,
                        model=model or "unset",
                        task=task,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        cost_usd=usage.cost_usd,
                        latency_ms=latency_ms,
                        success=error_code is None,
                        error_code=error_code,
                    )
                )
                await session.commit()
        except Exception:
            # Losing a usage row is bad; failing the learner's request over it is worse.
            logger.exception("ai.usage_not_recorded")
