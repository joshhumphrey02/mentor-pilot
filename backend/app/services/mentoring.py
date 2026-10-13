"""Human mentor handoff: requests, matching and messaging."""

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import AIService
from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.core.time import utcnow
from app.models import (
    AIUsage,
    CreditLedger,
    MentorMessage,
    MentorProfile,
    MentorRequest,
    ModerationFlag,
    Project,
    RequestStatus,
    User,
    UserRole,
)
from app.schemas.mentoring import (
    MentorMessageOut,
    MentorProfileIn,
    MentorRegistration,
    MentorRequestOut,
    Person,
    UsageOut,
)
from app.services import audit, pathway
from app.services.auth import get_user_by_email, normalise_email

OPEN = (RequestStatus.PENDING.value,)
ACTIVE = (RequestStatus.MATCHED.value, RequestStatus.IN_PROGRESS.value)

# Mentors and learners talk on the platform, where it can be supervised.
# Anything that looks like a way to move the conversation elsewhere is refused.
_CONTACT_DETAILS = re.compile(
    r"(\+?\d[\d\s().-]{7,}\d)"  # phone numbers
    r"|([\w.+-]+@[\w-]+\.[\w.-]+)"  # email addresses
    r"|(https?://|www\.)"  # links
    r"|(\b(whatsapp|telegram|instagram|insta|snapchat|tiktok|facebook|discord|signal)\b)"
    r"|(@[A-Za-z0-9_.]{3,})",  # social handles
    re.IGNORECASE,
)


def first_name(user: User | None) -> str:
    return (user.full_name.split() or ["Someone"])[0] if user else "Someone"


def person(user: User | None) -> Person | None:
    return Person(id=user.id, first_name=first_name(user)) if user else None


# --- Mentor accounts -----------------------------------------------------------


async def register_mentor(session: AsyncSession, data: MentorRegistration) -> User | None:
    """Creates an unverified, unapproved mentor. Returns None if the email is taken."""
    password_hash = await hash_password(data.password)
    if await get_user_by_email(session, data.email) is not None:
        return None
    user = User(
        email=normalise_email(data.email),
        password_hash=password_hash,
        full_name=data.full_name,
        role=UserRole.MENTOR.value,
        privacy_accepted_at=utcnow(),
        # Mentors have no learner onboarding; their profile is their onboarding.
        onboarded_at=utcnow(),
        student_profile=None,
    )
    session.add(user)
    await session.flush()
    session.add(MentorProfile(user_id=user.id, **_profile_fields(data)))
    audit.record(session, "mentor.registered", user_id=user.id)
    return user


def _profile_fields(data: MentorProfileIn) -> dict[str, Any]:
    return {
        "organisation": data.organisation,
        "bio": data.bio,
        "expertise": list(dict.fromkeys(data.expertise)),
        "regions": list(dict.fromkeys(data.regions)),
        "availability": data.availability,
        "offers": data.offers,
    }


async def get_profile(session: AsyncSession, user: User) -> MentorProfile:
    profile: MentorProfile | None = await session.scalar(
        select(MentorProfile).where(MentorProfile.user_id == user.id)
    )
    if profile is None:
        profile = MentorProfile(user_id=user.id)
        session.add(profile)
        await session.flush()
    return profile


async def update_profile(session: AsyncSession, user: User, data: MentorProfileIn) -> MentorProfile:
    profile = await get_profile(session, user)
    for name, value in _profile_fields(data).items():
        setattr(profile, name, value)
    await session.commit()
    return profile


async def require_approved(session: AsyncSession, user: User) -> MentorProfile:
    profile = await get_profile(session, user)
    if not profile.is_approved:
        raise PermissionDeniedError(
            "Your mentor profile is waiting for approval. We'll email you when it is approved.",
            code="mentor_not_approved",
        )
    return profile


# --- Requests ------------------------------------------------------------------


