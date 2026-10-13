import asyncio
import uuid
from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request
from sqlalchemy import String, cast, func, or_, select

from app.ai.providers.base import ProviderError
from app.ai.registry import ProviderStatus
from app.ai.service import AIService, UsageContext
from app.ai.types import ChatMessage
from app.api.deps import AdminUser, SessionDep
from app.core.errors import AppError, NotFoundError, error_responses
from app.core.time import utcnow
from app.models import (
    AIUsage,
    CreditLedger,
    ExpoEvent,
    MentorProfile,
    MentorRequest,
    ModerationFlag,
    School,
    StageDefinition,
    StudentProfile,
    User,
    UserRole,
)
from app.schemas.admin import (
    AdminMentorOut,
    AdminSchoolOut,
    AdminSchoolUpdate,
    AdminUserOut,
    AdminUserUpdate,
    ApproveMentor,
    AssignMentor,
    CreditGrant,
    FlagOut,
    ProviderStatusOut,
    Role,
    StageDefinitionOut,
    StageDefinitionUpdate,
    TestChatRequest,
    TestChatResponse,
    UsageRow,
)
from app.schemas.common import MessageResponse
from app.schemas.mentoring import ExpoEventIn, ExpoEventOut, MentorProfileOut, MentorRequestOut
from app.services import audit, mentoring, pathway, sessions

router = APIRouter(prefix="/admin", tags=["admin"], responses=error_responses(401, 403))


def get_ai(request: Request) -> AIService:
    service: AIService = request.app.state.ai
    return service


async def _check(ai: AIService, status: ProviderStatus) -> ProviderStatusOut:
    out = ProviderStatusOut(
        name=status.name,
        active=status.active,
        configured=status.configured,
        model=status.model,
        fast_model=status.fast_model,
    )
    if not status.configured:
        out.healthy, out.detail = False, "No API key set."
        return out
    try:
        # The model id is only checked for the active provider: AI_MODEL
        # belongs to whichever vendor AI_PROVIDER names.
        out.detail = await ai.registry.get(status.name).check(status.model)
        out.healthy = True
    except ProviderError as exc:
        out.healthy, out.detail = False, f"{exc} ({exc.code})"
    return out


@router.get("/ai/providers", response_model=list[ProviderStatusOut])
async def ai_providers(
    request: Request,
    _admin: AdminUser,
    check: Annotated[bool, Query(description="Also call each provider to verify it.")] = False,
) -> list[ProviderStatusOut]:
    """Which AI providers have keys, which one is active, and (optionally) whether each works."""
    ai = get_ai(request)
    statuses = ai.registry.statuses()
    if check:
        return list(await asyncio.gather(*(_check(ai, status) for status in statuses)))
    return [
        ProviderStatusOut(
            name=s.name,
            active=s.active,
            configured=s.configured,
            model=s.model,
            fast_model=s.fast_model,
        )
        for s in statuses
    ]


@router.post("/ai/test-chat", response_model=TestChatResponse)
async def ai_test_chat(
    request: Request, body: TestChatRequest, admin: AdminUser
) -> TestChatResponse:
    """Sends one message through the active provider, end to end.

    The quickest way to confirm a provider switch worked: change AI_PROVIDER,
    restart, call this.
    """
    ai = get_ai(request)
    result = await ai.complete(
        messages=[ChatMessage(role="user", text=body.message)],
        system="You are a friendly assistant. Keep replies short.",
        task=body.task,
        max_tokens=1024,
        context=UsageContext(user_id=admin.id),
    )
    return TestChatResponse(
        provider=ai.registry.active_name,
        model=ai.model_for(body.task),
        ok=result.error is None,
        text=result.text,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cost_usd=result.usage.cost_usd,
        error=result.error.code if result.error else None,
    )


# --- People --------------------------------------------------------------------


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    _admin: AdminUser,
    session: SessionDep,
    q: Annotated[str, Query(max_length=100)] = "",
    role: Annotated[Role | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminUserOut]:
    statement = select(User).where(User.deleted_at.is_(None))
    if q.strip():
        pattern = _like(q.strip())
        statement = statement.where(
            or_(User.email.ilike(pattern, escape="\\"), User.full_name.ilike(pattern, escape="\\"))
        )
    if role:
        statement = statement.where(User.role == role)
    rows = await session.scalars(
        statement.order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return [AdminUserOut.model_validate(row) for row in rows]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: uuid.UUID, body: AdminUserUpdate, admin: AdminUser, session: SessionDep
) -> AdminUserOut:
    target = await session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise NotFoundError("We couldn't find that user.", code="user_not_found")
    if target.id == admin.id and (body.is_active is False or body.role not in (None, "admin")):
        # An admin locking themselves out could leave nobody able to undo it.
        raise AppError("You can't remove your own admin access.", code="cannot_demote_self")
    if body.role is not None:
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active
        if not body.is_active:
            await sessions.revoke_all_for_user(session, target.id)
    audit.record(
        session,
        "admin.user_updated",
        user_id=admin.id,
        target=str(target.id),
        **body.model_dump(exclude_none=True),
    )
    await session.commit()
    return AdminUserOut.model_validate(target)


