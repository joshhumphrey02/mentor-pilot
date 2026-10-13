"""Behaviour specific to the OpenAI adapter."""

import pytest

from app.ai.providers.base import ProviderError
from app.ai.types import ChatMessage, Done, ToolResult
from tests.ai.harness import OpenAIHarness
from tests.ai.test_provider_contract import WEATHER, hello, run


def refuse(harness: OpenAIHarness, message: str) -> None:
    harness._json(400, {"error": {"message": message, "type": "invalid_request_error"}})


async def test_conversations_are_not_stored_and_reasoning_travels_with_the_request() -> None:
    harness = OpenAIHarness()
    harness.queue_text(["Hello"])

    await run(harness, hello())

    assert harness.last["store"] is False
    assert harness.last["include"] == ["reasoning.encrypted_content"]


async def test_the_models_own_items_are_replayed_with_the_tool_result() -> None:
    harness = OpenAIHarness()
    harness.queue_tool_call("get_weather", {"city": "Cape Town"})
    first = (await run(harness, hello(), tools=[WEATHER]))[-1]
    assert isinstance(first, Done)

    harness.queue_text(["Sunny."])
    result = ToolResult(tool_call_id="call_1", name="get_weather", content="Sunny, 24C")
    await run(
        harness,
        [*hello(), first.message, ChatMessage(role="tool", tool_results=[result])],
        tools=[WEATHER],
    )

    replayed = harness.last["input"][1]
    assert (replayed["type"], replayed["id"], replayed["call_id"]) == (
        "function_call",
        "fc_1",
        "call_1",
    ), "sent back exactly as the model produced it, not rebuilt"


async def test_temperature_is_dropped_for_a_model_that_only_takes_its_default() -> None:
    harness = OpenAIHarness()
    refuse(harness, "Unsupported parameter: 'temperature' is not supported with this model.")
    harness.queue_text(["Hello"])

    await run(harness, hello())

    assert harness.requests[0]["temperature"] == 0.7
    assert "temperature" not in harness.requests[1]

    # Remembered: the next request does not pay for another rejection.
    harness.queue_text(["Hello"])
    await run(harness, hello())
    assert len(harness.requests) == 3
    assert "temperature" not in harness.requests[2]


async def test_a_rejection_is_reported_with_openais_reason() -> None:
    harness = OpenAIHarness()
    refuse(harness, "The model `nope` does not exist.")

    with pytest.raises(ProviderError) as caught:
        await run(harness, hello())

    assert caught.value.code == "bad_request"
    assert "does not exist" in str(caught.value)
    assert len(harness.requests) == 1
