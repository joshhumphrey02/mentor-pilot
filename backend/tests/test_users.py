from datetime import date

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, RefreshToken, School, StudentProfile, User
from app.services.users import age_on
from tests.conftest import PASSWORD, Outbox, csrf, make_client

EMAIL = "thandi@example.com"


def years_ago(years: int) -> str:
    today = date.today()
    return today.replace(year=today.year - years, day=min(today.day, 28)).isoformat()


def onboarding(**overrides: object) -> dict[str, object]:
    return {
        "full_name": "Thandi Mokoena",
        "date_of_birth": years_ago(16),
        "new_school": {"name": "Khayelitsha High", "province": "Western Cape", "town": "Cape Town"},
        "grade": "10",
        "province": "Western Cape",
        "interests": ["robotics", "energy"],
        "learning_style": "hands_on",
        "preferred_language": "en",
        "guardian_consent": True,
        "guardian_email": "parent@example.com",
        **overrides,
    }


async def submit(client: AsyncClient, **overrides: object):  # type: ignore[no-untyped-def]
    return await client.post(
        "/api/v1/users/me/onboarding", json=onboarding(**overrides), headers=csrf(client)
    )


# --- Onboarding --------------------------------------------------------------


async def test_onboarding_saves_the_profile(signed_in: AsyncClient, outbox: Outbox) -> None:
    response = await submit(signed_in)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_onboarded"] is True
    assert body["full_name"] == "Thandi Mokoena"
    profile = body["student_profile"]
    assert profile["school"]["name"] == "Khayelitsha High"
    assert profile["school"]["is_verified"] is False, "learner-added schools await admin review"
    assert profile["interests"] == ["robotics", "energy"]
    assert profile["guardian_consent"] is True


async def test_minor_needs_guardian_consent_and_email(signed_in: AsyncClient) -> None:
    no_consent = await submit(signed_in, guardian_consent=False)
    no_email = await submit(signed_in, guardian_email=None)

    assert no_consent.status_code == no_email.status_code == 400
    assert no_consent.json()["code"] == "guardian_consent_required"
    assert (await signed_in.get("/api/v1/users/me")).json()["is_onboarded"] is False


async def test_guardian_is_told_when_a_minor_joins(signed_in: AsyncClient, outbox: Outbox) -> None:
    await submit(signed_in)

    notice = outbox.last_to("parent@example.com")
    assert "Thandi Mokoena" in notice.subject
    assert "/privacy" in notice.text


async def test_adult_does_not_need_a_guardian_and_none_is_stored(
    signed_in: AsyncClient, outbox: Outbox
) -> None:
    sent_before = len(outbox.messages)

    response = await submit(signed_in, date_of_birth=years_ago(19), guardian_consent=False)

    assert response.status_code == 200
    profile = response.json()["student_profile"]
    assert profile["guardian_email"] is None, "we only keep guardian details for minors"
    assert profile["guardian_consent"] is False
    assert len(outbox.messages) == sent_before


async def test_implausible_date_of_birth_is_rejected(signed_in: AsyncClient) -> None:
    response = await submit(signed_in, date_of_birth=years_ago(3))

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_date_of_birth"


async def test_same_school_typed_differently_is_not_duplicated(
    signed_in: AsyncClient, db: AsyncSession
) -> None:
    await submit(signed_in)
    await submit(signed_in, new_school={"name": "KHAYELITSHA high", "province": "Western Cape"})

    assert len((await db.scalars(select(School))).all()) == 1


async def test_onboarding_with_an_existing_school(signed_in: AsyncClient) -> None:
    created = await signed_in.post(
        "/api/v1/schools",
        json={"name": "Langa Secondary", "province": "Western Cape"},
        headers=csrf(signed_in),
    )
    assert created.status_code == 201

    response = await submit(signed_in, new_school=None, school_id=created.json()["id"])

    assert response.json()["student_profile"]["school"]["name"] == "Langa Secondary"


async def test_onboarding_rejects_both_a_school_id_and_a_new_school(signed_in: AsyncClient) -> None:
    response = await submit(signed_in, school_id="00000000-0000-0000-0000-000000000001")
    assert response.status_code == 422