@router.get("/schools", response_model=list[AdminSchoolOut])
async def list_schools(
    _admin: AdminUser, session: SessionDep, q: Annotated[str, Query(max_length=100)] = ""
) -> list[AdminSchoolOut]:
    learners = (
        select(StudentProfile.school_id, func.count().label("learners"))
        .group_by(StudentProfile.school_id)
        .subquery()
    )
    statement = select(School, func.coalesce(learners.c.learners, 0)).outerjoin(
        learners, learners.c.school_id == School.id
    )
    if q.strip():
        statement = statement.where(School.name.ilike(_like(q.strip()), escape="\\"))
    rows = await session.execute(statement.order_by(School.is_verified, School.name).limit(200))
    return [
        AdminSchoolOut.model_validate(school).model_copy(update={"learners": count})
        for school, count in rows
    ]


@router.patch("/schools/{school_id}", response_model=AdminSchoolOut)
async def update_school(
    school_id: uuid.UUID, body: AdminSchoolUpdate, _admin: AdminUser, session: SessionDep
) -> AdminSchoolOut:
    school = await session.get(School, school_id)
    if school is None:
        raise NotFoundError("We couldn't find that school.", code="school_not_found")
    school.is_verified = body.is_verified
    await session.commit()
    return AdminSchoolOut.model_validate(school)


# --- Mentors and requests --------------------------------------------------------


@router.get("/mentors", response_model=list[AdminMentorOut])
async def list_mentors(_admin: AdminUser, session: SessionDep) -> list[AdminMentorOut]:
    rows = await session.execute(
        select(User, MentorProfile)
        .join(MentorProfile, MentorProfile.user_id == User.id)
        .where(User.deleted_at.is_(None))
        # Those waiting for approval first.
        .order_by(MentorProfile.is_approved, User.created_at.desc())
    )
    return [
        AdminMentorOut(
            user=AdminUserOut.model_validate(user), profile=MentorProfileOut.model_validate(profile)
        )
        for user, profile in rows
    ]


@router.post("/mentors/{user_id}/approval", response_model=AdminMentorOut)
async def set_mentor_approval(
    user_id: uuid.UUID, body: ApproveMentor, admin: AdminUser, session: SessionDep
) -> AdminMentorOut:
    """Approves a mentor to work with learners, or withdraws that approval."""
    user = await session.get(User, user_id)
    if user is None or user.role != UserRole.MENTOR.value:
        raise NotFoundError("We couldn't find that mentor.", code="mentor_not_found")
    profile = await mentoring.get_profile(session, user)
    profile.is_approved = body.approved
    audit.record(
        session,
        "admin.mentor_approval",
        user_id=admin.id,
        mentor=str(user.id),
        approved=body.approved,
    )
    await session.commit()
    return AdminMentorOut(
        user=AdminUserOut.model_validate(user), profile=MentorProfileOut.model_validate(profile)
    )


@router.get("/mentor-requests", response_model=list[MentorRequestOut])
async def list_mentor_requests(
    _admin: AdminUser,
    session: SessionDep,
    status: Annotated[str | None, Query(max_length=20)] = None,
) -> list[MentorRequestOut]:
    statement = select(MentorRequest).order_by(MentorRequest.created_at.desc()).limit(200)
    if status:
        statement = statement.where(MentorRequest.status == status)
    return [await mentoring.to_out(session, row) for row in await session.scalars(statement)]


@router.post("/mentor-requests/{request_id}/assign", response_model=MentorRequestOut)
async def assign_mentor(
    request_id: uuid.UUID, body: AssignMentor, admin: AdminUser, session: SessionDep
) -> MentorRequestOut:
    found = await mentoring.get_request(session, admin, request_id)
    mentor = await session.get(User, body.mentor_id)
    if mentor is None:
        raise NotFoundError("We couldn't find that mentor.", code="mentor_not_found")
    return await mentoring.to_out(session, await mentoring.assign(session, found, mentor))


# --- Usage and cost --------------------------------------------------------------


