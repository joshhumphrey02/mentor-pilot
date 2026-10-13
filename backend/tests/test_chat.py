import asyncio
import json
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import ProviderError
from app.ai.providers.fake import FLAG_WORD, FakeProvider
from app.ai.types import ChatMessage, ModerationResult
from app.core.config import Settings
from app.core.time import utcnow
from app.models import AIUsage, Conversation, Message, ModerationFlag, Project, User
from app.services.chat import TURN_TIMEOUT, ChatService
from tests.conftest import PASSWORD, csrf, login_as, make_client, make_user

LEARNER = "learner@example.com"

REPLY = """An LED lets current flow one way only.

:::callout safety
Always use a resistor with an LED.
:::

:::replies
Show me a diagram
Why a resistor?
:::
"""


def say(text: str) -> ChatMessage:
    return ChatMessage(role="assistant", text=text)


def events(response: Response) -> list[tuple[str, dict[str, Any]]]:
    """Parses a Server-Sent Events body into (event name, data) pairs."""
    parsed: list[tuple[str, dict[str, Any]]] = []
    for chunk in response.text.replace("\r\n", "\n").split("\n\n"):
        name, data = "", ""
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if name and data:
            parsed.append((name, json.loads(data)))
    return parsed


def final_message(response: Response) -> dict[str, Any]:
    message: dict[str, Any] = next(data for name, data in events(response) if name == "done")[
        "message"
    ]
    return message


@pytest.fixture
async def learner(client: AsyncClient, db: AsyncSession) -> User:
    user = await make_user(db, email=LEARNER)
    await login_as(client, LEARNER)
    return user


@pytest.fixture
async def conversation_id(client: AsyncClient, learner: User) -> str:
    response = await client.post(
        "/api/v1/projects", json={"title": "Solar phone charger"}, headers=csrf(client)
    )
    assert response.status_code == 201, response.text
    conversation: str = response.json()["latest_conversation"]["id"]
    return conversation


async def send(client: AsyncClient, conversation_id: str, text: str) -> Response:
    return await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": text},
        headers=csrf(client),
    )


