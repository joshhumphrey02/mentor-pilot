import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import School
from app.schemas.user import SchoolCreate


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search(
    session: AsyncSession, *, query: str, province: str | None, limit: int
) -> list[School]:
    statement = select(School)
    term = query.strip()
    if term:
        statement = statement.where(School.name.ilike(f"%{_escape_like(term)}%", escape="\\"))
    if province:
        statement = statement.where(School.province == province)
    # Verified schools first, so learners pick the canonical entry over a duplicate.
    statement = statement.order_by(School.is_verified.desc(), School.name).limit(limit)
    return list(await session.scalars(statement))


async def get(session: AsyncSession, school_id: uuid.UUID) -> School:
    school = await session.get(School, school_id)
    if school is None:
        raise NotFoundError("We couldn't find that school.", code="school_not_found")
    return school


async def _find(session: AsyncSession, name: str, province: str) -> School | None:
    school: School | None = await session.scalar(
        select(School).where(func.lower(School.name) == name.lower(), School.province == province)
    )
    return school


async def get_or_create(
    session: AsyncSession, data: SchoolCreate, *, created_by_id: uuid.UUID | None
) -> School:
    """Returns the matching school, adding it if this is the first time it is named.

    Does not commit. Safe against two learners adding the same school at once.
    """
    existing = await _find(session, data.name, data.province)
    if existing is not None:
        return existing

    school = School(
        name=data.name, province=data.province, town=data.town or None, created_by_id=created_by_id
    )
    try:
        async with session.begin_nested():
            session.add(school)
    except IntegrityError:
        raced = await _find(session, data.name, data.province)
        if raced is None:
            raise
        return raced
    return school
