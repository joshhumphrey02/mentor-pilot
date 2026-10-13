from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.user import SchoolCreate, SchoolOut
from app.services import schools as school_service

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("", response_model=list[SchoolOut])
async def search_schools(
    _user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(max_length=100)] = "",
    province: Annotated[str | None, Query(max_length=60)] = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[SchoolOut]:
    found = await school_service.search(session, query=q, province=province, limit=limit)
    return [SchoolOut.model_validate(school) for school in found]


@router.post("", response_model=SchoolOut, status_code=status.HTTP_201_CREATED)
async def add_school(body: SchoolCreate, user: CurrentUser, session: SessionDep) -> SchoolOut:
    """Adds a school that is not listed yet (or returns it if someone already did)."""
    school = await school_service.get_or_create(session, body, created_by_id=user.id)
    await session.commit()
    return SchoolOut.model_validate(school)
