"""OpenAI adapter (Responses API).

The Responses API rather than Chat Completions, because OpenAI's reasoning
models only accept function tools there.
"""

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
    ProviderState,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    Usage,
    UsageEvent,
)

_INCOMPLETE_REASONS: dict[str, StopReason] = {
    "max_output_tokens": "max_tokens",
    "content_filter": "refusal",
}


def _to_input(messages: Sequence[ChatMessage], model: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            # One output item per result; OpenAI matches them by call id.
            out.extend(
                {
                    "type": "function_call_output",
                    "call_id": result.tool_call_id,
                    "output": result.content,
                }
                for result in message.tool_results
            )
        elif message.role == "assistant":
            state = message.provider_state
            if state is not None and state.provider == "openai" and state.model == model:
                # Replay the model's own items: its reasoning has to come back
                # alongside the tool calls it led to.
                out.extend(state.payload)
                continue
            if message.text:
                out.append({"role": "assistant", "content": message.text})
            out.extend(
                {
                    "type": "function_call",
                    "call_id": call.id,
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                }
                for call in message.tool_calls
            )
        elif message.images:
            parts: list[dict[str, Any]] = (
                [{"type": "input_text", "text": message.text}] if message.text else []
            )
            parts.extend(
                {
                    "type": "input_image",
                    "image_url": f"data:{image.media_type};base64,{image.data_base64}",
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
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            # Strict mode demands a narrower JSON Schema than the tools use.
            "strict": False,
        }
        for tool in tools
    ]


def _wrap(exc: openai.OpenAIError) -> ProviderError:
    if isinstance(exc, openai.APIStatusError):
        # The vendor's own explanation goes to the server log, never to a learner.
        return error_from_status(
            exc.status_code, f"OpenAI returned HTTP {exc.status_code}: {exc.message}"
        )
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
                return await self._client.responses.create(**params, temperature=temperature)
            except openai.BadRequestError as exc:
                if "temperature" not in str(exc).lower():
                    raise
                self._fixed_temperature.add(model)
        return await self._client.responses.create(**params)

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
            "input": _to_input(messages, model),
            "max_output_tokens": max_tokens,
            "stream": True,
            # Learners' conversations are not kept on OpenAI's side. That means
            # reasoning has to travel with the request instead, encrypted.
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if system:
            params["instructions"] = system
        if tools:
            params["tools"] = _to_tools(tools)

        text: list[str] = []
        items: list[Any] = []
        final: Any = None

        try:
            stream = await self._open(params, temperature)
            async for event in stream:
                if event.type == "response.output_text.delta":
                    text.append(event.delta)
                    yield TextDelta(text=event.delta)
                elif event.type == "response.output_item.done":
                    items.append(event.item)
                elif event.type in ("response.completed", "response.incomplete"):
                    final = event.response
                elif event.type == "response.failed":
                    error = event.response.error
                    raise ProviderError(
                        f"OpenAI could not finish the response: {error.message if error else ''}",
                        code="unavailable",
                        retryable=True,
                    )
                elif event.type == "error":
                    raise ProviderError(
                        f"OpenAI reported an error: {event.message}",
                        code="unavailable",
                        retryable=True,
                    )
        except openai.OpenAIError as exc:
            raise _wrap(exc) from exc
        if final is None:
            raise ProviderError("OpenAI's response ended early", code="unavailable", retryable=True)

        calls = [_finish_call(item) for item in items if item.type == "function_call"]
        for finished in calls:
            yield ToolCallEvent(call=finished)
        usage = final.usage
        yield UsageEvent(
            usage=Usage(
                input_tokens=usage.input_tokens if usage else 0,
                # Includes the tokens spent reasoning, which are billed as output.
                output_tokens=usage.output_tokens if usage else 0,
            )
        )
        yield Done(
            stop_reason=_stop_reason(final, items, calls),
            message=ChatMessage(
                role="assistant",
                text="".join(text),
                tool_calls=calls,
                provider_state=ProviderState(
                    provider=self.name,
                    model=model,
                    payload=[item.model_dump(mode="json", exclude_none=True) for item in items],
                ),
            ),
        )

    async def moderate(self, text: str, *, with_title: bool = False) -> ModerationResult:
        # The moderation endpoint only classifies, so `with_title` is ignored
        # and conversations are named by a separate call.
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


def _stop_reason(final: Any, items: list[Any], calls: list[ToolCall]) -> StopReason:
    if calls:
        return "tool_calls"
    if final.status == "incomplete":
        reason = final.incomplete_details.reason if final.incomplete_details else None
        return _INCOMPLETE_REASONS.get(reason or "", "end")
    refused = any(
        part.type == "refusal" for item in items if item.type == "message" for part in item.content
    )
    return "refusal" if refused else "end"


def _finish_call(item: Any) -> ToolCall:
    try:
        arguments = json.loads(item.arguments or "{}")
    except json.JSONDecodeError as exc:
        # The model produced broken JSON; asking again usually fixes it.
        raise ProviderError(
            "OpenAI returned a malformed tool call", code="malformed_tool_call", retryable=True
        ) from exc
    if not isinstance(arguments, dict):
        raise ProviderError(
            "OpenAI returned a malformed tool call", code="malformed_tool_call", retryable=True
        )
    return ToolCall(id=item.call_id, name=item.name, arguments=arguments)
