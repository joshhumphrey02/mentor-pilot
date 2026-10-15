"""Behaviour specific to the Gemini adapter."""

import json

import pytest

from app.ai import safety
from app.ai.providers.base import ProviderError
from tests.ai.harness import GeminiHarness
from tests.ai.test_provider_contract import hello, run


def too_many_requests(harness: GeminiHarness, retry_delay: str) -> None:
    harness._json(
        429,
        {
            "error": {
                "code": 429,
                "message": "You exceeded your current quota.",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": retry_delay,
                    }
                ],
            }
        },
    )


def verdict(harness: GeminiHarness, body: dict[str, object]) -> None:
    harness._json(
        200,
        {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": json.dumps(body)}]},
                    "finishReason": "STOP",
                }
            ]
        },
    )


async def test_a_used_up_quota_is_not_retried() -> None:
    harness = GeminiHarness()
    too_many_requests(harness, "11725s")

    with pytest.raises(ProviderError) as caught:
        await run(harness, hello())

    assert (caught.value.code, caught.value.retryable) == ("quota_exhausted", False)


async def test_a_short_rate_limit_is_still_retried() -> None:
    harness = GeminiHarness()
    too_many_requests(harness, "2s")

    with pytest.raises(ProviderError) as caught:
        await run(harness, hello())

    assert (caught.value.code, caught.value.retryable) == ("rate_limited", True)


async def test_replies_are_screened_by_geminis_own_filters() -> None:
    harness = GeminiHarness()
    harness.queue_text(["Hello"])

    await run(harness, hello())

    thresholds = {s["category"]: s["threshold"] for s in harness.last["safetySettings"]}
    assert thresholds["HARM_CATEGORY_SEXUALLY_EXPLICIT"] == "BLOCK_LOW_AND_ABOVE"
    assert len(thresholds) == 4
    assert harness.provider.supports("safety_filter")


async def test_the_input_check_can_name_the_conversation() -> None:
    harness = GeminiHarness()
    verdict(harness, {"flagged": False, "categories": [], "title": "LED circuit basics"})

    result = await harness.provider.moderate("How do I connect an LED?", with_title=True)

    assert (result.flagged, result.title) == (False, "LED circuit basics")
    assert harness.last["systemInstruction"]["parts"][0]["text"] == (
        safety.CLASSIFIER_SYSTEM_WITH_TITLE
    )


async def test_a_plain_check_asks_for_no_title() -> None:
    harness = GeminiHarness()
    verdict(harness, {"flagged": False, "categories": []})

    result = await harness.provider.moderate("How do I connect an LED?")

    assert result.title is None
    assert harness.last["systemInstruction"]["parts"][0]["text"] == safety.CLASSIFIER_SYSTEM
