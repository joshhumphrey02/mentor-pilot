from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.fake import FLAG_WORD, FakeProvider
from app.models import AIUsage, MentorProfile, ModerationFlag, User, UserRole
from tests.conftest import PASSWORD, Outbox, csrf, login_as, make_client, make_user
from tests.test_chat import final_message, say
from tests.test_pathway import call

MENTOR = {
    "email": "mentor@example.com",
    "password": PASSWORD,
    "full_name": "Sipho Dlamini",
    "accept_privacy": True,
    "organisation": "Makerspace CT",
    "expertise": ["hardware_build", "coding"],
    "regions": ["Western Cape"],
    "availability": "Saturdays",
}
ASK = {"help_types": ["hardware_build"], "description": "I need help soldering my solar charger."}


@pytest.fixture
async def learner(client: AsyncClient, db: AsyncSession) -> User:
    from app.models import School, StudentProfile

    user = await make_user(db, email="learner@example.com")
    school = School(name="Langa High", province="Western Cape")
    db.add(school)
    await db.flush()
    db.add(
        StudentProfile(user_id=user.id, school_id=school.id, province="Western Cape", grade="10")
    )
    await db.commit()
    await login_as(client, "learner@example.com")
    return user


@pytest.fixture
async def project(client: AsyncClient, learner: User) -> dict[str, Any]:
    body: dict[str, Any] = (
        await client.post("/api/v1/projects", json={"title": "Solar charger"}, headers=csrf(client))
    ).json()
    return body


async def make_mentor(
    db: AsyncSession,
    app: FastAPI,
    *,
    email: str = "mentor@example.com",
    approved: bool = True,
    regions: list[str] | None = None,
    expertise: list[str] | None = None,
) -> AsyncClient:
    user = await make_user(db, email=email, role=UserRole.MENTOR)
    user.full_name = "Sipho Dlamini"
    db.add(
        MentorProfile(
            user_id=user.id,
            expertise=expertise or ["hardware_build"],
            regions=regions or ["Western Cape"],
            is_approved=approved,
        )
    )
    await db.commit()
    mentor = make_client(app)
    await login_as(mentor, email)
    return mentor


async def admin_client(db: AsyncSession, app: FastAPI) -> AsyncClient:
    await make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    admin = make_client(app)
    await login_as(admin, "admin@example.com")
    return admin


