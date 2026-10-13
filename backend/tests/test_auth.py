from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.config import Settings
from app.core.errors import PermissionDeniedError
from app.core.rate_limit import limiter
from app.core.security import new_csrf_token
from app.core.time import utcnow
from app.models import AuditLog, EmailToken, RefreshToken, User, UserRole
from tests.conftest import PASSWORD, Outbox, csrf, make_client, register_and_verify

EMAIL = "thandi@example.com"
REGISTRATION = {
    "email": EMAIL,
    "password": PASSWORD,
    "full_name": "Thandi M",
    "accept_privacy": True,
}


async def login(client: AsyncClient, password: str = PASSWORD, email: str = EMAIL) -> int:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.status_code


# --- Registration and email verification ------------------------------------


async def test_register_verify_then_access_account(client: AsyncClient, outbox: Outbox) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTRATION)
    assert response.status_code == 202
    assert "mp_access" not in client.cookies, "registering alone must not sign you in"

    response = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"

    response = await client.post(
        "/api/v1/auth/verify-email", json={"token": outbox.token_for(EMAIL)}
    )
    assert response.status_code == 200
    assert response.json()["is_verified"] is True
    assert response.json()["is_onboarded"] is False

    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL
    assert me.json()["role"] == "student"


async def test_auth_cookies_are_httponly_and_refresh_is_path_scoped(
    client: AsyncClient, outbox: Outbox
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    response = await client.post(
        "/api/v1/auth/verify-email", json={"token": outbox.token_for(EMAIL)}
    )

    cookies = {c.split("=", 1)[0]: c.lower() for c in response.headers.get_list("set-cookie")}
    assert "httponly" in cookies["mp_access"]
    assert "samesite=lax" in cookies["mp_access"]
    assert "httponly" in cookies["mp_refresh"]
    assert "path=/api/v1/auth" in cookies["mp_refresh"]
    assert "httponly" not in cookies["mp_csrf"], "the frontend must be able to read the CSRF token"


async def test_email_is_case_insensitive(client: AsyncClient, outbox: Outbox, app: FastAPI) -> None:
    await client.post("/api/v1/auth/register", json={**REGISTRATION, "email": "Thandi@Example.com"})
    await client.post("/api/v1/auth/verify-email", json={"token": outbox.token_for(EMAIL)})

    assert await login(make_client(app), email="THANDI@example.com") == 200


async def test_registering_an_existing_email_does_not_reveal_it(
    client: AsyncClient, outbox: Outbox, db: AsyncSession, app: FastAPI
) -> None:
    await register_and_verify(client, outbox)
    sent_before = len(outbox.messages)

    response = await make_client(app).post(
        "/api/v1/auth/register", json={**REGISTRATION, "password": "a different password"}
    )

    assert response.status_code == 202, "same response as for a brand new address"
    assert len(outbox.messages) == sent_before + 1
    assert "already have" in outbox.last_to(EMAIL).subject
    assert len((await db.scalars(select(User))).all()) == 1
    assert await login(make_client(app), "a different password") == 401, "password is unchanged"


async def test_registration_requires_accepting_the_privacy_notice(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTRATION, "accept_privacy": False}
    )
    assert response.status_code == 422


async def test_short_password_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTRATION, "password": "short"}
    )
    assert response.status_code == 422


