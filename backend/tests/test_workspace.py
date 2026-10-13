import base64
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.fake import FakeProvider
from app.core.config import Settings
from app.models import Attachment, User
from app.services.workspace import sniff_image_type
from tests.conftest import PASSWORD, csrf, login_as, make_client, make_user
from tests.test_chat import final_message, say
from tests.test_pathway import call

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@pytest.fixture
async def learner(client: AsyncClient, db: AsyncSession) -> User:
    user = await make_user(db, email="learner@example.com")
    await login_as(client, "learner@example.com")
    return user


@pytest.fixture
async def project(client: AsyncClient, learner: User) -> dict[str, Any]:
    body: dict[str, Any] = (
        await client.post("/api/v1/projects", json={"title": "Tap water"}, headers=csrf(client))
    ).json()
    return body


@pytest.fixture
async def stranger(db: AsyncSession, app: FastAPI) -> AsyncClient:
    await make_user(db, email="other@example.com")
    other = make_client(app)
    await login_as(other, "other@example.com")
    return other


async def upload(client: AsyncClient, project_id: str, data: bytes = PNG, name: str = "sketch.png"):  # type: ignore[no-untyped-def]
    return await client.post(
        f"/api/v1/projects/{project_id}/attachments",
        files={"file": (name, data, "image/png")},
        headers=csrf(client),
    )


# --- Logbook -----------------------------------------------------------------


