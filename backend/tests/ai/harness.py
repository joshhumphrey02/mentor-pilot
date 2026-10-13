"""Runs each real adapter against a fake HTTP server speaking that vendor's wire format.

This exercises the vendor SDK's own parsing as well as our adapter, without a
network call or an API key. Each harness can queue responses and inspect what
was sent, in provider-neutral terms, so one set of contract tests covers all.
"""

import json
from typing import Any, Protocol

import httpx
import httpx2

from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.base import AIProvider, ProviderError
from app.ai.providers.fake import FakeProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.types import ChatMessage, ToolCall

MODEL = "test-model"
INPUT_TOKENS = 10
OUTPUT_TOKENS = 5


def sse(events: list[tuple[str | None, Any]]) -> bytes:
    lines: list[str] = []
    for name, data in events:
        if name:
            lines.append(f"event: {name}")
        lines.append(f"data: {data if isinstance(data, str) else json.dumps(data)}")
        lines.append("")
    return ("\n".join(lines) + "\n").encode()


class Harness(Protocol):
    name: str
    provider: AIProvider
    requests: list[dict[str, Any]]

    def queue_text(self, chunks: list[str]) -> None: ...
    def queue_tool_call(self, name: str, arguments: dict[str, Any]) -> None: ...
    def queue_error(self, status: int) -> None: ...
    def sent_system(self) -> str: ...
    def sent_tool_names(self) -> list[str]: ...
    def sent_image_count(self) -> int: ...
    def sent_tool_result(self) -> str: ...
    def sent_roles(self) -> list[str]: ...


