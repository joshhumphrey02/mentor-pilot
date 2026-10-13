"""Seeds demo data for local development. Run with `make seed`.

Safe to run repeatedly: existing rows are left alone. Never run in production:
the demo accounts share a well-known password.
"""

import asyncio
from datetime import date, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.blocks import dump_blocks
from app.ai.stream_parser import BlockStreamParser
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.session import create_engine, create_session_factory
from app.models import (
    ExperimentDataset,
    ExpoEvent,
    LogbookEntry,
    Message,
    School,
    StudentProfile,
    User,
    UserRole,
)
from app.schemas.user import SchoolCreate
from app.services import mentoring, pathway, projects, schools
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
    await _demo_project(session, student)
    await _demo_expo(session)
    await session.commit()


DEMO_IDEA = {
    "title": "Solar phone charger for load-shedding",
    "problem": "Phones run flat during load-shedding, so learners cannot study or call home.",
    "field": "Energy",
    "difficulty": 3,
    "cost_min_zar": 150,
    "cost_max_zar": 380,
    "materials": ["6V solar panel", "USB charging module", "old power bank cell", "cardboard"],
    "time_needed": "4 weeks",
    "why_judges_like_it": "A real local problem with results you can measure.",
    "safety_level": "medium",
    "safety_note": "Never short the battery cell. Ask an adult to help with soldering.",
    "reason": "My phone dies every evening during stage 4.",
}


async def _demo_project(session: AsyncSession, student: User) -> None:
    """A project part-way along the pathway, so the app has something to show."""
    if await projects.list_for(session, student):
        return
    project, conversation = await projects.create(session, student, DEMO_IDEA["title"])
    project.idea = DEMO_IDEA
    project.memory = (
        "Thandi noticed phones running flat during load-shedding. She chose to build a small "
        "solar charger and test how charging time changes with the angle of the panel."
    )
    await pathway.move_to(session, project, "method")
    for stage_key, item_key, note in (
        ("problem_discovery", "observations", "Flat phones, dark streets, spoiled food"),
        ("problem_discovery", "chosen_problem", "Phones running flat"),
        ("idea_development", "chosen_idea", "Solar phone charger"),
        ("research_question", "final_question", "How does panel angle affect charging time?"),
    ):
        await pathway.set_item(
            session,
            project,
            stage_key=stage_key,
            item_key=item_key,
            done=True,
            note=note,
            by="learner",
        )
    for role, text in (
        ("user", "I want to test if the angle of the solar panel changes how fast it charges."),
        (
            "assistant",
            "That is a testable question. What will you change on purpose, and what will you "
            "measure?\n\n:::callout judge_insight\nJudges often ask why you chose your "
            "angles. Write your reason in your logbook.\n:::\n\n:::replies\nI'll change the "
            "angle\nHelp me pick the angles\n:::",
        ),
    ):
        parser = BlockStreamParser()
        parser.feed(text)
        parser.finish()
        session.add(
            Message(
                conversation_id=conversation.id,
                role=role,
                raw=text,
                blocks=dump_blocks(parser.blocks),
            )
        )
        await session.flush()
    conversation.title = "Planning the solar panel test"
    session.add_all(
        [
            LogbookEntry(
                project_id=project.id,
                stage_key="problem_discovery",
                text="Counted 7 of 10 classmates whose phones were flat by 7pm on Tuesday.",
            ),
            LogbookEntry(
                project_id=project.id,
                stage_key="research_question",
                text="Decided to test three panel angles: flat, 30 degrees and 60 degrees.",
            ),
            ExperimentDataset(
                project_id=project.id,
                title="Charging time by panel angle",
                columns=["Angle (degrees)", "Minutes to reach 20%"],
                rows=[["0", "58"], ["30", "41"], ["60", "47"]],
            ),
        ]
    )
    logger.info("seed.project_created", title=project.title)


async def _demo_expo(session: AsyncSession) -> None:
    if await session.scalar(select(func.count()).select_from(ExpoEvent)):
        return
    today = utcnow().date()
    session.add(
        ExpoEvent(
            name="Regional Expo for Young Scientists (demo date)",
            starts_on=today + timedelta(days=75),
            location="Cape Town",
            province="Western Cape",
        )
    )


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