async def ask(client: AsyncClient, project: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/projects/{project['id']}/mentor-requests", json=ASK, headers=csrf(client)
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


# --- The handoff -------------------------------------------------------------


async def test_the_mentor_can_offer_a_human_but_does_not_send_the_request(
    client: AsyncClient, project: dict[str, Any], fake_ai: FakeProvider
) -> None:
    fake_ai.script = [
        call(
            "request_human_mentor",
            {"help_types": ["hardware_build"], "reason": "Soldering needs supervision."},
        ),
        say("Meanwhile, let's finish your materials list."),
    ]

    message = final_message(
        await client.post(
            f"/api/v1/conversations/{project['latest_conversation']['id']}/messages",
            json={"text": "I need to solder"},
            headers=csrf(client),
        )
    )

    assert message["blocks"][0] == {
        "type": "mentor_handoff",
        "help_types": ["hardware_build"],
        "reason": "Soldering needs supervision.",
    }
    assert (await client.get("/api/v1/mentor-requests")).json() == []


async def test_a_request_carries_a_project_snapshot_and_only_a_first_name(
    client: AsyncClient, project: dict[str, Any]
) -> None:
    request = await ask(client, project)

    assert request["status"] == "pending"
    assert request["province"] == "Western Cape"
    assert request["school_name"] == "Langa High"
    assert request["snapshot"]["title"] == "Solar charger"
    assert request["snapshot"]["stage"] == "Problem Discovery"
    assert request["learner"]["first_name"] == "Test"
    assert "email" not in str(request) and "User" not in request["learner"]["first_name"]
    assert request["mentor"] is None


async def test_one_open_request_per_project(client: AsyncClient, project: dict[str, Any]) -> None:
    await ask(client, project)

    again = await client.post(
        f"/api/v1/projects/{project['id']}/mentor-requests", json=ASK, headers=csrf(client)
    )
    assert (again.status_code, again.json()["code"]) == (409, "request_exists")


# --- Mentors -----------------------------------------------------------------


async def test_mentor_signup_needs_email_confirmation_then_admin_approval(
    client: AsyncClient, outbox: Outbox, db: AsyncSession
) -> None:
    response = await client.post("/api/v1/mentors/register", json=MENTOR)
    assert response.status_code == 202
    await client.post(
        "/api/v1/auth/verify-email", json={"token": outbox.token_for(MENTOR["email"])}
    )

    me = (await client.get("/api/v1/users/me")).json()
    assert (me["role"], me["is_onboarded"]) == ("mentor", True)
    profile = (await client.get("/api/v1/mentors/me")).json()
    assert profile["is_approved"] is False
    assert profile["expertise"] == ["hardware_build", "coding"]

    blocked = await client.get("/api/v1/mentors/open-requests")
    assert (blocked.status_code, blocked.json()["code"]) == (403, "mentor_not_approved")


async def test_registering_an_existing_email_as_a_mentor_reveals_nothing(
    client: AsyncClient, outbox: Outbox, db: AsyncSession
) -> None:
    await make_user(db, email=MENTOR["email"])

    response = await client.post("/api/v1/mentors/register", json=MENTOR)

    assert response.status_code == 202
    assert "already have" in outbox.last_to(MENTOR["email"]).subject
    assert (await db.scalars(select(User))).one().role == "student"


async def test_learners_cannot_use_mentor_endpoints(client: AsyncClient, learner: User) -> None:
    assert (await client.get("/api/v1/mentors/open-requests")).status_code == 403


async def test_open_requests_match_region_and_expertise(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, app: FastAPI
) -> None:
    request = await ask(client, project)
    nearby = await make_mentor(db, app)
    far = await make_mentor(db, app, email="far@example.com", regions=["Gauteng"])
    other_skill = await make_mentor(db, app, email="coach@example.com", expertise=["expo_coaching"])

    assert [r["id"] for r in (await nearby.get("/api/v1/mentors/open-requests")).json()] == [
        request["id"]
    ]
    assert (await far.get("/api/v1/mentors/open-requests")).json() == []
    assert (await other_skill.get("/api/v1/mentors/open-requests")).json() == []


async def test_only_one_mentor_can_accept(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, app: FastAPI
) -> None:
    request = await ask(client, project)
    first = await make_mentor(db, app)
    second = await make_mentor(db, app, email="second@example.com")
    url = f"/api/v1/mentor-requests/{request['id']}/accept"

    won = await first.post(url, headers=csrf(first))
    lost = await second.post(url, headers=csrf(second))

    assert won.status_code == 200
    assert (won.json()["status"], won.json()["mentor"]["first_name"]) == ("matched", "Sipho")
    assert (lost.status_code, lost.json()["code"]) == (409, "already_matched")
    assert (await client.get("/api/v1/mentor-requests")).json()[0]["status"] == "matched"
    assert (await second.get(f"/api/v1/mentor-requests/{request['id']}")).status_code == 404


async def test_unapproved_mentors_cannot_accept(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, app: FastAPI
) -> None:
    request = await ask(client, project)
    unvetted = await make_mentor(db, app, approved=False)

    response = await unvetted.post(
        f"/api/v1/mentor-requests/{request['id']}/accept", headers=csrf(unvetted)
    )
    assert response.status_code == 403


# --- Messaging ---------------------------------------------------------------


@pytest.fixture
async def matched(
    client: AsyncClient,
    project: dict[str, Any],
    db: AsyncSession,
    app: FastAPI,
    fake_ai: FakeProvider,
) -> tuple[AsyncClient, str]:
    request = await ask(client, project)
    mentor = await make_mentor(db, app)
    await mentor.post(f"/api/v1/mentor-requests/{request['id']}/accept", headers=csrf(mentor))
    return mentor, f"/api/v1/mentor-requests/{request['id']}"


async def test_learner_and_mentor_can_message_each_other(
    client: AsyncClient, matched: tuple[AsyncClient, str], fake_ai: FakeProvider
) -> None:
    mentor, url = matched

    await mentor.post(
        f"{url}/messages", json={"text": "Hi! What have you built so far?"}, headers=csrf(mentor)
    )
    await client.post(f"{url}/messages", json={"text": "Just the frame."}, headers=csrf(client))

    thread = (await client.get(f"{url}/messages")).json()
    assert [(m["sender"]["first_name"], m["mine"], m["text"]) for m in thread] == [
        ("Sipho", False, "Hi! What have you built so far?"),
        ("Test", True, "Just the frame."),
    ]
    assert fake_ai.calls == [], "no AI takes part in this conversation"


@pytest.mark.parametrize(
    "text",
    [
        "Call me on 082 555 0142",
        "my number is +27825550142",
        "email me at sipho@gmail.com",
        "add me on WhatsApp",
        "my insta is @sipho_makes",
        "see https://example.com/me",
    ],
)
async def test_contact_details_cannot_be_shared(
    client: AsyncClient, matched: tuple[AsyncClient, str], text: str
) -> None:
    mentor, url = matched

    response = await mentor.post(f"{url}/messages", json={"text": text}, headers=csrf(mentor))

    assert (response.status_code, response.json()["code"]) == (400, "contact_details_not_allowed")
    assert (await client.get(f"{url}/messages")).json() == []


async def test_ordinary_project_talk_with_numbers_is_allowed(
    client: AsyncClient, matched: tuple[AsyncClient, str]
) -> None:
    _, url = matched

    response = await client.post(
        f"{url}/messages",
        json={"text": "The panel gives 5.2 V at 12:30 and I used 3 resistors of 220 ohm."},
        headers=csrf(client),
    )
    assert response.status_code == 201


async def test_unsafe_messages_are_blocked_and_flagged(
    client: AsyncClient, matched: tuple[AsyncClient, str], db: AsyncSession
) -> None:
    mentor, url = matched

    response = await mentor.post(
        f"{url}/messages", json={"text": f"hello {FLAG_WORD}"}, headers=csrf(mentor)
    )

    assert (response.status_code, response.json()["code"]) == (400, "message_blocked")
    flag = (await db.scalars(select(ModerationFlag))).one()
    assert flag.direction == "mentor_chat"


async def test_messages_open_only_while_matched(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, app: FastAPI
) -> None:
    request = await ask(client, project)
    url = f"/api/v1/mentor-requests/{request['id']}"

    before = await client.post(
        f"{url}/messages", json={"text": "Anyone there?"}, headers=csrf(client)
    )
    assert before.json()["code"] == "thread_closed"

    mentor = await make_mentor(db, app)
    await mentor.post(f"{url}/accept", headers=csrf(mentor))
    await mentor.post(f"{url}/status", json={"status": "completed"}, headers=csrf(mentor))
    after = await client.post(
        f"{url}/messages", json={"text": "Thanks again"}, headers=csrf(client)
    )
    assert after.json()["code"] == "thread_closed"


async def test_only_the_mentor_updates_status_and_only_the_learner_cancels(
    client: AsyncClient, matched: tuple[AsyncClient, str]
) -> None:
    mentor, url = matched

    assert (
        await client.post(f"{url}/status", json={"status": "completed"}, headers=csrf(client))
    ).status_code == 403
    assert (await mentor.post(f"{url}/cancel", headers=csrf(mentor))).status_code == 403
    assert (
        await mentor.post(f"{url}/status", json={"status": "in_progress"}, headers=csrf(mentor))
    ).json()["status"] == "in_progress"
    assert (await client.post(f"{url}/cancel", headers=csrf(client))).json()[
        "status"
    ] == "cancelled"


# --- Admin -------------------------------------------------------------------


async def test_admin_panels_are_admin_only(client: AsyncClient, learner: User) -> None:
    for path in ("users", "schools", "mentors", "mentor-requests", "usage", "moderation", "stages"):
        assert (await client.get(f"/api/v1/admin/{path}")).status_code == 403, path


async def test_admin_approves_a_mentor_and_assigns_a_request(
    client: AsyncClient, project: dict[str, Any], db: AsyncSession, app: FastAPI
) -> None:
    request = await ask(client, project)
    mentor = await make_mentor(db, app, approved=False, regions=["Gauteng"])
    admin = await admin_client(db, app)
    waiting = (await admin.get("/api/v1/admin/mentors")).json()
    mentor_id = waiting[0]["user"]["id"]
    assert waiting[0]["profile"]["is_approved"] is False

    early = await admin.post(
        f"/api/v1/admin/mentor-requests/{request['id']}/assign",
        json={"mentor_id": mentor_id},
        headers=csrf(admin),
    )
    assert early.status_code == 403, "an unapproved mentor cannot be assigned"

    approved = await admin.post(
        f"/api/v1/admin/mentors/{mentor_id}/approval", json={"approved": True}, headers=csrf(admin)
    )
    assert approved.json()["profile"]["is_approved"] is True
    assigned = await admin.post(
        f"/api/v1/admin/mentor-requests/{request['id']}/assign",
        json={"mentor_id": mentor_id},
        headers=csrf(admin),
    )
    assert assigned.json()["status"] == "matched"
    assert [r["id"] for r in (await mentor.get("/api/v1/mentor-requests")).json()] == [
        request["id"]
    ]


async def test_admin_searches_users_and_can_deactivate_one(
    client: AsyncClient, learner: User, db: AsyncSession, app: FastAPI
) -> None:
    admin = await admin_client(db, app)

    found = (await admin.get("/api/v1/admin/users", params={"q": "learner@"})).json()
    assert [u["email"] for u in found] == ["learner@example.com"]
    students = (await admin.get("/api/v1/admin/users", params={"role": "student"})).json()
    assert len(students) == 1

    await admin.patch(
        f"/api/v1/admin/users/{found[0]['id']}", json={"is_active": False}, headers=csrf(admin)
    )

    assert (await client.get("/api/v1/users/me")).status_code == 401, "signed out at once"


async def test_an_admin_cannot_lock_themselves_out(db: AsyncSession, app: FastAPI) -> None:
    admin = await admin_client(db, app)
    me = (await admin.get("/api/v1/users/me")).json()

    for change in ({"is_active": False}, {"role": "student"}):
        response = await admin.patch(
            f"/api/v1/admin/users/{me['id']}", json=change, headers=csrf(admin)
        )
        assert (response.status_code, response.json()["code"]) == (400, "cannot_demote_self")


async def test_usage_report_groups_calls_and_cost(
    learner: User, db: AsyncSession, app: FastAPI
) -> None:
    for model, cost in (("big", Decimal("0.5")), ("big", Decimal("0.25")), ("small", None)):
        db.add(
            AIUsage(
                user_id=learner.id,
                provider="acme",
                model=model,
                task="chat",
                input_tokens=100,
                output_tokens=50,
                cost_usd=cost,
            )
        )
    await db.commit()
    admin = await admin_client(db, app)

    by_model = {
        r["label"]: r
        for r in (await admin.get("/api/v1/admin/usage", params={"group_by": "provider"})).json()
    }
    by_user = (await admin.get("/api/v1/admin/usage", params={"group_by": "user"})).json()
    by_day = (await admin.get("/api/v1/admin/usage")).json()

    assert (by_model["acme / big"]["calls"], by_model["acme / big"]["cost_usd"]) == (2, "0.750000")
    assert by_model["acme / small"]["cost_usd"] is None, "unpriced stays unknown, not zero"
    assert (by_user[0]["label"], by_user[0]["calls"], by_user[0]["output_tokens"]) == (
        "learner@example.com",
        3,
        150,
    )
    assert len(by_day) == 1 and by_day[0]["input_tokens"] == 300


async def test_moderation_queue_can_be_reviewed(
    db: AsyncSession, app: FastAPI, learner: User
) -> None:
    db.add(
        ModerationFlag(
            user_id=learner.id, direction="input", categories=["harassment"], content="bad words"
        )
    )
    await db.commit()
    admin = await admin_client(db, app)

    queue = (await admin.get("/api/v1/admin/moderation")).json()
    assert (queue[0]["content"], queue[0]["status"]) == ("bad words", "open")
    await admin.post(f"/api/v1/admin/moderation/{queue[0]['id']}/review", headers=csrf(admin))

    assert (await admin.get("/api/v1/admin/moderation")).json() == []
    assert (
        len((await admin.get("/api/v1/admin/moderation", params={"status": "reviewed"})).json())
        == 1
    )


async def test_editing_a_stage_changes_what_the_mentor_is_told(
    client: AsyncClient,
    project: dict[str, Any],
    db: AsyncSession,
    app: FastAPI,
    fake_ai: FakeProvider,
) -> None:
    admin = await admin_client(db, app)
    stage = (await admin.get("/api/v1/admin/stages")).json()[0]
    original = {
        k: stage[k] for k in ("title", "goal", "deliverables", "exit_criteria", "instructions")
    }

    edited = await admin.put(
        "/api/v1/admin/stages/problem_discovery",
        json={**original, "instructions": "Always ask about the learner's street first."},
        headers=csrf(admin),
    )
    assert edited.json()["version"] == stage["version"] + 1

    await client.post(
        f"/api/v1/conversations/{project['latest_conversation']['id']}/messages",
        json={"text": "Hi"},
        headers=csrf(client),
    )
    assert "Always ask about the learner's street first." in str(fake_ai.calls[0]["system"])

    duplicate = await admin.put(
        "/api/v1/admin/stages/problem_discovery",
        json={**original, "deliverables": [original["deliverables"][0]] * 2},
        headers=csrf(admin),
    )
    assert duplicate.json()["code"] == "duplicate_keys"
    await admin.put("/api/v1/admin/stages/problem_discovery", json=original, headers=csrf(admin))


# --- Usage, credits and expo dates -------------------------------------------


async def test_usage_counts_this_months_replies_against_the_free_tier(
    client: AsyncClient,
    project: dict[str, Any],
    learner: User,
    db: AsyncSession,
    app: FastAPI,
    fake_ai: FakeProvider,
) -> None:
    await client.post(
        f"/api/v1/conversations/{project['latest_conversation']['id']}/messages",
        json={"text": "Hi"},
        headers=csrf(client),
    )

    usage = (await client.get("/api/v1/users/me/usage")).json()
    assert usage == {
        "used_this_month": 1,
        "free_per_month": 200,
        "extra_credits": 0,
        "remaining": 199,
    }

    admin = await admin_client(db, app)
    await admin.post(
        "/api/v1/admin/credits",
        json={"user_id": str(learner.id), "delta": 50, "reason": "Pilot school grant"},
        headers=csrf(admin),
    )
    assert (await client.get("/api/v1/users/me/usage")).json()["remaining"] == 249


async def test_upcoming_expos_are_listed_soonest_first(
    client: AsyncClient, learner: User, db: AsyncSession, app: FastAPI
) -> None:
    admin = await admin_client(db, app)
    today = date.today()
    for name, offset in (("Regional Expo", 40), ("Last year's expo", -30), ("School fair", 10)):
        await admin.post(
            "/api/v1/admin/expo-events",
            json={
                "name": name,
                "starts_on": (today + timedelta(days=offset)).isoformat(),
                "location": "Cape Town",
            },
            headers=csrf(admin),
        )

    upcoming = (await client.get("/api/v1/expo-events")).json()

    assert [event["name"] for event in upcoming] == ["School fair", "Regional Expo"]
