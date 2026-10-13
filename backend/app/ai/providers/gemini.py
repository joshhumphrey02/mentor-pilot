"""Google Gemini adapter, using the google-genai SDK."""

import base64
import uuid
from collections.abc import AsyncIterator, Sequence
from typing import cast

import httpx
from google import genai
from google.genai import errors, types

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

# Gemini does not always give function calls an id. Ours get this prefix so we
# know not to send them back as if Gemini had issued them.
_LOCAL_ID_PREFIX = "local_"

_REFUSALS = frozenset(
    {
        types.FinishReason.SAFETY,
        types.FinishReason.PROHIBITED_CONTENT,
        types.FinishReason.BLOCKLIST,
        types.FinishReason.SPII,
        types.FinishReason.RECITATION,
    }
)


def _to_contents(messages: Sequence[ChatMessage], model: str) -> list[types.Content]:
    out: list[types.Content] = []
    for message in messages:
        if message.role == "tool":
            out.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=None
                                if result.tool_call_id.startswith(_LOCAL_ID_PREFIX)
                                else result.tool_call_id,
                                name=result.name,
                                response={"error" if result.is_error else "result": result.content},
                            )
                        )
                        for result in message.tool_results
                    ],
                )
            )
        elif message.role == "assistant":
            state = message.provider_state
            if state is not None and state.provider == "gemini" and state.model == model:
                # Replay Gemini's own parts: they carry the thought signatures
                # it requires alongside function calls.
                out.append(types.Content.model_validate(state.payload))
                continue
            parts = [types.Part(text=message.text)] if message.text else []
            parts.extend(
                types.Part(function_call=types.FunctionCall(name=call.name, args=call.arguments))
                for call in message.tool_calls
            )
            out.append(types.Content(role="model", parts=parts))
        else:
            parts = [
                types.Part.from_bytes(
                    data=base64.b64decode(image.data_base64), mime_type=image.media_type
                )
                for image in message.images
            ]
            parts.append(types.Part(text=message.text))
            out.append(types.Content(role="user", parts=parts))
    return out


def _wrap(exc: Exception) -> ProviderError:
    if isinstance(exc, errors.APIError):
        return error_from_status(exc.code or 500, f"Gemini returned HTTP {exc.code}")
    return ProviderError("Could not reach Gemini", code="unavailable", retryable=True)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        *,
        fast_model: str,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout * 1000),  # milliseconds
                httpx_async_client=http_client,
            ),
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
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters_json_schema=tool.parameters,
                        )
                        for tool in tools
                    ]
                )
            ]
            if tools
            else None,
            # We run tools ourselves, in our own loop.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        text: list[str] = []
        raw_parts: list[types.Part] = []
        calls: list[ToolCall] = []
        usage = Usage()
        finish: types.FinishReason | None = None
        blocked = False

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=model,
                # list[Content] is valid here; the SDK's union is just not covariant.
                contents=cast("types.ContentListUnion", _to_contents(messages, model)),
                config=config,
            )
            async for chunk in stream:
                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    blocked = True
                meta = chunk.usage_metadata
                if meta is not None:
                    usage = Usage(
                        input_tokens=meta.prompt_token_count or 0,
                        # Thinking tokens are billed as output.
                        output_tokens=(meta.candidates_token_count or 0)
                        + (meta.thoughts_token_count or 0),
                    )
                candidate = chunk.candidates[0] if chunk.candidates else None
                if candidate is None:
                    continue
                if candidate.finish_reason:
                    finish = candidate.finish_reason
                for part in (candidate.content.parts if candidate.content else None) or []:
                    raw_parts.append(part)
                    if part.function_call is not None:
                        call = ToolCall(
                            id=part.function_call.id or f"{_LOCAL_ID_PREFIX}{uuid.uuid4().hex}",
                            name=part.function_call.name or "",
                            arguments=dict(part.function_call.args or {}),
                        )
                        calls.append(call)
                    elif part.text and not part.thought:
                        text.append(part.text)
                        yield TextDelta(text=part.text)
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc

        if finish in (
            types.FinishReason.MALFORMED_FUNCTION_CALL,
            types.FinishReason.UNEXPECTED_TOOL_CALL,
        ):
            raise ProviderError(
                "Gemini returned a malformed tool call", code="malformed_tool_call", retryable=True
            )

        stop_reason: StopReason
        if blocked or finish in _REFUSALS:
            stop_reason, calls = "refusal", []
        elif calls:
            stop_reason = "tool_calls"
        elif finish == types.FinishReason.MAX_TOKENS:
            stop_reason = "max_tokens"
        else:
            stop_reason = "end"

        for call in calls:
            yield ToolCallEvent(call=call)
        yield UsageEvent(usage=usage)
        yield Done(
            stop_reason=stop_reason,
            message=ChatMessage(
                role="assistant",
                text="".join(text),
                tool_calls=calls,
                provider_state=ProviderState(
                    provider=self.name,
                    model=model,
                    payload=types.Content(role="model", parts=raw_parts).model_dump(
                        mode="json", exclude_none=True
                    ),
                ),
            ),
        )

    async def moderate(self, text: str) -> ModerationResult:
        """Gemini has no standalone moderation endpoint, so the fast model classifies."""
        try:
            response = await self._client.aio.models.generate_content(
                model=self._fast_model,
                contents=safety.classifier_prompt(text),
                config=types.GenerateContentConfig(
                    system_instruction=safety.CLASSIFIER_SYSTEM,
                    max_output_tokens=256,
                    temperature=0,
                ),
            )
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc
        candidate = response.candidates[0] if response.candidates else None
        refused = bool(response.prompt_feedback and response.prompt_feedback.block_reason) or (
            candidate is not None and candidate.finish_reason in _REFUSALS
        )
        if refused:
            # Gemini's own safety filter blocking it is itself a strong signal.
            return ModerationResult(flagged=True, categories=[])
        return safety.parse_verdict(response.text or "")

    async def check(self, model: str | None) -> str:
        try:
            if model:
                await self._client.aio.models.get(model=model)
                return f"Key is valid and model '{model}' is available."
            await self._client.aio.models.list(config={"page_size": 1})
            return "Key is valid."
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc
