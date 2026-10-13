import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.blocks import (
    BomTableBlock,
    ChecklistBlock,
    DiagramBlock,
    IdeaCardsBlock,
    ImageGalleryBlock,
    StageTransitionBlock,
    VideoCardsBlock,
)
from app.ai.tools.base import ToolContext, json_schema
from app.ai.tools.ideas import ProposeIdeasArgs, compare_ideas, propose_project_ideas, select_idea
from app.ai.tools.media import search_images, search_videos
from app.ai.tools.progress import advance_stage, revisit_stage, update_checklist
from app.ai.tools.registry import ALL_TOOLS, available_tools
from app.ai.tools.visuals import build_bill_of_materials, quiz_me, render_chart, render_diagram
from app.core.config import Settings
from app.models import Project
from app.services import pathway, projects
from tests.conftest import make_user


def idea(title: str = "Solar phone charger", **overrides: Any) -> dict[str, Any]:
    return {
        "title": title,
        "problem": "Phones die during load-shedding.",
        "field": "Energy",
        "difficulty": 3,
        "cost_min_zar": 150,
        "cost_max_zar": 400,
        "materials": ["small solar panel", "USB module"],
        "time_needed": "3 weeks",
        "why_judges_like_it": "Solves a real local problem with measurable results.",
        "safety_level": "low",
        **overrides,
    }


def offline(_request: httpx.Request) -> httpx.Response:
    raise AssertionError("this tool should not have made a network call")


@pytest.fixture
async def project(db: AsyncSession) -> Project:
    user = await make_user(db, email="learner@example.com")
    created, _ = await projects.create(db, user, "")
    return created


@pytest.fixture
def context(db: AsyncSession, project: Project, settings: Settings) -> ToolContext:
    return ToolContext(
        session=db,
        project=project,
        settings=settings,
        http=httpx.AsyncClient(transport=httpx.MockTransport(offline)),
    )


# --- The framework -----------------------------------------------------------


def test_every_tool_has_a_self_contained_schema_and_a_real_description() -> None:
    names = [tool.name for tool in ALL_TOOLS]
    assert len(names) == len(set(names))
    for tool in ALL_TOOLS:
        schema = json.dumps(tool.spec.parameters)
        assert "$ref" not in schema and "$defs" not in schema, tool.name
        assert tool.spec.parameters["type"] == "object"
        assert len(tool.description) > 80, f"{tool.name} needs a description the model can act on"


def test_schema_inlining_keeps_field_descriptions() -> None:
    schema = json_schema(ProposeIdeasArgs)

    card = schema["properties"]["ideas"]["items"]
    assert card["properties"]["difficulty"]["description"].startswith("1 = very easy")
    assert "title" in card["properties"], "a property named 'title' must survive"
    assert "title" not in card or isinstance(card.get("title"), dict)


async def test_invalid_arguments_are_explained_to_the_model(context: ToolContext) -> None:
    outcome = await propose_project_ideas.call(context, {"ideas": [idea(difficulty=9)]})

    assert outcome.is_error
    assert outcome.blocks == []
    assert "ideas" in outcome.result and "call the tool again" in outcome.result


# --- Ideas -------------------------------------------------------------------


async def test_propose_ideas_shows_cards(context: ToolContext) -> None:
    outcome = await propose_project_ideas.call(
        context, {"ideas": [idea("A"), idea("B"), idea("C")]}
    )

    assert not outcome.is_error
    block = outcome.blocks[0]
    assert isinstance(block, IdeaCardsBlock)
    assert [card.title for card in block.ideas] == ["A", "B", "C"]
    assert outcome.record == "idea cards: 1. A; 2. B; 3. C"


async def test_comparison_rows_must_match_the_options(context: ToolContext) -> None:
    arguments = {
        "options": ["A", "B"],
        "rows": [
            {"criterion": "Cost", "values": ["R100", "R300"]},
            {"criterion": "Time", "values": ["2 weeks"]},
            {"criterion": "Safety", "values": ["low", "low"]},
        ],
    }

    outcome = await compare_ideas.call(context, arguments)

    assert outcome.is_error and "'Time' has 1 values" in outcome.result


async def test_selecting_an_idea_names_the_project_and_moves_it_on(
    context: ToolContext, db: AsyncSession, project: Project
) -> None:
    outcome = await select_idea.call(context, {"idea": idea(), "reason": "I can test it at home"})

    assert not outcome.is_error
    await db.refresh(project)
    assert project.title == "Solar phone charger"
    assert project.idea is not None and project.idea["reason"] == "I can test it at home"
    assert project.current_stage == "research_question"
    statuses = {s.definition.key: s.state.status for s in await pathway.progress(db, project)}
    assert statuses["problem_discovery"] == statuses["idea_development"] == "completed"
    assert statuses["research_question"] == "active"
    assert statuses["method"] == "locked"


