"""One contract, four implementations.

Every test here runs against the fake provider and against each real adapter
(talking to a fake HTTP server in that vendor's wire format). If these pass,
the rest of the app can swap AI_PROVIDER without noticing.
"""

import pytest

from app.ai.providers.base import ProviderError
from app.ai.types import (
    ChatMessage,
    Done,
    ImageInput,
    ProviderEvent,
    TextDelta,
    ToolCallEvent,
    ToolResult,
    ToolSpec,
    UsageEvent,
)
from tests.ai.harness import HARNESSES, INPUT_TOKENS, MODEL, OUTPUT_TOKENS, Harness

WEATHER = ToolSpec(
    name="get_weather",
    description="Look up the weather in a city.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)
# A 1x1 transparent PNG.
PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
    "DwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@pytest.fixture(params=sorted(HARNESSES))
def harness(request: pytest.FixtureRequest) -> Harness:
    built: Harness = HARNESSES[request.param]()
    return built


async def run(
    harness: Harness,
    messages: list[ChatMessage],
    *,
    tools: list[ToolSpec] | None = None,
    system: str = "You are a mentor.",
) -> list[ProviderEvent]:
    return [
        event
        async for event in harness.provider.stream_chat(
            messages, tools or [], system, MODEL, 0.7, 512
        )
    ]


def hello() -> list[ChatMessage]:
    return [ChatMessage(role="user", text="Hi")]


async def test_text_streams_in_order_and_ends_with_done(harness: Harness) -> None:
    harness.queue_text(["Hello ", "there, ", "learner."])

    events = await run(harness, hello())

    deltas = [event.text for event in events if isinstance(event, TextDelta)]
    assert "".join(deltas) == "Hello there, learner."
    assert len(deltas) > 1, "text must arrive incrementally, not as one block"
    done = events[-1]
    assert isinstance(done, Done)
    assert done.stop_reason == "end"
    assert done.message.role == "assistant"
    assert done.message.text == "Hello there, learner."
    assert [type(e) for e in events].count(Done) == 1


async def test_usage_is_reported_in_one_shape(harness: Harness) -> None:
    harness.queue_text(["Hello ", "there"])

    events = await run(harness, hello())

    usage = next(event.usage for event in events if isinstance(event, UsageEvent))
    if harness.name == "fake":  # the fake counts words rather than replaying canned numbers
        assert usage.input_tokens > 0 and usage.output_tokens > 0
    else:
        assert (usage.input_tokens, usage.output_tokens) == (INPUT_TOKENS, OUTPUT_TOKENS)
    assert usage.cost_usd is None, "pricing is applied by AIService, not by adapters"


async def test_tool_call_is_normalised(harness: Harness) -> None:
    harness.queue_tool_call("get_weather", {"city": "Cape Town", "days": 3})

    events = await run(harness, hello(), tools=[WEATHER])

    calls = [event.call for event in events if isinstance(event, ToolCallEvent)]
    assert len(calls) == 1
    assert calls[0].name == "get_weather"
    assert calls[0].arguments == {"city": "Cape Town", "days": 3}
    assert calls[0].id
    done = events[-1]
    assert isinstance(done, Done)
    assert done.stop_reason == "tool_calls"
    assert done.message.tool_calls == calls
    assert harness.sent_tool_names() == ["get_weather"]


async def test_tool_result_round_trip(harness: Harness) -> None:
    """The assistant turn from one call must be accepted back in the next."""
    harness.queue_tool_call("get_weather", {"city": "Cape Town"})
    first = await run(harness, hello(), tools=[WEATHER])
    assistant = first[-1]
    assert isinstance(assistant, Done)
    call = assistant.message.tool_calls[0]

    harness.queue_text(["It is ", "sunny."])
    history = [
        *hello(),
        assistant.message,
        ChatMessage(
            role="tool",
            tool_results=[ToolResult(tool_call_id=call.id, name=call.name, content="Sunny, 24C")],
        ),
    ]
    second = await run(harness, history, tools=[WEATHER])

    assert harness.sent_tool_result() == "Sunny, 24C"
    assert harness.sent_roles()[-3:] == ["user", "assistant", "user"] or harness.sent_roles()[
        -3:
    ] == ["user", "assistant", "tool"]
    final = second[-1]
    assert isinstance(final, Done)
    assert final.message.text == "It is sunny."


async def test_history_from_another_provider_is_accepted(harness: Harness) -> None:
    """Switching AI_PROVIDER mid-conversation must not break existing chats."""
    harness.queue_text(["Welcome ", "back."])
    foreign = ChatMessage(
        role="assistant",
        text="Earlier answer.",
        provider_state={"provider": "some-other-vendor", "model": "x", "payload": {"junk": 1}},  # type: ignore[arg-type]
    )

    events = await run(harness, [*hello(), foreign, ChatMessage(role="user", text="And now?")])

    assert isinstance(events[-1], Done)
    assert harness.sent_roles() == ["user", "assistant", "user"] or harness.sent_roles() == [
        "system",
        "user",
        "assistant",
        "user",
    ]


async def test_system_prompt_is_sent(harness: Harness) -> None:
    harness.queue_text(["ok ", "then"])

    await run(harness, hello(), system="You are a patient STEM mentor.")

    assert harness.sent_system() == "You are a patient STEM mentor."


async def test_images_are_sent(harness: Harness) -> None:
    assert harness.provider.supports("vision")
    harness.queue_text(["A ", "pixel."])
    message = ChatMessage(
        role="user",
        text="What is this?",
        images=[ImageInput(media_type="image/png", data_base64=PIXEL)],
    )

    await run(harness, [message])

    assert harness.sent_image_count() == 1


@pytest.mark.parametrize(
    ("status", "retryable", "code"),
    [
        (429, True, "rate_limited"),
        (500, True, "unavailable"),
        (503, True, "unavailable"),
        (401, False, "auth"),
        (400, False, "bad_request"),
    ],
)
async def test_http_failures_become_provider_errors(
    harness: Harness, status: int, retryable: bool, code: str
) -> None:
    harness.queue_error(status)

    with pytest.raises(ProviderError) as caught:
        await run(harness, hello())

    assert caught.value.retryable is retryable
    assert caught.value.code == code


def test_every_provider_declares_its_features(harness: Harness) -> None:
    assert harness.provider.supports("tools")
    assert harness.provider.supports("image_gen") is False
