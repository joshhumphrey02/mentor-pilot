from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import ProviderError
from app.ai.providers.fake import FakeProvider
from app.ai.tools.registry import MAX_TOOL_ROUNDS
from app.ai.types import ChatMessage, ToolCall
from app.models import AIUsage, Message, Project, ProjectStage, User
from app.services import chat as chat_module
from app.services import pathway
from tests.conftest import csrf, login_as, make_client, make_user
from tests.test_chat import events, final_message, say, send

IDEA = {
    "title": "Solar phone charger",
    "problem": "Phones die during load-shedding.",
    "field": "Energy",
    "difficulty": 3,
    "cost_min_zar": 150,
    "cost_max_zar": 400,
    "materials": ["small solar panel"],
    "time_needed": "3 weeks",
    "why_judges_like_it": "A real local problem.",
    "safety_level": "low",
}


def call(
    name: str, arguments: dict[str, Any], *, text: str = "", call_id: str = "c1"
) -> ChatMessage:
    return ChatMessage(
        role="assistant",
        text=text,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
    )


@pytest.fixture
async def learner(client: AsyncClient, db: AsyncSession) -> User:
    user = await make_user(db, email="learner@example.com")
    await login_as(client, "learner@example.com")
    return user


@pytest.fixture
async def project(client: AsyncClient, learner: User) -> dict[str, Any]:
    response = await client.post("/api/v1/projects", json={}, headers=csrf(client))
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def conversation_id(project: dict[str, Any]) -> str:
    conversation: str = project["latest_conversation"]["id"]
    return conversation


async def stages(client: AsyncClient, project_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"/api/v1/projects/{project_id}/stages")
    assert response.status_code == 200, response.text
    body: list[dict[str, Any]] = response.json()
    return body


# --- Stage definitions -------------------------------------------------------


def test_the_shipped_pathway_is_well_formed() -> None:
    shipped = pathway.default_definitions()

    assert [stage.position for stage in shipped] == list(range(1, 10))
    assert len({stage.key for stage in shipped}) == 9
    assert [stage.key for stage in shipped if stage.handoff] == ["design_prototyping"]
    for stage in shipped:
        keys = [item["key"] for item in stage.deliverables]
        assert len(keys) == len(set(keys)) >= 3, stage.key
        assert stage.goal and stage.exit_criteria and stage.instructions, stage.key


async def test_definitions_are_seeded_once_and_then_left_alone(db: AsyncSession) -> None:
    first = await pathway.definitions(db)
    assert len(first) == 9
    first[0].title = "Edited by an admin"
    await db.commit()

    await pathway.ensure_definitions(db)

    again = await pathway.definitions(db)
    assert again[0].title == "Edited by an admin", "admin edits must survive a restart"
    again[0].title = "Problem Discovery"
    await db.commit()


# --- Progress through the API ------------------------------------------------