async def create_request(
    session: AsyncSession,
    learner: User,
    project: Project,
    *,
    help_types: list[str],
    description: str,
) -> MentorRequest:
    existing = await session.scalar(
        select(MentorRequest).where(
            MentorRequest.project_id == project.id,
            MentorRequest.status.in_([*OPEN, *ACTIVE]),
        )
    )
    if existing is not None:
        raise ConflictError(
            "You already have a mentor request open for this project.", code="request_exists"
        )
    stages = await pathway.progress(session, project)
    here = pathway.current(stages, project)
    profile = learner.student_profile
    idea = project.idea or {}
    request = MentorRequest(
        project_id=project.id,
        learner_id=learner.id,
        stage_key=project.current_stage,
        help_types=list(dict.fromkeys(help_types)),
        description=description,
        province=(profile.province if profile else "") or "",
        school_name=profile.school.name if profile and profile.school else "",
        snapshot={
            "title": project.title,
            "stage": here.definition.title,
            "grade": profile.grade if profile else None,
            "idea": {
                key: idea.get(key)
                for key in ("title", "problem", "field", "materials", "safety_level", "safety_note")
                if idea.get(key)
            },
            "summary": project.memory,
        },
    )
    session.add(request)
    audit.record(session, "mentor_request.created", user_id=learner.id)
    await session.commit()
    return request


