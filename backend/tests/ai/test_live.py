"""Calls the real provider named by AI_PROVIDER, which costs a little money.

Skipped unless RUN_LIVE_AI_TESTS=1, so the normal test run never spends
anything even when `.env` holds a real key. It also needs that provider's key
and AI_MODEL, from `.env` or the environment:

    RUN_LIVE_AI_TESTS=1 uv run pytest tests/ai/test_live.py

To confirm another vendor, name it for that run:

    RUN_LIVE_AI_TESTS=1 AI_PROVIDER=anthropic AI_MODEL=... ANTHROPIC_API_KEY=... \
        uv run pytest tests/ai/test_live.py
"""

import os

import pytest

from app.ai.providers.base import ProviderError
from app.ai.registry import ProviderRegistry
from app.ai.service import AIService
from app.ai.types import ChatMessage, ToolResult, ToolSpec
from app.core.config import Settings

ADD = ToolSpec(
    name="add_numbers",
    description="Add two numbers and return the sum.",
    parameters={
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    },
)


@pytest.fixture
def live() -> AIService:
    if os.environ.get("RUN_LIVE_AI_TESTS") != "1":
        pytest.skip("live AI tests are opt-in: set RUN_LIVE_AI_TESTS=1")
    settings = Settings()
    if settings.ai_provider == "fake" or not settings.ai_model:
        pytest.skip("no live AI provider configured")
    registry = ProviderRegistry(settings)
    try:
        registry.get()
    except ProviderError:
        pytest.skip(f"{settings.ai_provider} API key is not set")
    return AIService(settings, registry)


async def test_live_chat(live: AIService) -> None:
    result = await live.complete(
        messages=[ChatMessage(role="user", text="Reply with exactly the word: pong")],
        max_tokens=1024,
    )

    assert result.error is None, result.error
    assert "pong" in result.text.lower()
    assert result.usage.input_tokens > 0 and result.usage.output_tokens > 0


async def test_live_tool_round_trip(live: AIService) -> None:
    messages = [ChatMessage(role="user", text="Use the add_numbers tool to add 19 and 23.")]
    first = await live.complete(messages=messages, tools=[ADD], max_tokens=2048)

    assert first.error is None, first.error
    assert first.tool_calls and first.tool_calls[0].name == "add_numbers"
    assert first.message is not None
    call = first.tool_calls[0]
    assert {float(call.arguments["a"]), float(call.arguments["b"])} == {19.0, 23.0}

    messages += [
        first.message,
        ChatMessage(
            role="tool",
            tool_results=[ToolResult(tool_call_id=call.id, name=call.name, content="42")],
        ),
    ]
    second = await live.complete(messages=messages, tools=[ADD], max_tokens=2048)

    assert second.error is None, second.error
    assert "42" in second.text


async def test_live_moderation(live: AIService) -> None:
    result = await live.moderate("How do I connect an LED to a 9V battery safely?")

    assert result.checked is True
    assert result.flagged is False