# --- Progress ----------------------------------------------------------------


async def test_checklist_items_need_evidence_to_be_ticked(context: ToolContext) -> None:
    outcome = await update_checklist.call(
        context, {"updates": [{"item_key": "observations", "done": True}]}
    )

    assert outcome.is_error and "what the learner did" in outcome.result


async def test_ticking_a_checklist_item(
    context: ToolContext, db: AsyncSession, project: Project
) -> None:
    outcome = await update_checklist.call(
        context,
        {
            "updates": [
                {
                    "item_key": "observations",
                    "done": True,
                    "evidence": "Listed taps, litter and load-shedding",
                }
            ]
        },
    )

    assert outcome.blocks == [ChecklistBlock(stage_key="problem_discovery")]
    assert "Still to do" in outcome.result
    stage = pathway.current(await pathway.progress(db, project), project)
    ticked = next(item for item in stage.items if item["key"] == "observations")
    assert ticked["done"] and ticked["note"].startswith("Listed taps")


async def test_unknown_checklist_key_lists_the_valid_ones(context: ToolContext) -> None:
    outcome = await update_checklist.call(
        context, {"updates": [{"item_key": "nope", "done": True, "evidence": "x"}]}
    )

    assert outcome.is_error
    assert "observations" in outcome.result and "chosen_problem" in outcome.result


async def test_advance_stage_only_proposes(
    context: ToolContext, db: AsyncSession, project: Project
) -> None:
    outcome = await advance_stage.call(context, {"summary": "You found a real problem."})

    block = outcome.blocks[0]
    assert isinstance(block, StageTransitionBlock)
    assert (block.from_stage, block.to_stage) == ("problem_discovery", "idea_development")
    assert "Nothing has changed yet" in outcome.result
    assert "still unticked" in outcome.result
    await db.refresh(project)
    assert project.current_stage == "problem_discovery", "only the learner's confirmation moves it"


async def test_cannot_advance_past_the_last_stage(
    context: ToolContext, db: AsyncSession, project: Project
) -> None:
    await pathway.move_to(db, project, "expo_preparation")
    await db.commit()

    outcome = await advance_stage.call(context, {"summary": "Done"})

    assert outcome.is_error and "final stage" in outcome.result


async def test_revisit_goes_back_but_not_forward(
    context: ToolContext, db: AsyncSession, project: Project
) -> None:
    await pathway.move_to(db, project, "method")
    await db.commit()

    forward = await revisit_stage.call(context, {"stage_key": "testing_analysis", "reason": "x"})
    back = await revisit_stage.call(
        context, {"stage_key": "research_question", "reason": "The question was too broad"}
    )

    assert forward.is_error
    assert not back.is_error
    await db.refresh(project)
    assert project.current_stage == "research_question"


# --- Visuals -----------------------------------------------------------------


async def test_diagram_strips_code_fences(context: ToolContext) -> None:
    outcome = await render_diagram.call(
        context, {"title": "Design cycle", "mermaid": "```mermaid\nflowchart TD\n  A --> B\n```"}
    )

    block = outcome.blocks[0]
    assert isinstance(block, DiagramBlock)
    assert block.mermaid == "flowchart TD\n  A --> B"


async def test_diagram_rejects_text_that_is_not_mermaid(context: ToolContext) -> None:
    outcome = await render_diagram.call(
        context, {"title": "x", "mermaid": "First you ask a question, then you test it."}
    )

    assert outcome.is_error and "flowchart TD" in outcome.result


async def test_bill_of_materials_total_is_computed_not_trusted(context: ToolContext) -> None:
    outcome = await build_bill_of_materials.call(
        context,
        {
            "items": [
                {"name": "LED", "quantity": 5, "unit_price_zar": 2.5},
                {"name": "Resistor", "quantity": 5, "unit_price_zar": 1},
                {
                    "name": "Cardboard",
                    "quantity": 1,
                    "unit_price_zar": 0,
                    "substitute": "a cereal box",
                },
            ],
            "total_zar": 9999,
        },
    )

    block = outcome.blocks[0]
    assert isinstance(block, BomTableBlock)
    assert block.total_zar == 17.5
    assert "R17.50" in outcome.result


async def test_quiz_answer_index_must_exist(context: ToolContext) -> None:
    outcome = await quiz_me.call(
        context,
        {
            "questions": [
                {
                    "question": "Which variable do you change?",
                    "options": ["Independent", "Dependent"],
                    "correct_index": 3,
                    "explanation": "The independent variable is the one you change.",
                }
            ]
        },
    )

    assert outcome.is_error and "out of range" in outcome.result


