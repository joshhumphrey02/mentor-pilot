import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import error_responses
from app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ProjectUpdate,
)
from app.services import projects as project_service

router = APIRouter(prefix="/projects", tags=["projects"], responses=error_responses(401, 404))


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: CurrentUser, session: SessionDep) -> list[ProjectOut]:
    """Your projects, most recently active first."""
    found = await project_service.list_for(session, user)
    return [ProjectOut.model_validate(project) for project in found]


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate, user: CurrentUser, session: SessionDep
) -> ProjectDetail:
    """Starts a project, with a first conversation ready to chat in."""
    project, conversation = await project_service.create(session, user, body.title)
    return ProjectDetail(
        **ProjectOut.model_validate(project).model_dump(),
        latest_conversation=ConversationOut.model_validate(conversation),
    )


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ProjectDetail:
    project = await project_service.get(session, user, project_id)
    latest = await project_service.latest_conversation(session, project)
    return ProjectDetail(
        **ProjectOut.model_validate(project).model_dump(),
        latest_conversation=ConversationOut.model_validate(latest) if latest else None,
    )


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, user: CurrentUser, session: SessionDep
) -> ProjectOut:
    project = await project_service.get(session, user, project_id)
    return ProjectOut.model_validate(await project_service.update(session, project, body))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    project = await project_service.get(session, user, project_id)
    await project_service.delete(session, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/conversations", response_model=list[ConversationOut])
async def list_conversations(
    project_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(max_length=100, description="Search titles and messages.")] = "",
) -> list[ConversationOut]:
    project = await project_service.get(session, user, project_id)
    found = await project_service.list_conversations(session, project, query=q)
    return [ConversationOut.model_validate(conversation) for conversation in found]


@router.post(
    "/{project_id}/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    project_id: uuid.UUID, body: ConversationCreate, user: CurrentUser, session: SessionDep
) -> ConversationOut:
    project = await project_service.get(session, user, project_id)
    conversation = await project_service.create_conversation(session, project, body.title)
    return ConversationOut.model_validate(conversation)
