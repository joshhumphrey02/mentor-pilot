"""A scripted provider with no network calls.

Used by the test suite, and selectable with AI_PROVIDER=fake so the whole app
can be run and demoed without any API key.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Sequence

from app.ai.providers.base import ProviderError
from app.ai.types import (
    ChatMessage,
    Done,
    Feature,
    ModerationResult,
    ProviderEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    Usage,
    UsageEvent,
)

# In dev, a message containing `[[tool:name {"json": "args"}]]` makes the fake
# model call that tool, which is handy for exercising tools by hand.
_TOOL_DIRECTIVE = re.compile(r"\[\[tool:(\w+)\s*(\{.*?\})?\]\]", re.DOTALL)

FLAG_WORD = "FLAG_THIS_MESSAGE"


class FakeProvider:
    name = "fake"

    def __init__(self, *, delay: float = 0.0) -> None:
        self.delay = delay
        # Tests push replies or errors here; each call to stream_chat pops one.
        self.script: list[ChatMessage | ProviderError] = []
        self.calls: list[dict[str, object]] = []

    def supports(self, feature: Feature) -> bool:
        return feature in ("vision", "tools")

    def _reply(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> ChatMessage:
        last = messages[-1] if messages else ChatMessage(role="user")
        if last.role == "tool":
            summary = "; ".join(f"{r.name} returned {r.content}" for r in last.tool_results)
            return ChatMessage(role="assistant", text=f"Thanks. {summary}")
        directive = _TOOL_DIRECTIVE.search(last.text)
        if directive and any(tool.name == directive.group(1) for tool in tools):
            return ChatMessage(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id=f"fake_{len(self.calls)}",
                        name=directive.group(1),
                        arguments=json.loads(directive.group(2) or "{}"),
                    )
                ],
            )
        seen = f" I can see {len(last.images)} image(s)." if last.images else ""
        return ChatMessage(
            role="assistant",
            text=f"(Demo mentor, no AI key set.) You said: {last.text}{seen}",
        )

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system: str,
        model: str,
        temperature: float | None,
        max_tokens: int,
    ) -> AsyncIterator[ProviderEvent]:
        self.calls.append(
            {
                "messages": list(messages),
                "tools": list(tools),
                "system": system,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        scripted = self.script.pop(0) if self.script else self._reply(messages, tools)
        if isinstance(scripted, ProviderError):
            raise scripted

        # Split on spaces but keep them, so the pieces join back to the original.
        for piece in re.findall(r"\S+\s*", scripted.text):
            if self.delay:
                await asyncio.sleep(self.delay)
            yield TextDelta(text=piece)
        for call in scripted.tool_calls:
            yield ToolCallEvent(call=call)
        yield UsageEvent(
            usage=Usage(
                input_tokens=sum(len(m.text.split()) for m in messages) + len(system.split()),
                output_tokens=len(scripted.text.split()),
            )
        )
        yield Done(
            stop_reason="tool_calls" if scripted.tool_calls else "end",
            message=scripted,
        )

    async def moderate(self, text: str) -> ModerationResult:
        flagged = FLAG_WORD in text
        return ModerationResult(flagged=flagged, categories=["harassment"] if flagged else [])

    async def check(self, model: str | None) -> str:
        return "The fake provider is always available."