async def history(client: AsyncClient, conversation_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
    messages: list[dict[str, Any]] = response.json()["messages"]
    return messages


# --- Projects ----------------------------------------------------------------


async def test_new_project_comes_with_a_conversation(client: AsyncClient, learner: User) -> None:
    response = await client.post("/api/v1/projects", json={}, headers=csrf(client))

    assert response.status_code == 201
    project = response.json()
    assert project["title"] == "New project"
    assert project["current_stage"] == "problem_discovery"
    assert project["latest_conversation"]["project_id"] == project["id"]

    listed = (await client.get("/api/v1/projects")).json()
    assert [p["id"] for p in listed] == [project["id"]]


async def test_projects_are_private_to_their_owner(
    client: AsyncClient, conversation_id: str, db: AsyncSession, app: FastAPI
) -> None:
    project_id = (await client.get("/api/v1/projects")).json()[0]["id"]
    await make_user(db, email="other@example.com")
    stranger = make_client(app)
    await login_as(stranger, "other@example.com")

    assert (await stranger.get("/api/v1/projects")).json() == []
    assert (await stranger.get(f"/api/v1/projects/{project_id}")).status_code == 404
    assert (
        await stranger.get(f"/api/v1/conversations/{conversation_id}/messages")
    ).status_code == 404
    assert (await send(stranger, conversation_id, "hello")).status_code == 404


async def test_deleted_project_disappears(client: AsyncClient, conversation_id: str) -> None:
    project_id = (await client.get("/api/v1/projects")).json()[0]["id"]

    deleted = await client.delete(f"/api/v1/projects/{project_id}", headers=csrf(client))

    assert deleted.status_code == 204
    assert (await client.get("/api/v1/projects")).json() == []
    assert (await send(client, conversation_id, "hello")).status_code == 404


async def test_chat_requires_login(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000001/messages", json={"text": "hi"}
    )
    assert response.status_code == 401


# --- A streamed turn ---------------------------------------------------------


async def test_reply_streams_as_ordered_events(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say(REPLY)]

    response = await send(client, conversation_id, "How do I connect an LED?")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    stream = events(response)
    names = [name for name, _ in stream]
    assert names[0] == "message_start"
    assert names.index("block_start") < names.index("text_delta") < names.index("block_complete")
    assert names[-2:] == ["done", "conversation"] or names[-1] == "done"
    assert names.count("done") == 1

    start = stream[0][1]
    assert start["user_message"]["blocks"] == [
        {"type": "markdown", "text": "How do I connect an LED?"}
    ]
    streamed = "".join(data["text"] for name, data in stream if name == "text_delta")
    assert streamed.strip() == "An LED lets current flow one way only."
    assert ":::" not in streamed


async def test_reply_is_stored_as_typed_blocks(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say(REPLY)]

    message = final_message(await send(client, conversation_id, "How do I connect an LED?"))

    assert message["status"] == "complete"
    assert message["blocks"] == [
        {"type": "markdown", "text": "An LED lets current flow one way only."},
        {"type": "callout", "variant": "safety", "text": "Always use a resistor with an LED."},
        {"type": "suggested_replies", "replies": ["Show me a diagram", "Why a resistor?"]},
    ]


async def test_conversation_survives_a_refresh(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say(REPLY)]
    sent = final_message(await send(client, conversation_id, "How do I connect an LED?"))

    stored = await history(client, conversation_id)

    assert [m["role"] for m in stored] == ["user", "assistant"]
    assert stored[1] == sent
    assert stored[0]["blocks"][0]["text"] == "How do I connect an LED?"


async def test_model_sees_earlier_turns_and_the_learner_context(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say(REPLY), say("Title"), say("Because it limits the current.")]
    await send(client, conversation_id, "How do I connect an LED?")
    await send(client, conversation_id, "Why a resistor?")

    last = fake_ai.calls[-1]
    sent = last["messages"]
    assert isinstance(sent, list)
    assert [m.role for m in sent] == ["user", "assistant", "user"]
    assert sent[1].text == REPLY, "the model sees its own reply verbatim, directives included"
    assert sent[2].text == "Why a resistor?"
    system = str(last["system"])
    assert "Solar phone charger" in system
    assert "First name: Test" in system
    assert ":::callout" in system and "230 V" in system


async def test_every_turn_is_metered_against_the_project(
    client: AsyncClient,
    conversation_id: str,
    fake_ai: FakeProvider,
    db: AsyncSession,
    learner: User,
) -> None:
    await send(client, conversation_id, "Hello")

    rows = (await db.scalars(select(AIUsage).order_by(AIUsage.created_at))).all()
    project = (await db.scalars(select(Project))).one()
    assert [row.task for row in rows] == ["chat", "title"]
    assert all(row.user_id == learner.id and row.project_id == project.id for row in rows)


# --- Titles ------------------------------------------------------------------


async def test_first_exchange_names_the_conversation(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say(REPLY), say('"LED circuit basics."')]

    stream = events(await send(client, conversation_id, "How do I connect an LED?"))

    assert stream[-1][0] == "conversation"
    assert stream[-1][1]["conversation"]["title"] == "LED circuit basics"
    assert fake_ai.calls[-1]["model"] == "fake-fast-model", "titles use the cheap model"


async def test_title_falls_back_to_the_learners_words(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say(REPLY), ProviderError("down", code="auth")]

    stream = events(await send(client, conversation_id, "How do I connect an LED?"))

    assert stream[-1][1]["conversation"]["title"] == "How do I connect an LED?"


async def test_only_the_first_exchange_is_titled(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    await send(client, conversation_id, "First")
    calls_before = len(fake_ai.calls)

    stream = events(await send(client, conversation_id, "Second"))

    assert "conversation" not in [name for name, _ in stream]
    assert len(fake_ai.calls) == calls_before + 1


# --- Safety ------------------------------------------------------------------


async def test_unsafe_input_never_reaches_the_model(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider, db: AsyncSession
) -> None:
    message = final_message(await send(client, conversation_id, f"something {FLAG_WORD}"))

    assert fake_ai.calls == [], "the model must not be called"
    assert message["status"] == "complete"
    assert "here for your project" in message["blocks"][0]["text"]
    flag = (await db.scalars(select(ModerationFlag))).one()
    assert (flag.direction, flag.status, flag.checked) == ("input", "open", True)
    assert FLAG_WORD in flag.content
    stored = await history(client, conversation_id)
    assert stored[0]["status"] == "blocked"


async def test_blocked_messages_are_left_out_of_later_history(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    await send(client, conversation_id, f"something {FLAG_WORD}")
    await send(client, conversation_id, "Okay, back to my project")

    sent = fake_ai.calls[0]["messages"]
    assert isinstance(sent, list)
    assert [m.text for m in sent] == ["Okay, back to my project"]


async def test_unsafe_output_is_replaced_before_it_is_saved(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider, db: AsyncSession
) -> None:
    fake_ai.script = [say(f"Here is something bad {FLAG_WORD}")]

    message = final_message(await send(client, conversation_id, "Tell me something"))

    assert FLAG_WORD not in json.dumps(message)
    assert "here for your project" in message["blocks"][0]["text"]
    flag = (await db.scalars(select(ModerationFlag))).one()
    assert flag.direction == "output"
    stored = (await db.scalars(select(Message).where(Message.role == "assistant"))).one()
    assert FLAG_WORD not in stored.raw


async def test_moderation_outage_blocks_the_message_and_says_so(
    client: AsyncClient, conversation_id: str, app: FastAPI, db: AsyncSession
) -> None:
    class ModerationDown(FakeProvider):
        async def moderate(self, text: str) -> ModerationResult:
            raise ProviderError("down", code="auth")

    provider = ModerationDown()
    app.state.ai.registry.register(provider)

    message = final_message(await send(client, conversation_id, "How do I connect an LED?"))

    assert provider.calls == []
    assert message["status"] == "error"
    assert message["blocks"][0]["type"] == "error"
    assert message["blocks"][0]["retryable"] is True
    assert (await db.scalars(select(ModerationFlag))).one().checked is False


async def test_model_refusal_becomes_a_kind_redirect(
    client: AsyncClient, conversation_id: str, app: FastAPI
) -> None:
    from app.ai.types import Done, UsageEvent
    from app.ai.types import Usage as AIUsageShape

    class Refuses(FakeProvider):
        async def stream_chat(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def,override]
            yield UsageEvent(usage=AIUsageShape(input_tokens=5, output_tokens=0))
            yield Done(stop_reason="refusal", message=ChatMessage(role="assistant"))

    app.state.ai.registry.register(Refuses())

    message = final_message(await send(client, conversation_id, "Something the model declines"))

    assert message["status"] == "complete"
    assert "here for your project" in message["blocks"][0]["text"]


# --- Failures ----------------------------------------------------------------


async def test_provider_failure_becomes_an_error_block(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [ProviderError("bad key", code="auth")]

    message = final_message(await send(client, conversation_id, "Hello"))

    assert message["status"] == "error"
    assert message["blocks"] == [
        {
            "type": "error",
            "code": "auth",
            "text": "Your mentor isn't set up correctly. Please let your teacher or an admin know.",
            "retryable": False,
        }
    ]


async def test_failed_replies_are_not_replayed_to_the_model(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [ProviderError("bad key", code="auth")]
    await send(client, conversation_id, "First try")
    await send(client, conversation_id, "Second try")

    sent = fake_ai.calls[-1]["messages"]
    assert isinstance(sent, list)
    assert [m.role for m in sent] == ["user", "user"]


async def test_an_unexpected_crash_still_ends_the_turn_cleanly(
    client: AsyncClient, conversation_id: str, app: FastAPI, db: AsyncSession
) -> None:
    class Explodes(FakeProvider):
        async def stream_chat(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def,override]
            raise RuntimeError("bug in an adapter")
            yield  # pragma: no cover

    app.state.ai.registry.register(Explodes())

    message = final_message(await send(client, conversation_id, "Hello"))

    assert message["status"] == "error"
    assert message["blocks"][0]["code"] == "internal"
    statuses = (await db.scalars(select(Message.status))).all()
    assert "streaming" not in statuses, "no message may be left spinning forever"


async def test_empty_reply_is_reported(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say("")]

    message = final_message(await send(client, conversation_id, "Hello"))

    assert message["status"] == "error"
    assert message["blocks"][0]["code"] == "empty_reply"


# --- One turn at a time, and dropped connections -------------------------------


async def test_second_message_is_refused_while_a_reply_is_in_progress(
    client: AsyncClient, conversation_id: str, db: AsyncSession
) -> None:
    db.add(Message(conversation_id=conversation_id, role="assistant", status="streaming"))
    await db.commit()

    response = await send(client, conversation_id, "Are you there?")

    assert response.status_code == 409
    assert response.json()["code"] == "turn_in_progress"


async def test_a_turn_that_died_does_not_lock_the_conversation(
    client: AsyncClient, conversation_id: str, db: AsyncSession
) -> None:
    db.add(Message(conversation_id=conversation_id, role="assistant", status="streaming"))
    await db.commit()
    await db.execute(
        update(Message).values(created_at=utcnow() - TURN_TIMEOUT - timedelta(seconds=1))
    )
    await db.commit()

    response = await send(client, conversation_id, "Are you there?")

    assert response.status_code == 200
    assert final_message(response)["status"] == "complete"


async def test_reply_is_saved_even_if_the_learner_disconnects(
    client: AsyncClient,
    conversation_id: str,
    fake_ai: FakeProvider,
    app: FastAPI,
    db: AsyncSession,
    learner: User,
) -> None:
    fake_ai.script = [say(REPLY)]
    chat: ChatService = app.state.chat
    async with app.state.session_factory() as session:
        user = await session.get(User, learner.id)
        assert user is not None
        turn = await chat.begin_turn(session, user, conversation_id, "How do I connect an LED?")  # type: ignore[arg-type]

    stream = chat.stream(turn)
    first = await anext(stream)
    assert first.event == "message_start"
    await stream.aclose()  # the phone lost signal
    await asyncio.gather(*chat._tasks)

    recovered = await client.get(f"/api/v1/messages/{turn.assistant_message_id}")
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "complete"
    assert recovered.json()["blocks"][1]["type"] == "callout"


async def test_stale_streaming_message_is_shown_as_interrupted(
    client: AsyncClient, conversation_id: str, db: AsyncSession
) -> None:
    db.add(Message(conversation_id=conversation_id, role="assistant", status="streaming"))
    await db.commit()
    await db.execute(
        update(Message).values(created_at=utcnow() - TURN_TIMEOUT - timedelta(seconds=1))
    )
    await db.commit()

    stored = await history(client, conversation_id)

    assert stored[0]["status"] == "error"
    assert stored[0]["blocks"][0]["code"] == "interrupted"


# --- Regenerate, feedback, paging, search --------------------------------------


async def test_regenerate_replaces_the_last_reply(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [say("First answer."), say("Title"), say("Better answer.")]
    first = final_message(await send(client, conversation_id, "Explain voltage"))

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/regenerate", headers=csrf(client)
    )

    second = final_message(response)
    assert second["id"] != first["id"]
    assert events(response)[0][1]["user_message"] is None, "no new learner message to show"
    stored = await history(client, conversation_id)
    assert [m["role"] for m in stored] == ["user", "assistant"]
    assert stored[1]["blocks"][0]["text"] == "Better answer."
    sent = fake_ai.calls[-1]["messages"]
    assert isinstance(sent, list)
    assert [m.text for m in sent] == ["Explain voltage"]


async def test_nothing_to_regenerate_in_an_empty_conversation(
    client: AsyncClient, conversation_id: str
) -> None:
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/regenerate", headers=csrf(client)
    )

    assert response.status_code == 400
    assert response.json()["code"] == "nothing_to_regenerate"


async def test_feedback_can_be_set_and_cleared(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    message = final_message(await send(client, conversation_id, "Hello"))
    url = f"/api/v1/messages/{message['id']}/feedback"

    assert (await client.post(url, json={"value": 1}, headers=csrf(client))).json()["feedback"] == 1
    assert (await client.post(url, json={"value": -1}, headers=csrf(client))).json()[
        "feedback"
    ] == -1
    assert (await client.post(url, json={"value": 0}, headers=csrf(client))).json()[
        "feedback"
    ] is None
    assert (await client.post(url, json={"value": 5}, headers=csrf(client))).status_code == 422


async def test_feedback_is_only_for_the_mentors_replies(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    await send(client, conversation_id, "Hello")
    mine = (await history(client, conversation_id))[0]

    response = await client.post(
        f"/api/v1/messages/{mine['id']}/feedback", json={"value": 1}, headers=csrf(client)
    )
    assert response.status_code == 400


async def test_messages_page_backwards_from_the_newest(
    client: AsyncClient, conversation_id: str, db: AsyncSession
) -> None:
    for number in range(5):
        db.add(Message(conversation_id=conversation_id, role="user", raw=f"m{number}"))
        await db.flush()
    await db.commit()
    url = f"/api/v1/conversations/{conversation_id}/messages"

    newest = (await client.get(url, params={"limit": 2})).json()
    older = (await client.get(url, params={"limit": 2, "before": newest["next_before"]})).json()
    oldest = (await client.get(url, params={"limit": 2, "before": older["next_before"]})).json()

    assert newest["next_before"] is not None
    assert len(newest["messages"]) == len(older["messages"]) == 2
    assert len(oldest["messages"]) == 1
    assert oldest["next_before"] is None


async def test_conversations_can_be_searched_by_what_was_said(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    project_id = (await client.get("/api/v1/projects")).json()[0]["id"]
    await send(client, conversation_id, "Tell me about photosynthesis")
    await client.post(f"/api/v1/projects/{project_id}/conversations", json={}, headers=csrf(client))
    url = f"/api/v1/projects/{project_id}/conversations"

    everything = (await client.get(url)).json()
    found = (await client.get(url, params={"q": "PHOTOSYNTH"})).json()
    nothing = (await client.get(url, params={"q": "volcano"})).json()

    assert len(everything) == 2
    assert [c["id"] for c in found] == [conversation_id]
    assert nothing == []


async def test_message_length_is_limited(client: AsyncClient, conversation_id: str) -> None:
    assert (await send(client, conversation_id, "x" * 4001)).status_code == 422
    assert (await send(client, conversation_id, "   ")).status_code == 422


# --- Data rights -------------------------------------------------------------


async def test_export_includes_projects_and_deletion_removes_them(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider, db: AsyncSession
) -> None:
    await send(client, conversation_id, "Hello mentor")

    exported = (await client.get("/api/v1/users/me/export")).json()

    project = exported["projects"][0]
    assert project["title"] == "Solar phone charger"
    assert project["conversations"][0]["messages"][0]["blocks"][0]["text"] == "Hello mentor"

    await client.post(
        "/api/v1/users/me/delete",
        json={"confirm": "DELETE", "password": PASSWORD},
        headers=csrf(client),
    )
    for model in (Project, Conversation, Message):
        assert (await db.scalars(select(model))).all() == []


def test_settings_default_to_failing_closed(settings: Settings) -> None:
    assert settings.moderation_fail_closed is True
