"""Profile, onboarding and the POPIA data-subject rights (export and deletion)."""

from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, PermissionDeniedError
from app.core.security import verify_password
from app.core.time import utcnow
from app.models import (
    Attachment,
    AuditLog,
    Conversation,
    EmailToken,
    Message,
    ModerationFlag,
    Project,
    StudentProfile,
    User,
    UserRole,
)
from app.schemas.user import OnboardingRequest, UserUpdate
from app.services import audit, email, schools, sessions
from app.services.email import Mailer
from app.services.storage import Storage

ADULT_AGE = 18
MIN_AGE = 8
MAX_AGE = 100


def age_on(date_of_birth: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


async def update_profile(session: AsyncSession, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, field, value)
    await session.commit()
    return user


async def complete_onboarding(
    session: AsyncSession, settings: Settings, mailer: Mailer, user: User, data: OnboardingRequest
) -> User:
    if user.role != UserRole.STUDENT.value:
        raise PermissionDeniedError("Onboarding is for learner accounts.")

    age = age_on(data.date_of_birth, utcnow().date())
    if not MIN_AGE <= age <= MAX_AGE:
        raise AppError("Please check your date of birth.", code="invalid_date_of_birth")

    is_minor = age < ADULT_AGE
    if is_minor and not (data.guardian_consent and data.guardian_email):
        raise AppError(
            "Because you are under 18, we need a parent, guardian or teacher to agree, "
            "and their email address.",
            code="guardian_consent_required",
        )
    if user.privacy_accepted_at is None and not data.accept_privacy:
        raise AppError("Please accept the privacy notice to continue.", code="privacy_required")

    if data.school_id is not None:
        school = await schools.get(session, data.school_id)
    elif data.new_school is not None:
        school = await schools.get_or_create(session, data.new_school, created_by_id=user.id)
    else:
        school = None

    now = utcnow()
    profile = user.student_profile
    if profile is None:
        profile = StudentProfile(user_id=user.id)
        user.student_profile = profile

    guardian_email = str(data.guardian_email).lower() if data.guardian_email else None
    notify_guardian = (
        is_minor and guardian_email is not None and guardian_email != profile.guardian_email
    )

    profile.school = school
    profile.education_level = data.education_level
    profile.grade = data.grade or None
    profile.province = data.province
    # Order-preserving de-duplication.
    profile.interests = list(dict.fromkeys(data.interests))
    profile.learning_style = data.learning_style
    profile.date_of_birth = data.date_of_birth
    # Guardian details are only kept for minors (collect only what is needed).
    profile.guardian_consent = is_minor and data.guardian_consent
    profile.guardian_email = guardian_email if is_minor else None
    profile.guardian_consent_at = now if profile.guardian_consent else None

    user.full_name = data.full_name
    user.preferred_language = data.preferred_language
    if user.privacy_accepted_at is None:
        user.privacy_accepted_at = now
    first_time = user.onboarded_at is None
    if first_time:
        user.onboarded_at = now
        audit.record(session, "user.onboarded", user_id=user.id, minor=is_minor)

    await session.commit()

    if notify_guardian and guardian_email is not None:
        mailer.send_later(
            email.guardian_notice_email(
                guardian_email, user.full_name, f"{settings.public_base_url}/privacy"
            )
        )
    return user


async def export_data(session: AsyncSession, user: User) -> dict[str, Any]:
    """Everything we hold about the user, in a portable form (POPIA s23 access)."""
    profile = user.student_profile
    events = await session.scalars(
        select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at)
    )
    exported_projects = await _export_projects(session, user)
    audit.record(session, "user.data_exported", user_id=user.id)
    await session.commit()

    return {
        "exported_at": utcnow().isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "preferred_language": user.preferred_language,
            "signs_in_with_google": user.google_sub is not None,
            "email_verified_at": _iso(user.email_verified_at),
            "privacy_accepted_at": _iso(user.privacy_accepted_at),
            "onboarded_at": _iso(user.onboarded_at),
            "created_at": _iso(user.created_at),
        },
        "student_profile": None
        if profile is None
        else {
            "school": None
            if profile.school is None
            else {
                "name": profile.school.name,
                "province": profile.school.province,
                "town": profile.school.town,
            },
            "education_level": profile.education_level,
            "grade": profile.grade,
            "province": profile.province,
            "interests": profile.interests,
            "learning_style": profile.learning_style,
            "date_of_birth": _iso(profile.date_of_birth),
            "guardian_consent": profile.guardian_consent,
            "guardian_email": profile.guardian_email,
            "guardian_consent_at": _iso(profile.guardian_consent_at),
        },
        "projects": exported_projects,
        "activity": [
            {"action": event.action, "at": _iso(event.created_at), "details": event.details}
            for event in events
        ],
    }


async def _export_projects(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    projects = await session.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at)
    )
    exported: list[dict[str, Any]] = []
    for project in projects:
        conversations = await session.scalars(
            select(Conversation)
            .where(Conversation.project_id == project.id)
            .order_by(Conversation.created_at)
        )
        chats: list[dict[str, Any]] = []
        for conversation in conversations:
            messages = await session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.seq)
            )
            chats.append(
                {
                    "title": conversation.title,
                    "created_at": _iso(conversation.created_at),
                    "messages": [
                        {
                            "role": message.role,
                            "at": _iso(message.created_at),
                            "blocks": message.blocks,
                        }
                        for message in messages
                    ],
                }
            )
        exported.append(
            {
                "title": project.title,
                "stage": project.current_stage,
                "status": project.status,
                "idea": project.idea,
                "created_at": _iso(project.created_at),
                "conversations": chats,
            }
        )
    return exported


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


async def delete_account(
    session: AsyncSession, user: User, *, password: str | None, storage: Storage
) -> None:
    """Erases personal data and closes the account (POPIA s24 deletion).

    The row is kept, anonymised, so that records which must outlive the account
    (usage and billing figures) still have something to point at.
    """
    if user.has_password and not await verify_password(password or "", user.password_hash):
        raise AppError("That password is incorrect.", code="invalid_credentials", status_code=403)

    await sessions.revoke_all_for_user(session, user.id)
    await session.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
    # Audit details can hold personal data; the deletion itself is still recorded below.
    await session.execute(delete(AuditLog).where(AuditLog.user_id == user.id))
    # Uploaded photos live outside the database, so they are removed by hand.
    uploads = await session.scalars(select(Attachment).where(Attachment.owner_id == user.id))
    for upload in uploads:
        await storage.delete(upload.storage_key)
    await session.execute(delete(Attachment).where(Attachment.owner_id == user.id))
    # Cascades to their conversations, messages, logbook, saved items and data.
    await session.execute(delete(Project).where(Project.owner_id == user.id))
    await session.execute(delete(ModerationFlag).where(ModerationFlag.user_id == user.id))
    if user.student_profile is not None:
        await session.delete(user.student_profile)
        user.student_profile = None

    user.email = f"deleted-{user.id}@deleted.invalid"
    user.full_name = "Deleted user"
    user.password_hash = None
    user.google_sub = None
    user.is_active = False
    user.deleted_at = utcnow()
    audit.record(session, "user.account_deleted", user_id=user.id)
    await session.commit()
