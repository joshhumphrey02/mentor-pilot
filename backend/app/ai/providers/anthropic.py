"""Anthropic (Claude) adapter, using the Messages API."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

import anthropic
import httpx2
from anthropic import AsyncAnthropic

from app.ai import safety
from app.ai.providers.base import ProviderError, error_from_status
from app.ai.types import (
    ChatMessage,
    Done,
    Feature,
    ModerationResult,
    ProviderEvent,
    ProviderState,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    Usage,
    UsageEvent,
)

_STOP_REASONS: dict[str, StopReason] = {
    "end_turn": "end",
    "stop_sequence": "end",
    "pause_turn": "end",
    "tool_use": "tool_calls",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
}


def _to_messages(messages: Sequence[ChatMessage], model: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            # Every result for one round goes back in a single user message.
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": result.tool_call_id,
                            "content": result.content,
                            "is_error": result.is_error,
                        }
                        for result in message.tool_results
                    ],
                }
            )
        elif message.role == "assistant":
            state = message.provider_state
            if state is not None and state.provider == "anthropic" and state.model == model:
                # Replay Claude's own blocks untouched: its thinking blocks are
                # only valid if they come back exactly as they were sent.
                out.append({"role": "assistant", "content": state.payload})
                continue
            content: list[dict[str, Any]] = []
            if message.text:
                content.append({"type": "text", "text": message.text})
            content.extend(
                {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                for call in message.tool_calls
            )
            out.append({"role": "assistant", "content": content})
        else:
            blocks: list[dict[str, Any]] = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.media_type,
                        "data": image.data_base64,
                    },
                }
                for image in message.images
            ]
            blocks.append({"type": "text", "text": message.text})
            out.append({"role": "user", "content": blocks})
    return out


def _to_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    # eager_input_streaming is left off on purpose. We never show partial tool
    # input (the UI shows a skeleton until the block is complete), and without
    # it the API validates each tool input against its schema before we see it.
    return [
        {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
        for tool in tools
    ]


def _wrap(exc: anthropic.AnthropicError) -> ProviderError:
    if isinstance(exc, anthropic.APIStatusError):
        return error_from_status(
            exc.status_code, f"Anthropic returned HTTP {exc.status_code}: {exc.message}"
        )
    if isinstance(exc, anthropic.APIConnectionError):  # includes timeouts
        return ProviderError("Could not reach Anthropic", code="unavailable", retryable=True)
    return ProviderError("Anthropic request failed")


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        *,
        fast_model: str,
        timeout: float,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        # max_retries=0: AIService owns retries, so they are not multiplied.
        self._client = AsyncAnthropic(
            api_key=api_key, max_retries=0, timeout=timeout, http_client=http_client
        )
        self._fast_model = fast_model

    def supports(self, feature: Feature) -> bool:
        return feature in ("vision", "tools")

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system: str,
        model: str,
        temperature: float | None,
        max_tokens: int,
    ) -> AsyncIterator[ProviderEvent]:
        # `temperature` is deliberately not sent: current Claude models reject
        # non-default sampling parameters with a 400. Thinking is likewise left
        # at the model's default (adaptive on current models).
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": _to_messages(messages, model),
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = _to_tools(tools)

        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield TextDelta(text=event.text)
                final = await stream.get_final_message()
        except anthropic.AnthropicError as exc:
            raise _wrap(exc) from exc

        text = "".join(block.text for block in final.content if block.type == "text")
        calls: list[ToolCall] = []
        # A refusal or a hit token limit can cut a tool call off mid-input, so
        # tool calls are only trusted when the model actually stopped for them.
        if final.stop_reason == "tool_use":
            for block in final.content:
                if block.type != "tool_use":
                    continue
                if not isinstance(block.input, dict):
                    raise ProviderError(
                        "Anthropic returned a malformed tool call",
                        code="malformed_tool_call",
                        retryable=True,
                    )
                call = ToolCall(id=block.id, name=block.name, arguments=block.input)
                calls.append(call)
                yield ToolCallEvent(call=call)

        usage = final.usage
        yield UsageEvent(
            usage=Usage(
                # Cached tokens are reported separately from fresh input.
                input_tokens=usage.input_tokens
                + (usage.cache_creation_input_tokens or 0)
                + (usage.cache_read_input_tokens or 0),
                output_tokens=usage.output_tokens,
            )
        )
        yield Done(
            stop_reason=_STOP_REASONS.get(final.stop_reason or "end_turn", "end"),
            message=ChatMessage(
                role="assistant",
                text=text,
                tool_calls=calls,
                provider_state=ProviderState(
                    provider=self.name,
                    model=model,
                    payload=[
                        block.model_dump(mode="json", exclude_none=True) for block in final.content
                    ],
                ),
            ),
        )

    async def moderate(self, text: str) -> ModerationResult:
        """Anthropic has no moderation endpoint, so the fast model classifies the text."""
        try:
            response = await self._client.messages.create(
                model=self._fast_model,
                max_tokens=256,
                system=safety.CLASSIFIER_SYSTEM,
                messages=[{"role": "user", "content": safety.classifier_prompt(text)}],
            )
        except anthropic.AnthropicError as exc:
            raise _wrap(exc) from exc
        if response.stop_reason == "refusal":
            # The model declining to even classify it is itself a strong signal.
            return ModerationResult(flagged=True, categories=[])
        verdict = "".join(block.text for block in response.content if block.type == "text")
        return safety.parse_verdict(verdict)

    async def check(self, model: str | None) -> str:
        try:
            if model:
                await self._client.models.retrieve(model)
                return f"Key is valid and model '{model}' is available."
            await self._client.models.list(limit=1)
            return "Key is valid."
        except anthropic.AnthropicError as exc:
            raise _wrap(exc) from exc