async def test_onboarding_requires_login(client: AsyncClient) -> None:
    response = await client.post("/api/v1/users/me/onboarding", json=onboarding())
    assert response.status_code == 401


def test_age_counts_birthdays_not_calendar_years() -> None:
    born = date(2010, 6, 15)
    assert age_on(born, date(2028, 6, 14)) == 17
    assert age_on(born, date(2028, 6, 15)) == 18


# --- Schools -----------------------------------------------------------------


async def test_school_search_matches_part_of_the_name(signed_in: AsyncClient) -> None:
    for name in ("Khayelitsha High", "Langa Secondary", "Paarl Boys' High"):
        await signed_in.post(
            "/api/v1/schools",
            json={"name": name, "province": "Western Cape"},
            headers=csrf(signed_in),
        )

    found = await signed_in.get("/api/v1/schools", params={"q": "high"})

    assert [school["name"] for school in found.json()] == ["Khayelitsha High", "Paarl Boys' High"]


async def test_school_search_treats_wildcards_literally(signed_in: AsyncClient) -> None:
    await signed_in.post(
        "/api/v1/schools",
        json={"name": "Langa Secondary", "province": "Western Cape"},
        headers=csrf(signed_in),
    )

    assert (await signed_in.get("/api/v1/schools", params={"q": "%"})).json() == []


async def test_school_search_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/schools")).status_code == 401


# --- POPIA: export and deletion ----------------------------------------------


async def test_export_contains_what_we_hold_and_no_secrets(signed_in: AsyncClient) -> None:
    await submit(signed_in)

    response = await signed_in.get("/api/v1/users/me/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["account"]["email"] == EMAIL
    assert data["student_profile"]["school"]["name"] == "Khayelitsha High"
    assert data["student_profile"]["guardian_email"] == "parent@example.com"
    assert any(event["action"] == "user.onboarded" for event in data["activity"])
    assert "hash" not in response.text.lower()
    assert "google_sub" not in response.text


async def test_deleting_the_account_erases_personal_data(
    signed_in: AsyncClient, db: AsyncSession, app: FastAPI
) -> None:
    await submit(signed_in)

    response = await signed_in.post(
        "/api/v1/users/me/delete",
        json={"confirm": "DELETE", "password": PASSWORD},
        headers=csrf(signed_in),
    )

    assert response.status_code == 204
    assert (await signed_in.get("/api/v1/users/me")).status_code == 401

    user = (await db.scalars(select(User))).one()
    assert EMAIL not in user.email
    assert user.full_name == "Deleted user"
    assert user.password_hash is None
    assert user.deleted_at is not None
    assert (await db.scalars(select(StudentProfile))).all() == []
    assert all(t.revoked_at for t in (await db.scalars(select(RefreshToken))).all())
    assert [a.action for a in (await db.scalars(select(AuditLog))).all()] == [
        "user.account_deleted"
    ]

    login = await make_client(app).post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert login.status_code == 401


async def test_the_email_can_be_registered_again_after_deletion(
    signed_in: AsyncClient, outbox: Outbox, app: FastAPI
) -> None:
    await signed_in.post(
        "/api/v1/users/me/delete",
        json={"confirm": "DELETE", "password": PASSWORD},
        headers=csrf(signed_in),
    )

    response = await make_client(app).post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "full_name": "Thandi", "accept_privacy": True},
    )

    assert response.status_code == 202
    assert "Confirm" in outbox.last_to(EMAIL).subject


async def test_deleting_needs_the_right_password_and_confirmation(signed_in: AsyncClient) -> None:
    wrong_password = await signed_in.post(
        "/api/v1/users/me/delete",
        json={"confirm": "DELETE", "password": "not my password"},
        headers=csrf(signed_in),
    )
    no_confirmation = await signed_in.post(
        "/api/v1/users/me/delete",
        json={"confirm": "yes", "password": PASSWORD},
        headers=csrf(signed_in),
    )

    assert wrong_password.status_code == 403
    assert no_confirmation.status_code == 422
    assert (await signed_in.get("/api/v1/users/me")).status_code == 200