async def test_verification_link_works_only_once(
    client: AsyncClient, outbox: Outbox, app: FastAPI
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    token = outbox.token_for(EMAIL)

    assert (
        await client.post("/api/v1/auth/verify-email", json={"token": token})
    ).status_code == 200
    again = await make_client(app).post("/api/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["code"] == "invalid_token"


async def test_expired_verification_link_is_rejected(
    client: AsyncClient, outbox: Outbox, db: AsyncSession
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    await db.execute(update(EmailToken).values(expires_at=utcnow() - timedelta(minutes=1)))
    await db.commit()

    response = await client.post(
        "/api/v1/auth/verify-email", json={"token": outbox.token_for(EMAIL)}
    )
    assert response.status_code == 400


async def test_resending_verification_retires_the_previous_link(
    client: AsyncClient, outbox: Outbox
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    first = outbox.token_for(EMAIL)
    await client.post("/api/v1/auth/resend-verification", json={"email": EMAIL})
    second = outbox.token_for(EMAIL)

    assert first != second
    assert (
        await client.post("/api/v1/auth/verify-email", json={"token": first})
    ).status_code == 400
    assert (
        await client.post("/api/v1/auth/verify-email", json={"token": second})
    ).status_code == 200


# --- With no email server -----------------------------------------------------


@pytest.fixture
def no_email_server(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default for an install with no SMTP host: nothing to send links with."""
    monkeypatch.setattr(settings, "email_verification", None)


def test_verification_follows_whether_there_is_an_email_server() -> None:
    assert Settings(smtp_host=None, email_verification=None).email_verification_enabled is False
    assert Settings(smtp_host="smtp.example.com").email_verification_enabled is True
    assert Settings(smtp_host=None, email_verification=True).email_verification_enabled is True


@pytest.mark.usefixtures("no_email_server")
async def test_without_an_email_server_a_new_account_can_log_in_at_once(
    client: AsyncClient, outbox: Outbox
) -> None:
    providers = await client.get("/api/v1/auth/providers")
    assert providers.json()["email_verification"] is False

    response = await client.post("/api/v1/auth/register", json=REGISTRATION)
    assert response.status_code == 202
    assert "mp_access" not in client.cookies, "registering alone must not sign you in"
    assert outbox.messages == [], "no link is sent that could never arrive"

    assert await login(client) == 200
    me = await client.get("/api/v1/users/me")
    assert me.json()["is_verified"] is True


@pytest.mark.usefixtures("no_email_server")
async def test_without_an_email_server_an_account_awaiting_a_link_is_let_in(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_verification", True)
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    assert await login(client) == 403

    monkeypatch.setattr(settings, "email_verification", None)
    assert await login(client, password="not the password") == 401, "still needs the password"
    assert await login(client) == 200


# --- Login and lockout -------------------------------------------------------


async def test_wrong_password_and_unknown_email_look_the_same(
    client: AsyncClient, outbox: Outbox, app: FastAPI
) -> None:
    await register_and_verify(client, outbox)
    fresh = make_client(app)

    wrong = await fresh.post("/api/v1/auth/login", json={"email": EMAIL, "password": "nope-nope"})
    unknown = await fresh.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "nope-nope"}
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_account_locks_after_repeated_failures(
    client: AsyncClient, outbox: Outbox, app: FastAPI, settings: Settings, db: AsyncSession
) -> None:
    await register_and_verify(client, outbox)
    fresh = make_client(app)

    for _ in range(settings.max_failed_logins):
        assert await login(fresh, "wrong-password") == 401

    response = await fresh.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 423, "even the right password is refused while locked"
    assert response.json()["code"] == "account_locked"

    await db.execute(update(User).values(locked_until=utcnow() - timedelta(seconds=1)))
    await db.commit()
    assert await login(fresh) == 200, "the lock lifts by itself"


async def test_successful_login_resets_the_failure_count(
    client: AsyncClient, outbox: Outbox, app: FastAPI, settings: Settings
) -> None:
    await register_and_verify(client, outbox)
    fresh = make_client(app)

    for _ in range(settings.max_failed_logins - 1):
        await login(fresh, "wrong-password")
    assert await login(fresh) == 200
    for _ in range(settings.max_failed_logins - 1):
        assert await login(make_client(app), "wrong-password") == 401
    assert await login(make_client(app)) == 200


# --- Refresh token rotation --------------------------------------------------


async def refresh_with(app: FastAPI, refresh_token: str) -> Response:
    """Presents a specific refresh token from another browser.

    Models the worst case: a thief who copied the whole cookie jar, so the
    request also carries a valid CSRF pair.
    """
    token = new_csrf_token(app.state.settings)
    async with make_client(app) as other:
        return await other.post(
            "/api/v1/auth/refresh",
            headers={
                "cookie": f"mp_refresh={refresh_token}; mp_csrf={token}",
                "x-csrf-token": token,
            },
        )


async def test_refresh_rotates_the_token(signed_in: AsyncClient) -> None:
    before = signed_in.cookies.get("mp_refresh")

    response = await signed_in.post("/api/v1/auth/refresh", headers=csrf(signed_in))

    assert response.status_code == 200
    assert signed_in.cookies.get("mp_refresh") != before
    assert (await signed_in.get("/api/v1/users/me")).status_code == 200


async def test_reusing_a_rotated_token_revokes_the_whole_family(
    signed_in: AsyncClient,
    app: FastAPI,
    settings: Settings,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "refresh_reuse_grace_seconds", 0)
    stolen = signed_in.cookies.get("mp_refresh")
    assert stolen
    assert (
        await signed_in.post("/api/v1/auth/refresh", headers=csrf(signed_in))
    ).status_code == 200
    current = signed_in.cookies.get("mp_refresh")
    assert current

    assert (await refresh_with(app, stolen)).status_code == 401, "the replayed token is refused"
    assert (await refresh_with(app, current)).status_code == 401, (
        "and the legitimate session is ended too"
    )

    tokens = (await db.scalars(select(RefreshToken))).all()
    assert tokens and all(token.revoked_at is not None for token in tokens)
    actions = (await db.scalars(select(AuditLog.action))).all()
    assert "auth.refresh_reuse_detected" in actions


async def test_simultaneous_refresh_from_two_tabs_is_not_treated_as_theft(
    signed_in: AsyncClient, app: FastAPI
) -> None:
    shared = signed_in.cookies.get("mp_refresh")
    assert shared
    assert (
        await signed_in.post("/api/v1/auth/refresh", headers=csrf(signed_in))
    ).status_code == 200

    assert (await refresh_with(app, shared)).status_code == 409, "the losing tab is told to retry"
    again = await signed_in.post("/api/v1/auth/refresh", headers=csrf(signed_in))
    assert again.status_code == 200, "the session survives"


async def test_refresh_tokens_are_stored_hashed(signed_in: AsyncClient, db: AsyncSession) -> None:
    raw = signed_in.cookies.get("mp_refresh")
    stored = (await db.scalars(select(RefreshToken.token_hash))).all()

    assert raw not in stored
    assert all(len(value) == 64 for value in stored)


async def test_refresh_without_a_cookie_is_401(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_failed_refresh_clears_the_dead_cookies(app: FastAPI) -> None:
    response = await refresh_with(app, "not-a-real-token")

    assert response.status_code == 401
    cleared = " ".join(response.headers.get_list("set-cookie"))
    assert 'mp_access=""' in cleared and 'mp_refresh=""' in cleared


async def test_logout_ends_the_session(signed_in: AsyncClient, app: FastAPI) -> None:
    refresh_token = signed_in.cookies.get("mp_refresh")
    assert refresh_token

    response = await signed_in.post("/api/v1/auth/logout", headers=csrf(signed_in))

    assert response.status_code == 204
    assert "mp_access" not in signed_in.cookies
    assert (await signed_in.get("/api/v1/users/me")).status_code == 401
    assert (await refresh_with(app, refresh_token)).status_code == 401, (
        "the token is revoked server-side"
    )


# --- CSRF --------------------------------------------------------------------


async def test_cookie_authenticated_writes_need_the_csrf_header(signed_in: AsyncClient) -> None:
    missing = await signed_in.patch("/api/v1/users/me", json={"full_name": "New Name"})
    assert missing.status_code == 403
    assert missing.json()["code"] == "csrf_failed"

    forged = await signed_in.patch(
        "/api/v1/users/me", json={"full_name": "New Name"}, headers={"x-csrf-token": "guess.guess"}
    )
    assert forged.status_code == 403

    ok = await signed_in.patch(
        "/api/v1/users/me", json={"full_name": "New Name"}, headers=csrf(signed_in)
    )
    assert ok.status_code == 200
    assert ok.json()["full_name"] == "New Name"


async def test_csrf_token_must_be_signed_by_us(signed_in: AsyncClient) -> None:
    """An attacker who can plant a matching cookie and header still fails."""
    planted = "attacker-nonce.attacker-signature"
    access = signed_in.cookies.get("mp_access")

    response = await signed_in.patch(
        "/api/v1/users/me",
        json={"full_name": "Hacked"},
        headers={"cookie": f"mp_access={access}; mp_csrf={planted}", "x-csrf-token": planted},
    )
    assert response.status_code == 403


# --- Password reset ----------------------------------------------------------


async def test_password_reset_flow(client: AsyncClient, outbox: Outbox, app: FastAPI) -> None:
    await register_and_verify(client, outbox)
    old_refresh = client.cookies.get("mp_refresh")
    assert old_refresh
    visitor = make_client(app)

    assert (
        await visitor.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
    ).status_code == 202
    token = outbox.token_for(EMAIL)
    new_password = "a brand new passphrase"

    response = await visitor.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": new_password}
    )
    assert response.status_code == 200

    assert await login(make_client(app), PASSWORD) == 401, "the old password stops working"
    assert await login(make_client(app), new_password) == 200
    assert (await refresh_with(app, old_refresh)).status_code == 401, (
        "sessions from before the reset are ended"
    )

    replay = await visitor.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "yet another one"}
    )
    assert replay.status_code == 400, "the link works only once"


async def test_forgot_password_for_unknown_email_sends_nothing(
    client: AsyncClient, outbox: Outbox
) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
    )

    assert response.status_code == 202
    assert outbox.messages == []


async def test_a_reset_token_cannot_verify_an_email(client: AsyncClient, outbox: Outbox) -> None:
    """Tokens are bound to their purpose."""
    await register_and_verify(client, outbox)
    await client.post("/api/v1/auth/forgot-password", json={"email": EMAIL}, headers=csrf(client))

    response = await client.post(
        "/api/v1/auth/verify-email", json={"token": outbox.token_for(EMAIL)}, headers=csrf(client)
    )
    assert response.status_code == 400


# --- Google sign-in ----------------------------------------------------------


class FakeGoogle:
    def __init__(self, *, email: str = EMAIL, verified: bool = True) -> None:
        from app.services.google_oauth import GoogleProfile

        self.profile = GoogleProfile(
            sub="google-sub-1", email=email, email_verified=verified, name="Thandi M"
        )
        self.seen_verifier: str | None = None

    def authorization_request(self, redirect_uri: str):  # type: ignore[no-untyped-def]
        from app.services.google_oauth import AuthorizationRequest

        return AuthorizationRequest(
            f"https://accounts.google.test/auth?redirect_uri={redirect_uri}",
            "state-123",
            "verifier-abc",
        )

    async def fetch_profile(self, *, code: str, code_verifier: str, redirect_uri: str):  # type: ignore[no-untyped-def]
        self.seen_verifier = code_verifier
        return self.profile


@pytest.fixture
def google(app: FastAPI) -> FakeGoogle:
    fake = FakeGoogle()
    app.state.google_oauth = fake
    return fake


async def test_google_sign_in_creates_a_verified_account(
    client: AsyncClient, google: FakeGoogle, db: AsyncSession
) -> None:
    start = await client.get("/api/v1/auth/google/login")
    assert start.status_code == 303
    assert start.headers["location"].startswith("https://accounts.google.test/auth")

    callback = await client.get("/api/v1/auth/google/callback?code=abc&state=state-123")

    assert callback.status_code == 303
    assert callback.headers["location"] == "http://test/app"
    assert google.seen_verifier == "verifier-abc", "the PKCE verifier survives the round trip"
    me = (await client.get("/api/v1/users/me")).json()
    assert me["email"] == EMAIL
    assert me["is_verified"] is True
    assert me["has_password"] is False


async def test_google_callback_with_wrong_state_is_rejected(
    client: AsyncClient, google: FakeGoogle
) -> None:
    await client.get("/api/v1/auth/google/login")

    callback = await client.get("/api/v1/auth/google/callback?code=abc&state=forged")

    assert callback.status_code == 303
    assert callback.headers["location"] == "http://test/login?error=google_failed"
    assert "mp_access" not in client.cookies


async def test_google_callback_without_starting_the_flow_is_rejected(
    client: AsyncClient, google: FakeGoogle
) -> None:
    callback = await client.get("/api/v1/auth/google/callback?code=abc&state=state-123")

    assert callback.headers["location"] == "http://test/login?error=google_failed"


async def test_google_links_to_an_existing_password_account(
    client: AsyncClient, outbox: Outbox, google: FakeGoogle, app: FastAPI, db: AsyncSession
) -> None:
    await register_and_verify(client, outbox)
    browser = make_client(app)

    await browser.get("/api/v1/auth/google/login")
    await browser.get("/api/v1/auth/google/callback?code=abc&state=state-123")

    users = (await db.scalars(select(User))).all()
    assert len(users) == 1
    assert users[0].google_sub == "google-sub-1"
    assert users[0].has_password, "the password still works too"


async def test_unverified_google_email_is_refused(client: AsyncClient, app: FastAPI) -> None:
    app.state.google_oauth = FakeGoogle(verified=False)
    await client.get("/api/v1/auth/google/login")

    callback = await client.get("/api/v1/auth/google/callback?code=abc&state=state-123")

    assert callback.headers["location"] == "http://test/login?error=google_failed"


async def test_providers_endpoint_reports_google(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/providers")).json()["google"] is True


# --- Roles and rate limits ---------------------------------------------------


async def test_require_roles_allows_and_denies() -> None:
    admin_only = require_roles(UserRole.ADMIN)
    admin = User(email="a@example.com", role=UserRole.ADMIN.value)
    student = User(email="s@example.com", role=UserRole.STUDENT.value)

    assert await admin_only(admin) is admin
    with pytest.raises(PermissionDeniedError):
        await admin_only(student)


async def test_auth_endpoints_are_rate_limited(client: AsyncClient) -> None:
    limiter.enabled = True

    statuses = [await login(client, "wrong-password", "nobody@example.com") for _ in range(12)]

    assert statuses[0] == 401
    assert statuses[-1] == 429