async def test_new_project_starts_at_the_first_stage(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    listed = await stages(client, project["id"])

    assert [stage["status"] for stage in listed] == ["active"] + ["locked"] * 8
    assert listed[0]["title"] == "Problem Discovery"
    assert all(item["done"] is False for item in listed[0]["checklist"])
    assert listed[5]["handoff"] is True


async def test_learner_can_tick_and_untick_a_deliverable(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    url = f"/api/v1/projects/{project['id']}/stages/problem_discovery/checklist/observations"

    ticked = (await client.put(url, json={"done": True}, headers=csrf(client))).json()
    assert ticked[0]["checklist"][0] == {
        "key": "observations",
        "label": "List at least three problems you have noticed around you",
        "done": True,
        "note": "",
    }
    unticked = (await client.put(url, json={"done": False}, headers=csrf(client))).json()
    assert unticked[0]["checklist"][0]["done"] is False


async def test_unknown_checklist_item_is_404(client: AsyncClient, project: dict[str, Any]) -> None:
    response = await client.put(
        f"/api/v1/projects/{project['id']}/stages/problem_discovery/checklist/nope",
        json={"done": True},
        headers=csrf(client),
    )
    assert response.status_code == 404


async def test_confirming_moves_the_project_on(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    url = f"/api/v1/projects/{project['id']}/stages/advance"

    moved = await client.post(url, json={"from_stage": "problem_discovery"}, headers=csrf(client))

    assert moved.status_code == 200
    assert moved.json()["current_stage"] == "idea_development"
    listed = await stages(client, project["id"])
    assert [stage["status"] for stage in listed[:3]] == ["completed", "active", "locked"]


async def test_a_stale_confirmation_cannot_skip_a_stage(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    url = f"/api/v1/projects/{project['id']}/stages/advance"
    await client.post(url, json={"from_stage": "problem_discovery"}, headers=csrf(client))

    again = await client.post(url, json={"from_stage": "problem_discovery"}, headers=csrf(client))

    assert again.status_code == 400
    assert again.json()["code"] == "stage_changed"
    assert (await client.get(f"/api/v1/projects/{project['id']}")).json()[
        "current_stage"
    ] == "idea_development"


async def test_finishing_the_last_stage_completes_the_project(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession
) -> None:
    stored = (await db.scalars(select(Project))).one()
    await pathway.move_to(db, stored, "expo_preparation")
    await db.commit()

    done = await client.post(
        f"/api/v1/projects/{project['id']}/stages/advance",
        json={"from_stage": "expo_preparation"},
        headers=csrf(client),
    )

    assert done.json()["status"] == "completed"


async def test_stages_are_private(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, app: FastAPI
) -> None:
    await make_user(db, email="other@example.com")
    stranger = make_client(app)
    await login_as(stranger, "other@example.com")

    assert (await stranger.get(f"/api/v1/projects/{project['id']}/stages")).status_code == 404


async def test_projects_from_before_the_pathway_get_their_stages(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession
) -> None:
    for row in (await db.scalars(select(ProjectStage))).all():
        await db.delete(row)
    await db.commit()

    listed = await stages(client, project["id"])

    assert len(listed) == 9 and listed[0]["status"] == "active"


# --- The mentor using tools in a conversation ----------------------------------


async def test_tool_blocks_sit_in_the_reply_where_they_were_called(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call(
            "propose_project_ideas",
            {"ideas": [IDEA, {**IDEA, "title": "B"}, {**IDEA, "title": "C"}]},
            text="Here are some ideas to look at.",
        ),
        say("Which of these interests you?\n\n:::replies\nTell me about the first\n:::"),
        say("Title"),
    ]

    response = await send(client, conversation_id, "My phone dies in load-shedding")

    message = final_message(response)
    assert [block["type"] for block in message["blocks"]] == [
        "markdown",
        "idea_cards",
        "markdown",
        "suggested_replies",
    ]
    assert message["blocks"][1]["ideas"][0]["title"] == "Solar phone charger"
    status = [data for name, data in events(response) if name == "tool_status"]
    assert status == [
        {"tool": "propose_project_ideas", "text": "Putting together some project ideas…"}
    ]


async def test_tool_results_go_back_to_the_model(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call(
            "propose_project_ideas",
            {"ideas": [IDEA, {**IDEA, "title": "B"}, {**IDEA, "title": "C"}]},
        ),
        say("Which one?"),
    ]

    await send(client, conversation_id, "Ideas please")

    second = fake_ai.calls[1]["messages"]
    assert isinstance(second, list)
    assert [m.role for m in second] == ["user", "assistant", "tool"]
    assert second[1].tool_calls[0].name == "propose_project_ideas"
    result = second[2].tool_results[0]
    assert result.tool_call_id == "c1" and not result.is_error
    assert "3 idea cards" in result.content
    offered = fake_ai.calls[0]["tools"]
    assert isinstance(offered, list)
    assert "propose_project_ideas" in [tool.name for tool in offered]
    assert "search_videos" not in [tool.name for tool in offered], "no YouTube key in tests"


async def test_later_turns_remember_what_was_shown(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call(
            "render_diagram",
            {"title": "Design cycle", "mermaid": "flowchart TD\n A-->B"},
            text="Look:",
        ),
        say("That is the cycle."),
        say("Title"),
        say("Sure."),
    ]
    await send(client, conversation_id, "Show me the design cycle")
    await send(client, conversation_id, "Thanks")

    history = fake_ai.calls[-1]["messages"]
    assert isinstance(history, list)
    assert "[Record: diagram: Design cycle]" in history[1].text
    assert history[1].tool_calls == [], "past tool calls are replayed as notes, not as calls"
    assert "never write such a line yourself" in str(fake_ai.calls[-1]["system"])


async def test_a_bad_tool_call_is_reported_so_the_model_can_fix_it(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call("render_diagram", {"title": "x", "mermaid": "not mermaid at all"}),
        call("render_diagram", {"title": "Cycle", "mermaid": "flowchart LR\n A-->B"}, call_id="c2"),
        say("There it is."),
    ]

    message = final_message(await send(client, conversation_id, "Diagram please"))

    assert [block["type"] for block in message["blocks"]] == ["diagram", "markdown"]
    retry_input = fake_ai.calls[1]["messages"]
    assert isinstance(retry_input, list)
    assert retry_input[-1].tool_results[0].is_error is True


async def test_unknown_tool_does_not_break_the_turn(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [call("make_coffee", {}), say("Sorry, let's carry on.")]

    message = final_message(await send(client, conversation_id, "Hi"))

    assert message["status"] == "complete"
    result = fake_ai.calls[1]["messages"][-1].tool_results[0]  # type: ignore[index]
    assert result.is_error and "no tool called 'make_coffee'" in result.content


async def test_a_crashing_tool_costs_the_tool_not_the_turn(
    client: AsyncClient,
    conversation_id: str,
    fake_ai: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def explode(*_args: object) -> None:
        raise RuntimeError("bug in a tool")

    from app.ai.tools import registry

    broken = registry.render_diagram.__class__(
        name="render_diagram",
        description=registry.render_diagram.description,
        args=registry.render_diagram.args,
        run=explode,  # type: ignore[arg-type]
        status=registry.render_diagram.status,
    )
    monkeypatch.setattr(
        chat_module, "available_tools", lambda _settings: {"render_diagram": broken}
    )
    fake_ai.script = [
        call("render_diagram", {"title": "Cycle", "mermaid": "flowchart LR\n A-->B"}),
        say("I'll explain it in words instead."),
    ]

    message = final_message(await send(client, conversation_id, "Diagram please"))

    assert message["status"] == "complete"
    assert message["blocks"][0]["text"] == "I'll explain it in words instead."


async def test_tool_rounds_are_capped(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider
) -> None:
    looping = call("render_diagram", {"title": "Again", "mermaid": "flowchart LR\n A-->B"})
    fake_ai.script = [looping] * MAX_TOOL_ROUNDS + [say("Right, that is enough diagrams.")]

    message = final_message(await send(client, conversation_id, "Loop"))

    assert message["status"] == "complete"
    chat_calls = [c for c in fake_ai.calls if c["model"] == "fake-model"]
    assert len(chat_calls) == MAX_TOOL_ROUNDS + 1
    assert chat_calls[-1]["tools"] == [], "the final round offers no tools, forcing an answer"
    assert [block["type"] for block in message["blocks"]].count("diagram") == MAX_TOOL_ROUNDS


async def test_usage_is_summed_across_tool_rounds(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider, db: AsyncSession
) -> None:
    fake_ai.script = [
        call("render_diagram", {"title": "Cycle", "mermaid": "flowchart LR\n A-->B"}, text="Look"),
        say("That is it."),
        say("Title"),
    ]

    await send(client, conversation_id, "Diagram please")

    rows = (await db.scalars(select(AIUsage).where(AIUsage.task == "chat"))).all()
    stored = (await db.scalars(select(Message).where(Message.role == "assistant"))).one()
    assert len(rows) == 2, "each model call is metered"
    assert stored.input_tokens == sum(row.input_tokens for row in rows)
    assert stored.output_tokens == sum(row.output_tokens for row in rows)


async def test_choosing_an_idea_in_chat_advances_the_project(
    client: AsyncClient, project: dict[str, Any], conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call("select_idea", {"idea": IDEA, "reason": "I can test it at home"}),
        say("Great choice! Now let's shape your research question."),
        say("Title"),
        say("Go on."),
    ]

    await send(client, conversation_id, "I choose the solar charger")

    updated = (await client.get(f"/api/v1/projects/{project['id']}")).json()
    assert updated["title"] == "Solar phone charger"
    assert updated["current_stage"] == "research_question"
    assert updated["idea"]["title"] == "Solar phone charger"

    await send(client, conversation_id, "What next?")
    system = str(fake_ai.calls[-1]["system"])
    assert "stage 3 of 9: Research Question" in system
    assert "Chosen idea: Solar phone charger" in system
    assert "`final_question`" in system
    assert "**Research Question** (current)" in system


async def test_system_prompt_carries_the_stage_and_its_checklist(
    client: AsyncClient, project: dict[str, Any], conversation_id: str, fake_ai: FakeProvider
) -> None:
    await client.put(
        f"/api/v1/projects/{project['id']}/stages/problem_discovery/checklist/observations",
        json={"done": True},
        headers=csrf(client),
    )

    await send(client, conversation_id, "Hello")

    system = str(fake_ai.calls[0]["system"])
    assert "stage 1 of 9: Problem Discovery" in system
    assert (
        "- [x] List at least three problems you have noticed around you (`observations`)" in system
    )
    assert "- [ ] Pick the one problem you care most about (`chosen_problem`)" in system
    assert "Do not propose project ideas yet" in system
    assert "# Your tools" in system


async def test_a_proposed_stage_change_waits_for_the_learner(
    client: AsyncClient, project: dict[str, Any], conversation_id: str, fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call("advance_stage", {"summary": "You found a real problem."}, text="You're ready."),
        say(""),
    ]

    message = final_message(await send(client, conversation_id, "I think I'm done"))

    card = next(b for b in message["blocks"] if b["type"] == "stage_transition")
    assert (card["from_stage"], card["to_stage"]) == ("problem_discovery", "idea_development")
    assert card["to_title"] == "Idea Development"
    unchanged = (await client.get(f"/api/v1/projects/{project['id']}")).json()
    assert unchanged["current_stage"] == "problem_discovery"


# --- Project memory ----------------------------------------------------------


async def test_memory_is_refreshed_with_the_fast_model_and_used_next_turn(
    client: AsyncClient,
    conversation_id: str,
    fake_ai: FakeProvider,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat_module, "MEMORY_REFRESH_EVERY", 2)
    fake_ai.script = [
        say("Tell me about the tap."),
        say("Title"),
        say("The learner noticed a leaking school tap and wants to measure the waste."),
        say("Good."),
    ]

    await send(client, conversation_id, "Our school tap leaks all day")

    project = (await db.scalars(select(Project))).one()
    assert project.memory.startswith("The learner noticed a leaking school tap")
    assert project.memory_message_count == 2
    summary_call = fake_ai.calls[2]
    assert summary_call["model"] == "fake-fast-model"
    prompt = summary_call["messages"][0].text  # type: ignore[index]
    assert "Learner: Our school tap leaks all day" in prompt
    assert "Mentor: Tell me about the tap." in prompt

    await send(client, conversation_id, "What should I measure?")
    next_chat = [c for c in fake_ai.calls if c["model"] == "fake-model"][-1]
    assert "leaking school tap" in str(next_chat["system"])


async def test_memory_is_not_refreshed_every_turn(
    client: AsyncClient, conversation_id: str, fake_ai: FakeProvider, db: AsyncSession
) -> None:
    await send(client, conversation_id, "Hello")

    assert (await db.scalars(select(Project))).one().memory == ""
    assert not [c for c in fake_ai.calls if "running notes" in str(c["system"])]


async def test_a_failed_summary_keeps_the_old_memory(
    client: AsyncClient,
    conversation_id: str,
    fake_ai: FakeProvider,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat_module, "MEMORY_REFRESH_EVERY", 2)
    project = (await db.scalars(select(Project))).one()
    project.memory = "Earlier notes."
    await db.commit()
    fake_ai.script = [say("Hi."), say("Title"), ProviderError("down", code="auth")]

    await send(client, conversation_id, "Hello")

    await db.refresh(project)
    assert project.memory == "Earlier notes."
    assert project.memory_message_count == 0, "so it is tried again after the next turn"
