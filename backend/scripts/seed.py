"""Seeds demo data for local development. Run with `make seed`.

Safe to run repeatedly: existing rows are left alone. Never run in production:
the demo accounts share a well-known password.
"""

import asyncio
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.session import create_engine, create_session_factory
from app.models import School, StudentProfile, User, UserRole
from app.schemas.user import SchoolCreate
from app.services import mentoring, schools
from app.services.auth import get_user_by_email

logger = structlog.get_logger(__name__)

DEMO_PASSWORD = "mentorpilot-demo"  # noqa: S105  (dev-only, documented in the README)

DEMO_SCHOOLS = [
    SchoolCreate(name="Khayelitsha Science Academy", province="Western Cape", town="Cape Town"),
    SchoolCreate(name="Langa High School", province="Western Cape", town="Cape Town"),
    SchoolCreate(name="Paarl Technical High School", province="Western Cape", town="Paarl"),
]


async def _user(session: AsyncSession, *, email: str, full_name: str, role: UserRole) -> User:
    existing = await get_user_by_email(session, email)
    if existing is not None:
        return existing
    now = utcnow()
    user = User(
        email=email,
        full_name=full_name,
        role=role.value,
        password_hash=await hash_password(DEMO_PASSWORD),
        email_verified_at=now,
        privacy_accepted_at=now,
        # Staff accounts have no learner onboarding to do.
        onboarded_at=None if role is UserRole.STUDENT else now,
        # Set explicitly so the relationship counts as loaded; reading an
        # unloaded one would trigger a lazy load, which async sessions forbid.
        student_profile=None,
    )
    session.add(user)
    await session.flush()
    logger.info("seed.user_created", role=role.value, login=email)
    return user


async def seed(session: AsyncSession) -> None:
    seeded: list[School] = []
    for data in DEMO_SCHOOLS:
        school = await schools.get_or_create(session, data, created_by_id=None)
        school.is_verified = True
        seeded.append(school)

    await _user(
        session, email="admin@demo.example.com", full_name="Demo Admin", role=UserRole.ADMIN
    )
    mentor = await _user(
        session, email="mentor@demo.example.com", full_name="Demo Mentor", role=UserRole.MENTOR
    )
    profile = await mentoring.get_profile(session, mentor)
    if not profile.expertise:
        profile.organisation = "Cape Town Makerspace"
        profile.bio = "Electronics hobbyist and former expo judge."
        profile.expertise = ["hardware_build", "coding", "expo_coaching"]
        profile.regions = ["Western Cape"]
        profile.availability = "Saturday mornings"
        profile.is_approved = True
    student = await _user(
        session, email="student@demo.example.com", full_name="Thandi Mokoena", role=UserRole.STUDENT
    )
    if student.student_profile is None:
        now = utcnow()
        student.student_profile = StudentProfile(
            user_id=student.id,
            school=seeded[0],
            grade="10",
            province="Western Cape",
            interests=["robotics", "energy", "environment"],
            learning_style="hands_on",
            date_of_birth=date(now.year - 16, 3, 14),
            guardian_consent=True,
            guardian_email="guardian@demo.example.com",
            guardian_consent_at=now,
        )
        student.onboarded_at = now

    await session.commit()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    if settings.is_prod:
        raise SystemExit("Refusing to seed demo accounts in production.")
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            await seed(session)
    finally:
        await engine.dispose()
    logger.info("seed.done", demo_password=DEMO_PASSWORD)


if __name__ == "__main__":
    asyncio.run(main())