class _HttpHarness:
    """Shared plumbing: a queue of canned HTTP responses and a log of requests."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self._queue: list[tuple[int, bytes, str]] = []

    def _next(self, body: bytes) -> tuple[int, bytes, dict[str, str]]:
        self.requests.append(json.loads(body))
        status, content, content_type = self._queue.pop(0)
        return status, content, {"content-type": content_type}

    def _handle2(self, request: httpx2.Request) -> httpx2.Response:
        status, content, headers = self._next(request.content)
        return httpx2.Response(status, content=content, headers=headers)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        status, content, headers = self._next(request.content)
        return httpx.Response(status, content=content, headers=headers)

    def _stream(self, events: list[tuple[str | None, Any]]) -> None:
        self._queue.append((200, sse(events), "text/event-stream"))

    def _json(self, status: int, body: Any) -> None:
        self._queue.append((status, json.dumps(body).encode(), "application/json"))

    @property
    def last(self) -> dict[str, Any]:
        return self.requests[-1]


class OpenAIHarness(_HttpHarness):
    name = "openai"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider = OpenAIProvider(
            "test-key",
            moderation_model="test-moderation",
            timeout=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(self._handle2)),
        )

    def _finish(self, items: list[dict[str, Any]]) -> list[tuple[str | None, Any]]:
        """The closing events of a Responses API stream that produced `items`."""
        events: list[tuple[str | None, Any]] = [
            (
                "response.output_item.done",
                {"type": "response.output_item.done", "output_index": index, "item": item},
            )
            for index, item in enumerate(items)
        ]
        events.append(
            (
                "response.completed",
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_1",
                        "object": "response",
                        "model": MODEL,
                        "status": "completed",
                        "output": items,
                        "usage": {
                            "input_tokens": INPUT_TOKENS,
                            "output_tokens": OUTPUT_TOKENS,
                            "total_tokens": INPUT_TOKENS + OUTPUT_TOKENS,
                        },
                    },
                },
            )
        )
        return events

    def queue_text(self, chunks: list[str]) -> None:
        events: list[tuple[str | None, Any]] = [
            (
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "item_id": "msg_1",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": chunk,
                },
            )
            for chunk in chunks
        ]
        message = {
            "type": "message",
            "id": "msg_1",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "".join(chunks), "annotations": []}],
        }
        self._stream(events + self._finish([message]))

    def queue_tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        call = {
            "type": "function_call",
            "id": "fc_1",
            "call_id": "call_1",
            "name": name,
            "arguments": json.dumps(arguments),
            "status": "completed",
        }
        self._stream(self._finish([call]))

    def queue_error(self, status: int) -> None:
        self._json(status, {"error": {"message": "nope", "type": "error", "code": None}})

    def sent_system(self) -> str:
        return str(self.last["instructions"])

    def sent_tool_names(self) -> list[str]:
        return [tool["name"] for tool in self.last.get("tools", [])]

    def sent_image_count(self) -> int:
        return sum(
            part["type"] == "input_image"
            for item in self.last["input"]
            if isinstance(item.get("content"), list)
            for part in item["content"]
        )

    def sent_tool_result(self) -> str:
        return next(
            str(item["output"])
            for item in self.last["input"]
            if item.get("type") == "function_call_output"
        )

    def sent_roles(self) -> list[str]:
        kinds = {"function_call": "assistant", "function_call_output": "tool"}
        return [item.get("role") or kinds[item["type"]] for item in self.last["input"]]


class AnthropicHarness(_HttpHarness):
    name = "anthropic"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider = AnthropicProvider(
            "test-key",
            fast_model="test-fast",
            timeout=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(self._handle2)),
        )

    def _envelope(
        self, blocks: list[tuple[str | None, Any]], stop_reason: str
    ) -> list[tuple[str | None, Any]]:
        start = {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": MODEL,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": INPUT_TOKENS, "output_tokens": 1},
            },
        }
        end = {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": OUTPUT_TOKENS},
        }
        return [
            ("message_start", start),
            *blocks,
            ("message_delta", end),
            ("message_stop", {"type": "message_stop"}),
        ]

    def queue_text(self, chunks: list[str]) -> None:
        blocks: list[tuple[str | None, Any]] = [
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        ]
        blocks += [
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": chunk},
                },
            )
            for chunk in chunks
        ]
        blocks.append(("content_block_stop", {"type": "content_block_stop", "index": 0}))
        self._stream(self._envelope(blocks, "end_turn"))

    def queue_tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        raw = json.dumps(arguments)
        half = len(raw) // 2
        blocks: list[tuple[str | None, Any]] = [
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": name,
                        "input": {},
                    },
                },
            ),
            *[
                (
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "input_json_delta", "partial_json": piece},
                    },
                )
                for piece in (raw[:half], raw[half:])
            ],
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ]
        self._stream(self._envelope(blocks, "tool_use"))

    def queue_error(self, status: int) -> None:
        self._json(status, {"type": "error", "error": {"type": "api_error", "message": "nope"}})

    def sent_system(self) -> str:
        return str(self.last["system"])

    def sent_tool_names(self) -> list[str]:
        return [tool["name"] for tool in self.last.get("tools", [])]

    def _blocks(self, kind: str) -> list[dict[str, Any]]:
        return [
            block
            for m in self.last["messages"]
            if isinstance(m["content"], list)
            for block in m["content"]
            if block["type"] == kind
        ]

    def sent_image_count(self) -> int:
        return len(self._blocks("image"))

    def sent_tool_result(self) -> str:
        return str(self._blocks("tool_result")[0]["content"])

    def sent_roles(self) -> list[str]:
        return [m["role"] for m in self.last["messages"]]


class GeminiHarness(_HttpHarness):
    name = "gemini"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider = GeminiProvider(
            "test-key",
            fast_model="test-fast",
            timeout=5,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self._handle)),
        )

    @staticmethod
    def _usage() -> dict[str, Any]:
        return {
            "promptTokenCount": INPUT_TOKENS,
            "candidatesTokenCount": OUTPUT_TOKENS,
            "totalTokenCount": INPUT_TOKENS + OUTPUT_TOKENS,
        }

    def queue_text(self, chunks: list[str]) -> None:
        events: list[tuple[str | None, Any]] = [
            (None, {"candidates": [{"content": {"role": "model", "parts": [{"text": chunk}]}}]})
            for chunk in chunks
        ]
        events.append(
            (
                None,
                {
                    "candidates": [
                        {"content": {"role": "model", "parts": []}, "finishReason": "STOP"}
                    ],
                    "usageMetadata": self._usage(),
                },
            )
        )
        self._stream(events)

    def queue_tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        self._stream(
            [
                (
                    None,
                    {
                        "candidates": [
                            {
                                "content": {
                                    "role": "model",
                                    "parts": [{"functionCall": {"name": name, "args": arguments}}],
                                },
                                "finishReason": "STOP",
                            }
                        ],
                        "usageMetadata": self._usage(),
                    },
                )
            ]
        )

    def queue_error(self, status: int) -> None:
        self._json(status, {"error": {"code": status, "message": "nope", "status": "ERROR"}})

    def sent_system(self) -> str:
        return str(self.last["systemInstruction"]["parts"][0]["text"])

    def sent_tool_names(self) -> list[str]:
        return [
            declaration["name"]
            for tool in self.last.get("tools", [])
            for declaration in tool["functionDeclarations"]
        ]

    def _parts(self, key: str) -> list[dict[str, Any]]:
        return [
            part for content in self.last["contents"] for part in content["parts"] if key in part
        ]

    def sent_image_count(self) -> int:
        return len(self._parts("inlineData"))

    def sent_tool_result(self) -> str:
        return str(self._parts("functionResponse")[0]["functionResponse"]["response"]["result"])

    def sent_roles(self) -> list[str]:
        return ["assistant" if c["role"] == "model" else "user" for c in self.last["contents"]]


class FakeHarness:
    """The fake provider must honour the same contract the real adapters do."""

    name = "fake"

    def __init__(self) -> None:
        self._fake = FakeProvider()
        self.provider: AIProvider = self._fake
        self.requests: list[dict[str, Any]] = self._fake.calls  # type: ignore[assignment]

    def queue_text(self, chunks: list[str]) -> None:
        self._fake.script.append(ChatMessage(role="assistant", text="".join(chunks)))

    def queue_tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        self._fake.script.append(
            ChatMessage(
                role="assistant", tool_calls=[ToolCall(id="fake_1", name=name, arguments=arguments)]
            )
        )

    def queue_error(self, status: int) -> None:
        from app.ai.providers.base import error_from_status

        error: ProviderError = error_from_status(status, "nope")
        self._fake.script.append(error)

    @property
    def _messages(self) -> list[ChatMessage]:
        return self._fake.calls[-1]["messages"]  # type: ignore[return-value]

    def sent_system(self) -> str:
        return str(self._fake.calls[-1]["system"])

    def sent_tool_names(self) -> list[str]:
        return [tool.name for tool in self._fake.calls[-1]["tools"]]  # type: ignore[attr-defined]

    def sent_image_count(self) -> int:
        return sum(len(m.images) for m in self._messages)

    def sent_tool_result(self) -> str:
        return next(m.tool_results[0].content for m in self._messages if m.role == "tool")

    def sent_roles(self) -> list[str]:
        # OpenAI's wire format is the odd one out with a `tool` role; the
        # others send tool results as a user turn.
        return ["user" if m.role == "tool" else m.role for m in self._messages]


HARNESSES: dict[str, type[Any]] = {
    "fake": FakeHarness,
    "openai": OpenAIHarness,
    "anthropic": AnthropicHarness,
    "gemini": GeminiHarness,
}
