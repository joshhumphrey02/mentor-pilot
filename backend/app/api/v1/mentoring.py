import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, MailerDep, SessionDep, SettingsDep, require_roles
from app.core.errors import error_responses
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.core.time import utcnow
from app.models import ExpoEvent, User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.mentoring import (
    ExpoEventOut,
    MentorMessageIn,
    MentorMessageOut,
    MentorProfileIn,
    MentorProfileOut,
    MentorRegistration,
    MentorRequestIn,
    MentorRequestOut,
    StatusUpdate,
    UsageOut,
)
from app.services import auth as auth_service
from app.services import email, mentoring
from app.services import projects as project_service

router = APIRouter(tags=["mentoring"], responses=error_responses(401, 403, 404))

MentorUser = Annotated[User, Depends(require_roles(UserRole.MENTOR))]


# --- Mentor accounts -----------------------------------------------------------


@router.post(
    "/mentors/register", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit(AUTH_LIMIT)
async def register_mentor(
    request: Request,
    body: MentorRegistration,
    session: SessionDep,
    settings: SettingsDep,
    mailer: MailerDep,
) -> MessageResponse:
    """Signs up as a mentor. The account must confirm its email and then be
    approved by an admin before it can see any learner's request."""
    user = await mentoring.register_mentor(session, body)
    if user is None:
        existing = await auth_service.get_user_by_email(session, body.email)
        if existing is not None:
            mailer.send_later(
                email.account_exists_email(
                    existing.email, existing.full_name, f"{settings.public_base_url}/login"
                )
            )
    else:
        await auth_service.confirm_or_send_verification(session, settings, mailer, user)
        await session.commit()
    # The same answer either way, so this cannot be used to find accounts.
    return MessageResponse(
        message="If that email address can be used, we've sent a message to it. Check your inbox."
    )


@router.get("/mentors/me", response_model=MentorProfileOut)
async def my_mentor_profile(user: MentorUser, session: SessionDep) -> MentorProfileOut:
    profile = await mentoring.get_profile(session, user)
    await session.commit()
    return MentorProfileOut.model_validate(profile)


@router.put("/mentors/me", response_model=MentorProfileOut)
async def update_my_mentor_profile(
    body: MentorProfileIn, user: MentorUser, session: SessionDep
) -> MentorProfileOut:
    return MentorProfileOut.model_validate(await mentoring.update_profile(session, user, body))


@router.get("/mentors/open-requests", response_model=list[MentorRequestOut])
async def open_requests(user: MentorUser, session: SessionDep) -> list[MentorRequestOut]:
    """Unmatched requests in this mentor's regions that need their expertise."""
    found = await mentoring.open_requests(session, user)
    return [await mentoring.to_out(session, request) for request in found]


# --- Requests ------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/mentor-requests",
    response_model=MentorRequestOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
async def request_a_mentor(
    project_id: uuid.UUID, body: MentorRequestIn, user: CurrentUser, session: SessionDep
) -> MentorRequestOut:
    project = await project_service.get(session, user, project_id)
    created = await mentoring.create_request(
        session, user, project, help_types=list(body.help_types), description=body.description
    )
    return await mentoring.to_out(session, created)


@router.get("/mentor-requests", response_model=list[MentorRequestOut])
async def my_requests(user: CurrentUser, session: SessionDep) -> list[MentorRequestOut]:
    """A learner's requests, or the requests a mentor has taken on."""
    found = await mentoring.requests_for(session, user)
    return [await mentoring.to_out(session, request) for request in found]


@router.get("/mentor-requests/{request_id}", response_model=MentorRequestOut)
async def get_request(
    request_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> MentorRequestOut:
    return await mentoring.to_out(session, await mentoring.get_request(session, user, request_id))


@router.post(
    "/mentor-requests/{request_id}/accept",
    response_model=MentorRequestOut,
    responses=error_responses(409),
)
async def accept_request(
    request_id: uuid.UUID, user: MentorUser, session: SessionDep
) -> MentorRequestOut:
    return await mentoring.to_out(session, await mentoring.accept(session, user, request_id))


@router.post("/mentor-requests/{request_id}/status", response_model=MentorRequestOut)
async def update_status(
    request_id: uuid.UUID, body: StatusUpdate, user: CurrentUser, session: SessionDep
) -> MentorRequestOut:
    found = await mentoring.get_request(session, user, request_id)
    return await mentoring.to_out(
        session, await mentoring.set_status(session, user, found, body.status)
    )


@router.post("/mentor-requests/{request_id}/cancel", response_model=MentorRequestOut)
async def cancel_request(
    request_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> MentorRequestOut:
    found = await mentoring.get_request(session, user, request_id)
    return await mentoring.to_out(session, await mentoring.cancel(session, user, found))


@router.get("/mentor-requests/{request_id}/messages", response_model=list[MentorMessageOut])
async def list_thread_messages(
    request_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[MentorMessageOut]:
    found = await mentoring.get_request(session, user, request_id)
    return await mentoring.list_messages(session, user, found)


@router.post(
    "/mentor-requests/{request_id}/messages",
    response_model=MentorMessageOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400),
)
@limiter.limit("60/hour")
async def send_thread_message(
    request: Request,
    request_id: uuid.UUID,
    body: MentorMessageIn,
    user: CurrentUser,
    session: SessionDep,
) -> MentorMessageOut:
    """A message between learner and mentor. No AI takes part, but every
    message is moderated, and contact details are refused."""
    found = await mentoring.get_request(session, user, request_id)
    message = await mentoring.send_message(session, request.app.state.ai, user, found, body.text)
    return MentorMessageOut(
        id=message.id,
        sender=mentoring.person(user),
        mine=True,
        text=message.text,
        created_at=message.created_at,
    )


# --- Usage and expo dates --------------------------------------------------------


@router.get("/users/me/usage", response_model=UsageOut)
async def my_usage(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> UsageOut:
    return await mentoring.usage_for(session, settings, user)


@router.get("/expo-events", response_model=list[ExpoEventOut])
async def upcoming_expos(_user: CurrentUser, session: SessionDep) -> list[ExpoEventOut]:
    events = await session.scalars(
        select(ExpoEvent)
        .where(ExpoEvent.starts_on >= utcnow().date())
        .order_by(ExpoEvent.starts_on)
        .limit(5)
    )
    return [ExpoEventOut.model_validate(event) for event in events]