@router.get("/usage", response_model=list[UsageRow])
async def usage_report(
    _admin: AdminUser,
    session: SessionDep,
    group_by: Annotated[Literal["day", "user", "school", "provider"], Query()] = "day",
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[UsageRow]:
    """AI calls, tokens and estimated cost over a period, grouped one way."""
    since = utcnow() - timedelta(days=days)
    key: Any
    label: Any
    if group_by == "day":
        key = label = func.to_char(func.date_trunc("day", AIUsage.created_at), "YYYY-MM-DD")
    elif group_by == "provider":
        key = label = AIUsage.provider + " / " + AIUsage.model
    elif group_by == "user":
        key, label = cast(AIUsage.user_id, String), func.coalesce(User.email, "(deleted user)")
    else:
        key, label = cast(AIUsage.school_id, String), func.coalesce(School.name, "(no school)")

    statement = select(
        func.coalesce(key, "none"),
        func.max(label),
        func.count(),
        func.coalesce(func.sum(AIUsage.input_tokens), 0),
        func.coalesce(func.sum(AIUsage.output_tokens), 0),
        func.sum(AIUsage.cost_usd),
    ).where(AIUsage.created_at >= since)
    if group_by == "user":
        statement = statement.outerjoin(User, User.id == AIUsage.user_id)
    elif group_by == "school":
        statement = statement.outerjoin(School, School.id == AIUsage.school_id)
    statement = statement.group_by(key).order_by(
        key.desc() if group_by == "day" else func.sum(AIUsage.output_tokens).desc()
    )
    return [
        UsageRow(
            key=str(row[0]),
            label=str(row[1] or row[0]),
            calls=row[2],
            input_tokens=row[3],
            output_tokens=row[4],
            cost_usd=row[5],
        )
        for row in await session.execute(statement.limit(200))
    ]


@router.post("/credits", response_model=MessageResponse)
async def grant_credits(
    body: CreditGrant, admin: AdminUser, session: SessionDep
) -> MessageResponse:
    """Adds (or removes) mentor-reply credits for a learner or a whole school."""
    if (body.user_id is None) == (body.school_id is None):
        raise AppError("Give either a user or a school, not both.", code="one_owner_required")
    session.add(
        CreditLedger(
            user_id=body.user_id, school_id=body.school_id, delta=body.delta, reason=body.reason
        )
    )
    audit.record(session, "admin.credits_granted", user_id=admin.id, delta=body.delta)
    await session.commit()
    return MessageResponse(message="Credits updated.")


# --- Moderation queue ------------------------------------------------------------


@router.get("/moderation", response_model=list[FlagOut])
async def moderation_queue(
    _admin: AdminUser,
    session: SessionDep,
    status: Annotated[Literal["open", "reviewed"], Query()] = "open",
) -> list[FlagOut]:
    rows = await session.scalars(
        select(ModerationFlag)
        .where(ModerationFlag.status == status)
        .order_by(ModerationFlag.created_at.desc())
        .limit(200)
    )
    return [FlagOut.model_validate(row) for row in rows]


@router.post("/moderation/{flag_id}/review", response_model=FlagOut)
async def review_flag(flag_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> FlagOut:
    flag = await session.get(ModerationFlag, flag_id)
    if flag is None:
        raise NotFoundError("We couldn't find that flag.", code="flag_not_found")
    flag.status = "reviewed"
    audit.record(session, "admin.flag_reviewed", user_id=admin.id, flag=str(flag.id))
    await session.commit()
    return FlagOut.model_validate(flag)


# --- Stage definitions and expo dates ----------------------------------------------


@router.get("/stages", response_model=list[StageDefinitionOut])
async def list_stage_definitions(
    _admin: AdminUser, session: SessionDep
) -> list[StageDefinitionOut]:
    return [StageDefinitionOut.model_validate(s) for s in await pathway.definitions(session)]


@router.put("/stages/{key}", response_model=StageDefinitionOut)
async def update_stage_definition(
    key: str, body: StageDefinitionUpdate, admin: AdminUser, session: SessionDep
) -> StageDefinitionOut:
    """Edits a stage's wording, checklist and mentoring instructions. Takes
    effect on the next message in every project at that stage."""
    stage = await session.get(StageDefinition, key)
    if stage is None:
        raise NotFoundError("That stage doesn't exist.", code="stage_not_found")
    keys = [item.key for item in body.deliverables]
    if len(keys) != len(set(keys)):
        raise AppError("Each checklist item needs its own key.", code="duplicate_keys")
    stage.title = body.title
    stage.goal = body.goal
    stage.deliverables = [item.model_dump() for item in body.deliverables]
    stage.exit_criteria = list(body.exit_criteria)
    stage.instructions = body.instructions
    stage.version += 1
    audit.record(session, "admin.stage_edited", user_id=admin.id, stage=key)
    await session.commit()
    await session.refresh(stage)
    return StageDefinitionOut.model_validate(stage)


@router.post("/expo-events", response_model=ExpoEventOut, status_code=201)
async def add_expo_event(body: ExpoEventIn, _admin: AdminUser, session: SessionDep) -> ExpoEventOut:
    event = ExpoEvent(**body.model_dump())
    session.add(event)
    await session.commit()
    return ExpoEventOut.model_validate(event)


@router.delete("/expo-events/{event_id}", status_code=204)
async def delete_expo_event(event_id: uuid.UUID, _admin: AdminUser, session: SessionDep) -> None:
    event = await session.get(ExpoEvent, event_id)
    if event is not None:
        await session.delete(event)
        await session.commit()
