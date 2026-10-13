"""OpenAI adapter (Chat Completions API)."""

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx2
import openai
from openai import AsyncOpenAI

from app.ai.providers.base import ProviderError, error_from_status
from app.ai.types import (
    ChatMessage,
    Done,
    Feature,
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

_STOP_REASONS: dict[str, StopReason] = {
    "stop": "end",
    "tool_calls": "tool_calls",
    "function_call": "tool_calls",
    "length": "max_tokens",
    "content_filter": "refusal",
}


def _to_messages(system: str, messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    for message in messages:
        if message.role == "tool":
            # One `tool` message per result; OpenAI matches them by call id.
            out.extend(
                {"role": "tool", "tool_call_id": result.tool_call_id, "content": result.content}
                for result in message.tool_results
            )
        elif message.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": message.text or None}
            if message.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                    for call in message.tool_calls
                ]
            out.append(entry)
        elif message.images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": message.text}]
            parts.extend(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image.media_type};base64,{image.data_base64}"},
                }
                for image in message.images
            )
            out.append({"role": "user", "content": parts})
        else:
            out.append({"role": "user", "content": message.text})
    return out


def _to_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def _wrap(exc: openai.OpenAIError) -> ProviderError:
    if isinstance(exc, openai.APIStatusError):
        return error_from_status(exc.status_code, f"OpenAI returned HTTP {exc.status_code}")
    if isinstance(exc, openai.APIConnectionError):  # includes timeouts
        return ProviderError("Could not reach OpenAI", code="unavailable", retryable=True)
    return ProviderError("OpenAI request failed")


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        *,
        moderation_model: str,
        timeout: float,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        # max_retries=0: AIService owns retries, so they are not multiplied.
        self._client = AsyncOpenAI(
            api_key=api_key, max_retries=0, timeout=timeout, http_client=http_client
        )
        self._moderation_model = moderation_model
        # Some models only accept the default temperature. They are found out
        # by their first rejection and remembered here.
        self._fixed_temperature: set[str] = set()

    def supports(self, feature: Feature) -> bool:
        return feature in ("vision", "tools")

    async def _open(self, params: dict[str, Any], temperature: float | None) -> Any:
        model = params["model"]
        if temperature is not None and model not in self._fixed_temperature:
            try:
                return await self._client.chat.completions.create(**params, temperature=temperature)
            except openai.BadRequestError as exc:
                if "temperature" not in str(exc).lower():
                    raise
                self._fixed_temperature.add(model)
        return await self._client.chat.completions.create(**params)

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system: str,
        model: str,
        temperature: float | None,
        max_tokens: int,
    ) -> AsyncIterator[ProviderEvent]:
        params: dict[str, Any] = {
            "model": model,
            "messages": _to_messages(system, messages),
            "max_completion_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            params["tools"] = _to_tools(tools)

        text: list[str] = []
        # Tool calls arrive in fragments, keyed by their index in the response.
        pending: dict[int, dict[str, str]] = {}
        finish_reason = "stop"
        usage = Usage()

        try:
            stream = await self._open(params, temperature)
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = Usage(
                        input_tokens=chunk.usage.prompt_tokens,
                        output_tokens=chunk.usage.completion_tokens,
                    )
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta
                if delta.content:
                    text.append(delta.content)
                    yield TextDelta(text=delta.content)
                for fragment in delta.tool_calls or []:
                    call = pending.setdefault(fragment.index, {"id": "", "name": "", "args": ""})
                    if fragment.id:
                        call["id"] = fragment.id
                    if fragment.function and fragment.function.name:
                        call["name"] = fragment.function.name
                    if fragment.function and fragment.function.arguments:
                        call["args"] += fragment.function.arguments
        except openai.OpenAIError as exc:
            raise _wrap(exc) from exc

        calls = [_finish_call(pending[index]) for index in sorted(pending)]
        for finished in calls:
            yield ToolCallEvent(call=finished)
        yield UsageEvent(usage=usage)
        yield Done(
            stop_reason="tool_calls" if calls else _STOP_REASONS.get(finish_reason, "end"),
            message=ChatMessage(role="assistant", text="".join(text), tool_calls=calls),
        )

    async def moderate(self, text: str) -> ModerationResult:
        try:
            response = await self._client.moderations.create(
                model=self._moderation_model, input=text
            )
        except openai.OpenAIError as exc:
            raise _wrap(exc) from exc
        result = response.results[0]
        flagged = [name for name, hit in result.categories.model_dump().items() if hit]
        return ModerationResult(flagged=result.flagged, categories=sorted(flagged))

    async def check(self, model: str | None) -> str:
        try:
            if model:
                await self._client.models.retrieve(model)
                return f"Key is valid and model '{model}' is available."
            await self._client.models.list()
            return "Key is valid."
        except openai.OpenAIError as exc:
            raise _wrap(exc) from exc


def _finish_call(raw: dict[str, str]) -> ToolCall:
    try:
        arguments = json.loads(raw["args"] or "{}")
    except json.JSONDecodeError as exc:
        # The model produced broken JSON; asking again usually fixes it.
        raise ProviderError(
            "OpenAI returned a malformed tool call", code="malformed_tool_call", retryable=True
        ) from exc
    if not isinstance(arguments, dict):
        raise ProviderError(
            "OpenAI returned a malformed tool call", code="malformed_tool_call", retryable=True
        )
    return ToolCall(id=raw["id"], name=raw["name"], arguments=arguments)