async def test_logbook_entries_are_dated_and_tagged_with_the_stage(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    url = f"/api/v1/projects/{project['id']}/logbook"
    await client.post(url, json={"text": "Counted drips for 10 minutes."}, headers=csrf(client))
    second = await client.post(
        url, json={"text": "Tap leaks 40 ml a minute."}, headers=csrf(client)
    )

    assert second.status_code == 201
    entries = (await client.get(url)).json()
    assert [entry["text"] for entry in entries] == [
        "Tap leaks 40 ml a minute.",
        "Counted drips for 10 minutes.",
    ]
    assert entries[0]["stage_key"] == "problem_discovery"


async def test_editing_a_logbook_entry_keeps_its_original_date(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    created = (
        await client.post(
            f"/api/v1/projects/{project['id']}/logbook",
            json={"text": "Frist try"},
            headers=csrf(client),
        )
    ).json()

    edited = await client.put(
        f"/api/v1/logbook/{created['id']}", json={"text": "First try"}, headers=csrf(client)
    )

    assert edited.json()["text"] == "First try"
    assert edited.json()["created_at"] == created["created_at"]
    deleted = await client.delete(f"/api/v1/logbook/{created['id']}", headers=csrf(client))
    assert deleted.status_code == 204


async def test_logbook_is_private(
    client: AsyncClient, project: dict[str, Any], stranger: AsyncClient
) -> None:
    entry = (
        await client.post(
            f"/api/v1/projects/{project['id']}/logbook", json={"text": "Mine"}, headers=csrf(client)
        )
    ).json()

    assert (await stranger.get(f"/api/v1/projects/{project['id']}/logbook")).status_code == 404
    assert (
        await stranger.put(
            f"/api/v1/logbook/{entry['id']}", json={"text": "Hacked"}, headers=csrf(stranger)
        )
    ).status_code == 404


# --- Saved blocks ------------------------------------------------------------


async def reply_with_diagram(client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider):  # type: ignore[no-untyped-def]
    fake_ai.script = [
        call(
            "render_diagram",
            {"title": "Water cycle", "mermaid": "flowchart TD\n A-->B"},
            text="Look:",
        ),
        say("That is the cycle.\n\n:::replies\nThanks\n:::"),
        say("Title"),
    ]
    response = await client.post(
        f"/api/v1/conversations/{project['latest_conversation']['id']}/messages",
        json={"text": "Show me"},
        headers=csrf(client),
    )
    return final_message(response)


async def test_a_block_can_be_saved_and_survives_regeneration(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider
) -> None:
    message = await reply_with_diagram(client, project, fake_ai)
    url = f"/api/v1/projects/{project['id']}/pins"

    pinned = await client.post(
        url, json={"message_id": message["id"], "block_index": 1}, headers=csrf(client)
    )

    assert pinned.status_code == 201
    assert pinned.json()["title"] == "Water cycle"
    assert pinned.json()["block"]["type"] == "diagram"

    await client.post(
        f"/api/v1/conversations/{project['latest_conversation']['id']}/regenerate",
        headers=csrf(client),
    )
    saved = (await client.get(url)).json()
    assert len(saved) == 1 and saved[0]["block"]["mermaid"].startswith("flowchart")
    assert saved[0]["message_id"] is None, "the pin keeps its own copy of the block"

    assert (
        await client.delete(f"/api/v1/pins/{saved[0]['id']}", headers=csrf(client))
    ).status_code == 204
    assert (await client.get(url)).json() == []


async def test_text_blocks_are_titled_by_their_first_line(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider
) -> None:
    message = await reply_with_diagram(client, project, fake_ai)

    pinned = await client.post(
        f"/api/v1/projects/{project['id']}/pins",
        json={"message_id": message["id"], "block_index": 0},
        headers=csrf(client),
    )

    assert pinned.json()["title"] == "Look:"


async def test_reply_chips_and_missing_blocks_cannot_be_saved(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider
) -> None:
    message = await reply_with_diagram(client, project, fake_ai)
    url = f"/api/v1/projects/{project['id']}/pins"

    chips = await client.post(
        url, json={"message_id": message["id"], "block_index": 3}, headers=csrf(client)
    )
    missing = await client.post(
        url, json={"message_id": message["id"], "block_index": 9}, headers=csrf(client)
    )

    assert (chips.status_code, chips.json()["code"]) == (400, "not_pinnable")
    assert missing.status_code == 404


# --- Experiment data ---------------------------------------------------------


async def test_dataset_rows_are_squared_up_to_the_header(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    url = f"/api/v1/projects/{project['id']}/datasets"

    created = await client.post(
        url,
        json={
            "title": "Drips",
            "columns": ["Trial", "ml"],
            "rows": [["1", "40"], ["2"], ["3", "41", "x"]],
        },
        headers=csrf(client),
    )

    assert created.status_code == 201
    assert created.json()["rows"] == [["1", "40"], ["2", ""], ["3", "41"]]

    updated = await client.put(
        f"/api/v1/datasets/{created.json()['id']}",
        json={"title": "Drips", "columns": ["Trial", "ml", "Notes"], "rows": [["1", "40"]]},
        headers=csrf(client),
    )
    assert updated.json()["rows"] == [["1", "40", ""]]
    assert [d["title"] for d in (await client.get(url)).json()] == ["Drips"]


async def test_datasets_are_private(
    client: AsyncClient, project: dict[str, Any], stranger: AsyncClient
) -> None:
    created = (
        await client.post(
            f"/api/v1/projects/{project['id']}/datasets",
            json={"columns": ["a"], "rows": []},
            headers=csrf(client),
        )
    ).json()

    response = await stranger.put(
        f"/api/v1/datasets/{created['id']}",
        json={"columns": ["x"], "rows": []},
        headers=csrf(stranger),
    )
    assert response.status_code == 404


# --- Photo uploads -----------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (PNG, ("image/png", "png")),
        (b"\xff\xd8\xff\xe0" + b"0" * 20, ("image/jpeg", "jpg")),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", ("image/webp", "webp")),
        (b"<svg onload=alert(1)>", None),
        (b"%PDF-1.7", None),
        (b"GIF89a", None),
        (b"", None),
    ],
)
def test_images_are_recognised_by_content_not_by_name(
    data: bytes, expected: tuple[str, str] | None
) -> None:
    assert sniff_image_type(data) == expected


async def test_upload_and_fetch_a_photo(
    client: AsyncClient, project: dict[str, Any], stranger: AsyncClient
) -> None:
    uploaded = await upload(client, project["id"], name="../../etc/passwd.png")

    assert uploaded.status_code == 201
    assert uploaded.json()["content_type"] == "image/png"
    fetched = await client.get(f"/api/v1/attachments/{uploaded.json()['id']}")
    assert fetched.content == PNG
    assert fetched.headers["content-type"] == "image/png"
    assert "sandbox" in fetched.headers["content-security-policy"]
    assert (await stranger.get(f"/api/v1/attachments/{uploaded.json()['id']}")).status_code == 404


async def test_the_stored_name_is_ours_not_the_uploaders(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, settings: Settings
) -> None:
    await upload(client, project["id"], name="../../etc/passwd.png")

    stored = (await db.scalars(select(Attachment))).one()
    assert stored.storage_key == f"{project['id']}/{stored.id}.png"
    assert (settings.upload_dir / stored.storage_key).is_file()


async def test_files_that_are_not_images_are_refused(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    disguised = await upload(client, project["id"], data=b"<script>alert(1)</script>", name="x.png")

    assert disguised.status_code == 415
    assert disguised.json()["code"] == "unsupported_file_type"


async def test_oversized_photos_are_refused(
    client: AsyncClient, project: dict[str, Any], settings: Settings
) -> None:
    too_big = await upload(client, project["id"], data=PNG + b"0" * settings.max_upload_bytes)

    assert too_big.status_code == 413


async def test_an_attached_photo_is_shown_to_the_model_once(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider
) -> None:
    photo = (await upload(client, project["id"])).json()
    conversation = project["latest_conversation"]["id"]

    first = await client.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"text": "Is my circuit right?", "attachment_ids": [photo["id"]]},
        headers=csrf(client),
    )

    sent = fake_ai.calls[0]["messages"]
    assert isinstance(sent, list)
    assert sent[-1].images[0].media_type == "image/png"
    assert base64.b64decode(sent[-1].images[0].data_base64) == PNG
    assert "I can see 1 image" in final_message(first)["blocks"][0]["text"]

    stored = (await client.get(f"/api/v1/conversations/{conversation}/messages")).json()["messages"]
    assert stored[0]["blocks"][1] == {
        "type": "image",
        "attachment_id": photo["id"],
        "alt": "Photo from the learner",
    }

    await client.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"text": "And now?"},
        headers=csrf(client),
    )
    later = [c for c in fake_ai.calls if c["model"] == "fake-model"][-1]["messages"]
    assert isinstance(later, list)
    assert later[0].images == [], "earlier photos are not resent"
    assert "attached a photo here" in later[0].text