async def test_chart_accepts_numbers_and_categories(context: ToolContext) -> None:
    outcome = await render_chart.call(
        context,
        {
            "chart_type": "bar",
            "title": "Plant height by fertiliser",
            "x_label": "Fertiliser",
            "y_label": "Height (cm)",
            "series": [
                {"name": "Height", "points": [{"x": "None", "y": 4}, {"x": "Compost", "y": 9.5}]}
            ],
        },
    )

    assert not outcome.is_error and outcome.blocks[0].type == "chart"


# --- Photos and videos -------------------------------------------------------


def commons_page(index: int, title: str, **info: Any) -> dict[str, Any]:
    return {
        "index": index,
        "title": f"File:{title}.jpg",
        "imageinfo": [
            {
                "mime": "image/jpeg",
                "url": f"https://upload.example/{index}.jpg",
                "thumburl": f"https://upload.example/thumb/{index}.jpg",
                "descriptionurl": f"https://commons.example/File:{index}",
                "thumbwidth": 640,
                "thumbheight": 480,
                "extmetadata": {
                    "Artist": {"value": '<a href="//x">Jane <b>Doe</b></a>'},
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                    "ImageDescription": {"value": "A photo"},
                },
                **info,
            }
        ],
    }


def serving(payload: Any, seen: list[httpx.Request] | None = None) -> httpx.AsyncClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def test_image_search_returns_a_credited_gallery_in_rank_order(context: ToolContext) -> None:
    seen: list[httpx.Request] = []
    context.http = serving(
        {
            "query": {
                "pages": {
                    "9": commons_page(2, "Breadboard_close_up"),
                    "4": commons_page(1, "Breadboard"),
                    "7": commons_page(3, "Datasheet", mime="application/pdf"),
                    "8": commons_page(4, "Nude_figure_study"),
                }
            }
        },
        seen,
    )

    outcome = await search_images.call(context, {"query": "breadboard"})

    block = outcome.blocks[0]
    assert isinstance(block, ImageGalleryBlock)
    assert [image.title for image in block.images] == ["Breadboard", "Breadboard close up"]
    assert block.images[0].author == "Jane Doe", "HTML in metadata is reduced to plain text"
    assert block.images[0].license == "CC BY-SA 4.0"
    assert block.images[0].source_url.startswith("https://commons.example/")
    assert "MentorPilot" in seen[0].headers["user-agent"]
    assert "not seen the photos" in outcome.result


async def test_image_search_caps_the_number_of_results(context: ToolContext) -> None:
    context.http = serving(
        {"query": {"pages": {str(n): commons_page(n, f"LED_{n}") for n in range(1, 13)}}}
    )

    outcome = await search_images.call(context, {"query": "LED"})

    assert len(outcome.blocks[0].images) == 6  # type: ignore[union-attr]


async def test_image_search_outage_is_reported_not_raised(context: ToolContext) -> None:
    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    context.http = httpx.AsyncClient(transport=httpx.MockTransport(down))

    outcome = await search_images.call(context, {"query": "LED"})

    assert outcome.is_error and "unavailable" in outcome.result


async def test_unsuitable_image_queries_are_refused_without_a_request(
    context: ToolContext,
) -> None:
    outcome = await search_images.call(context, {"query": "nude photo"})

    assert outcome.is_error


async def test_no_results_is_not_an_error(context: ToolContext) -> None:
    context.http = serving({"batchcomplete": ""})

    outcome = await search_images.call(context, {"query": "zzzqqq"})

    assert not outcome.is_error and outcome.blocks == []


def test_video_search_is_only_offered_when_a_key_is_set(settings: Settings) -> None:
    assert "search_videos" not in available_tools(settings)
    with_key = settings.model_copy(update={"youtube_api_key": SecretStr("k")})
    assert "search_videos" in available_tools(with_key)
    assert "search_images" in available_tools(settings), "photos need no key"


async def test_video_search_uses_strict_safe_search(context: ToolContext) -> None:
    seen: list[httpx.Request] = []
    context.settings = context.settings.model_copy(update={"youtube_api_key": SecretStr("secret")})
    context.http = serving(
        {
            "items": [
                {
                    "id": {"videoId": "abc123"},
                    "snippet": {
                        "title": "How a breadboard works &amp; why",
                        "channelTitle": "Science Class",
                        "thumbnails": {"medium": {"url": "https://img.example/abc.jpg"}},
                    },
                },
                {"id": {"kind": "channel"}, "snippet": {"title": "not a video"}},
            ]
        },
        seen,
    )

    outcome = await search_videos.call(context, {"query": "how a breadboard works"})

    block = outcome.blocks[0]
    assert isinstance(block, VideoCardsBlock)
    assert [(v.video_id, v.title) for v in block.videos] == [
        ("abc123", "How a breadboard works & why")
    ]
    assert seen[0].url.params["safeSearch"] == "strict"
    assert seen[0].url.params["videoEmbeddable"] == "true"
    assert "not watched them" in outcome.result