async def to_out(session: AsyncSession, request: MentorRequest) -> MentorRequestOut:
    project = await session.get(Project, request.project_id)
    learner = await session.get(User, request.learner_id)
    mentor = await session.get(User, request.mentor_id) if request.mentor_id else None
    return MentorRequestOut(
        id=request.id,
        project_id=request.project_id,
        project_title=project.title if project else "",
        status=request.status,
        stage_key=request.stage_key,
        help_types=request.help_types,
        description=request.description,
        province=request.province,
        school_name=request.school_name,
        snapshot=request.snapshot,
        learner=person(learner) or Person(id=request.learner_id, first_name="A learner"),
        mentor=person(mentor),
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


async def requests_for(session: AsyncSession, user: User) -> list[MentorRequest]:
    """A learner's own requests, or the ones a mentor has taken on."""
    column = (
        MentorRequest.mentor_id if user.role == UserRole.MENTOR.value else MentorRequest.learner_id
    )
    return list(
        await session.scalars(
            select(MentorRequest).where(column == user.id).order_by(MentorRequest.created_at.desc())
        )
    )


async def open_requests(session: AsyncSession, mentor: User) -> list[MentorRequest]:
    """Unmatched requests this mentor could help with: their region, their expertise."""
    profile = await require_approved(session, mentor)
    pending = await session.scalars(
        select(MentorRequest)
        .where(MentorRequest.status == RequestStatus.PENDING.value)
        .order_by(MentorRequest.created_at)
    )
    return [
        request
        for request in pending
        if (not request.province or request.province in profile.regions)
        and set(request.help_types) & set(profile.expertise)
    ]


async def get_request(session: AsyncSession, user: User, request_id: uuid.UUID) -> MentorRequest:
    """A request the user is party to. Admins may see any."""
    request = await session.get(MentorRequest, request_id)
    allowed = request is not None and (
        user.role == UserRole.ADMIN.value or user.id in (request.learner_id, request.mentor_id)
    )
    if request is None or not allowed:
        raise NotFoundError("We couldn't find that request.", code="request_not_found")
    return request


async def accept(session: AsyncSession, mentor: User, request_id: uuid.UUID) -> MentorRequest:
    await require_approved(session, mentor)
    # Locked so two mentors accepting at the same moment cannot both win.
    request = await session.scalar(
        select(MentorRequest).where(MentorRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise NotFoundError("We couldn't find that request.", code="request_not_found")
    if request.status != RequestStatus.PENDING.value:
        raise ConflictError(
            "Another mentor has already taken this request.", code="already_matched"
        )
    request.mentor_id = mentor.id
    request.status = RequestStatus.MATCHED.value
    audit.record(session, "mentor_request.accepted", user_id=mentor.id)
    await session.commit()
    await session.refresh(request)
    return request


async def assign(session: AsyncSession, request: MentorRequest, mentor: User) -> MentorRequest:
    """An admin matches a request by hand."""
    if mentor.role != UserRole.MENTOR.value:
        raise AppError("That user is not a mentor.", code="not_a_mentor")
    await require_approved(session, mentor)
    request.mentor_id = mentor.id
    if request.status == RequestStatus.PENDING.value:
        request.status = RequestStatus.MATCHED.value
    await session.commit()
    await session.refresh(request)
    return request


async def set_status(
    session: AsyncSession, user: User, request: MentorRequest, status: str
) -> MentorRequest:
    if user.id != request.mentor_id and user.role != UserRole.ADMIN.value:
        raise PermissionDeniedError("Only the mentor on this request can update it.")
    request.status = status
    await session.commit()
    await session.refresh(request)
    return request


async def cancel(session: AsyncSession, learner: User, request: MentorRequest) -> MentorRequest:
    if learner.id != request.learner_id:
        raise PermissionDeniedError("Only the learner who made this request can cancel it.")
    if request.status in (RequestStatus.COMPLETED.value, RequestStatus.CANCELLED.value):
        raise AppError("This request is already closed.", code="request_closed")
    request.status = RequestStatus.CANCELLED.value
    await session.commit()
    await session.refresh(request)
    return request


# --- Messages ------------------------------------------------------------------


async def list_messages(
    session: AsyncSession, user: User, request: MentorRequest
) -> list[MentorMessageOut]:
    rows = (
        await session.execute(
            select(MentorMessage, User)
            .outerjoin(User, User.id == MentorMessage.sender_id)
            .where(MentorMessage.request_id == request.id)
            .order_by(MentorMessage.created_at)
        )
    ).all()
    return [
        MentorMessageOut(
            id=message.id,
            sender=person(sender),
            mine=message.sender_id == user.id,
            text=message.text,
            created_at=message.created_at,
        )
        for message, sender in rows
    ]


async def send_message(
    session: AsyncSession, ai: AIService, user: User, request: MentorRequest, text: str
) -> MentorMessage:
    if user.id not in (request.learner_id, request.mentor_id):
        raise PermissionDeniedError("You are not part of this conversation.")
    if request.mentor_id is None or request.status not in ACTIVE:
        raise AppError(
            "Messages open once a mentor has accepted, and close when the request is finished.",
            code="thread_closed",
        )
    if _CONTACT_DETAILS.search(text):
        raise AppError(
            "For everyone's safety, phone numbers, email addresses, links and social media "
            "names can't be shared here. Arrange meetings through your school or teacher.",
            code="contact_details_not_allowed",
        )
    verdict = await ai.moderate(text)
    if ai.blocks(verdict):
        session.add(
            ModerationFlag(
                user_id=user.id,
                direction="mentor_chat",
                categories=verdict.categories,
                checked=verdict.checked,
                content=text,
            )
        )
        await session.commit()
        raise AppError(
            "That message couldn't be sent. Please keep the conversation about the project."
            if verdict.checked
            else "We couldn't check that message just now. Please try again in a moment.",
            code="message_blocked" if verdict.checked else "moderation_unavailable",
        )
    message = MentorMessage(request_id=request.id, sender_id=user.id, text=text)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


# --- Usage and credits ---------------------------------------------------------


async def usage_for(session: AsyncSession, settings: Settings, user: User) -> UsageOut:
    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = int(
        await session.scalar(
            select(func.count())
            .select_from(AIUsage)
            .where(
                AIUsage.user_id == user.id,
                AIUsage.task == "chat",
                AIUsage.success.is_(True),
                AIUsage.created_at >= month_start,
            )
        )
        or 0
    )
    school_id = user.student_profile.school_id if user.student_profile else None
    owners = [CreditLedger.user_id == user.id]
    if school_id is not None:
        owners.append(CreditLedger.school_id == school_id)
    extra = int(
        await session.scalar(
            select(func.coalesce(func.sum(CreditLedger.delta), 0)).where(or_(*owners))
        )
        or 0
    )
    free = settings.free_turns_per_month
    return UsageOut(
        used_this_month=used,
        free_per_month=free,
        extra_credits=max(extra, 0),
        remaining=max(free + max(extra, 0) - used, 0),
    )