async def test_a_photo_from_another_learner_cannot_be_attached(
    client: AsyncClient, project: dict[str, Any], stranger: AsyncClient
) -> None:
    theirs = (await stranger.post("/api/v1/projects", json={}, headers=csrf(stranger))).json()
    photo = (await upload(stranger, theirs["id"])).json()

    response = await client.post(
        f"/api/v1/conversations/{project['latest_conversation']['id']}/messages",
        json={"text": "Look", "attachment_ids": [photo["id"]]},
        headers=csrf(client),
    )

    assert response.status_code == 404


async def test_deleting_the_account_removes_uploaded_files(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, settings: Settings
) -> None:
    await upload(client, project["id"])
    stored = (await db.scalars(select(Attachment))).one()
    path = settings.upload_dir / stored.storage_key
    assert path.is_file()

    await client.post(
        "/api/v1/users/me/delete",
        json={"confirm": "DELETE", "password": PASSWORD},
        headers=csrf(client),
    )

    assert not path.exists()


# --- Judge practice ----------------------------------------------------------


async def test_judge_practice_starts_then_scores(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider
) -> None:
    conversation = project["latest_conversation"]["id"]
    fake_ai.script = [
        call("judge_practice", {"action": "start"}),
        say("I'll ask you five questions as a judge would. First: why this project?"),
        say("Title"),
        call(
            "judge_practice",
            {
                "action": "score",
                "scores": [
                    {"criterion": "Understanding", "score": 4, "comment": "Clear on variables."},
                    {"criterion": "Method", "score": 3, "comment": "Only one trial."},
                    {"criterion": "Communication", "score": 5, "comment": "Confident."},
                ],
                "strengths": ["Explained the problem well"],
                "improvements": ["Repeat each trial three times"],
            },
        ),
        say("Well done. Want to practise the method questions again?"),
    ]

    await client.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"text": "Quiz me like a judge"},
        headers=csrf(client),
    )
    rules = fake_ai.calls[1]["messages"][-1].tool_results[0].content  # type: ignore[index]
    assert "ONE question at a time" in rules and "action 'score'" in rules

    scored = final_message(
        await client.post(
            f"/api/v1/conversations/{conversation}/messages",
            json={"text": "Because of load-shedding"},
            headers=csrf(client),
        )
    )
    card = scored["blocks"][0]
    assert card["type"] == "judge_scorecard"
    assert [s["score"] for s in card["scores"]] == [4, 3, 5]
    assert card["improvements"] == ["Repeat each trial three times"]


async def test_an_empty_scorecard_is_sent_back(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call("judge_practice", {"action": "score"}),
        say("Let me score that properly."),
    ]

    await client.post(
        f"/api/v1/conversations/{project['latest_conversation']['id']}/messages",
        json={"text": "Score me"},
        headers=csrf(client),
    )

    result = fake_ai.calls[1]["messages"][-1].tool_results[0]  # type: ignore[index]
    assert result.is_error and "at least three rubric scores" in result.content


# --- PDF export --------------------------------------------------------------


async def test_project_summary_pdf_contains_the_learners_work(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider, stranger: AsyncClient
) -> None:
    from io import BytesIO

    from pypdf import PdfReader

    base = f"/api/v1/projects/{project['id']}"
    await client.post(
        f"{base}/logbook",
        json={"text": "Measured the drip: 40 ml → too much “waste”."},
        headers=csrf(client),
    )
    await client.post(
        f"{base}/datasets",
        json={"title": "Drips", "columns": ["Trial", "ml"], "rows": [["1", "40"], ["2", "38"]]},
        headers=csrf(client),
    )
    await client.put(
        f"{base}/stages/problem_discovery/checklist/observations",
        json={"done": True},
        headers=csrf(client),
    )

    response = await client.get(f"{base}/export.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="tap-water-summary.pdf"' in response.headers["content-disposition"]
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    assert "Tap water" in text and "Test User" in text
    assert "Stage 1 of 9: Problem Discovery" in text
    assert "[x] List at least three problems" in text
    assert "Data: Drips" in text and "38" in text
    assert 'Measured the drip: 40 ml -> too much "waste".' in text
    assert (await stranger.get(f"{base}/export.pdf")).status_code == 404
