"""Projects and their conversations. Every lookup is scoped to the owner."""

import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.time import utcnow
from app.models import Conversation, Message, Project, User
from app.schemas.chat import ProjectUpdate

DEFAULT_TITLE = "New project"


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def create(session: AsyncSession, owner: User, title: str) -> tuple[Project, Conversation]:
    """Creates a project with its first conversation, ready to chat in."""
    project = Project(owner_id=owner.id, title=title or DEFAULT_TITLE)
    session.add(project)
    await session.flush()
    conversation = Conversation(project_id=project.id)
    session.add(conversation)
    await session.commit()
    return project, conversation


async def list_for(session: AsyncSession, owner: User) -> list[Project]:
    return list(
        await session.scalars(
            select(Project)
            .where(Project.owner_id == owner.id, Project.deleted_at.is_(None))
            .order_by(Project.last_activity_at.desc())
        )
    )


async def get(session: AsyncSession, owner: User, project_id: uuid.UUID) -> Project:
    project: Project | None = await session.scalar(
        select(Project).where(
            Project.id == project_id, Project.owner_id == owner.id, Project.deleted_at.is_(None)
        )
    )
    if project is None:
        # The same answer whether it does not exist or belongs to someone
        # else, so ids cannot be probed.
        raise NotFoundError("We couldn't find that project.", code="project_not_found")
    return project


async def update(session: AsyncSession, project: Project, data: ProjectUpdate) -> Project:
    for name, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(project, name, value)
    await session.commit()
    return project


async def delete(session: AsyncSession, project: Project) -> None:
    project.deleted_at = utcnow()
    await session.commit()


async def latest_conversation(session: AsyncSession, project: Project) -> Conversation | None:
    conversation: Conversation | None = await session.scalar(
        select(Conversation)
        .where(Conversation.project_id == project.id, Conversation.deleted_at.is_(None))
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    return conversation


async def list_conversations(
    session: AsyncSession, project: Project, *, query: str = ""
) -> list[Conversation]:
    statement = select(Conversation).where(
        Conversation.project_id == project.id, Conversation.deleted_at.is_(None)
    )
    term = query.strip()
    if term:
        pattern = f"%{_escape_like(term)}%"
        in_messages = exists().where(
            Message.conversation_id == Conversation.id, Message.raw.ilike(pattern, escape="\\")
        )
        statement = statement.where(
            or_(Conversation.title.ilike(pattern, escape="\\"), in_messages)
        )
    return list(await session.scalars(statement.order_by(Conversation.last_message_at.desc())))


async def create_conversation(
    session: AsyncSession, project: Project, title: str = ""
) -> Conversation:
    conversation = Conversation(project_id=project.id, title=title)
    session.add(conversation)
    await session.commit()
    return conversation


async def get_conversation(
    session: AsyncSession, owner: User, conversation_id: uuid.UUID
) -> tuple[Conversation, Project]:
    row = (
        await session.execute(
            select(Conversation, Project)
            .join(Project, Project.id == Conversation.project_id)
            .where(
                Conversation.id == conversation_id,
                Conversation.deleted_at.is_(None),
                Project.owner_id == owner.id,
                Project.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("We couldn't find that conversation.", code="conversation_not_found")
    return row[0], row[1]


async def rename_conversation(
    session: AsyncSession, conversation: Conversation, title: str
) -> Conversation:
    conversation.title = title
    await session.commit()
    return conversation


async def delete_conversation(session: AsyncSession, conversation: Conversation) -> None:
    conversation.deleted_at = utcnow()
    await session.commit()


async def count_messages(session: AsyncSession, conversation_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
    )
    return int(total or 0)
