"""The learner's own material in a project: logbook, saved blocks, data, uploads."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.blocks import load_blocks
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.models import (
    Attachment,
    Conversation,
    ExperimentDataset,
    LogbookEntry,
    Message,
    PinnedItem,
    Project,
    User,
)
from app.schemas.workspace import DatasetIn
from app.services.storage import Storage

# Checked against the file's first bytes, not the name or the type the browser
# claims: either of those can say "image" about anything.
_SIGNATURES: dict[str, tuple[str, bytes]] = {
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
}
# What a block is called in the Saved list when it has no title of its own.
_PIN_TITLES = {
    "idea_cards": "Project ideas",
    "comparison_table": "Comparison",
    "checklist": "Checklist",
    "quiz": "Quick check",
    "image_gallery": "Photos",
    "video_cards": "Videos",
    "judge_scorecard": "Judge practice scorecard",
    "callout": "Note from your mentor",
    "markdown": "Note from your mentor",
}
_UNPINNABLE = {"suggested_replies", "error", "stage_transition", "image"}


def sniff_image_type(data: bytes) -> tuple[str, str] | None:
    """(content type, extension) if the bytes are an image we accept, else None."""
    for content_type, (extension, magic) in _SIGNATURES.items():
        if data.startswith(magic):
            return content_type, extension
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


# --- Logbook -----------------------------------------------------------------


async def list_logbook(session: AsyncSession, project: Project) -> list[LogbookEntry]:
    return list(
        await session.scalars(
            select(LogbookEntry)
            .where(LogbookEntry.project_id == project.id)
            .order_by(LogbookEntry.created_at.desc())
        )
    )


async def add_logbook_entry(session: AsyncSession, project: Project, text: str) -> LogbookEntry:
    entry = LogbookEntry(project_id=project.id, text=text, stage_key=project.current_stage)
    session.add(entry)
    await session.commit()
    return entry


async def _owned(session: AsyncSession, user: User, model: Any, item_id: uuid.UUID) -> Any:
    """Loads a project-scoped row, only if the project is the user's."""
    row = await session.scalar(
        select(model)
        .join(Project, Project.id == model.project_id)
        .where(model.id == item_id, Project.owner_id == user.id, Project.deleted_at.is_(None))
    )
    if row is None:
        raise NotFoundError("We couldn't find that.", code="not_found")
    return row


async def get_logbook_entry(session: AsyncSession, user: User, entry_id: uuid.UUID) -> LogbookEntry:
    entry: LogbookEntry = await _owned(session, user, LogbookEntry, entry_id)
    return entry


# --- Saved (pinned) blocks ---------------------------------------------------


async def list_pins(session: AsyncSession, project: Project) -> list[PinnedItem]:
    return list(
        await session.scalars(
            select(PinnedItem)
            .where(PinnedItem.project_id == project.id)
            .order_by(PinnedItem.created_at.desc())
        )
    )


async def pin_block(
    session: AsyncSession, project: Project, message_id: uuid.UUID, block_index: int
) -> PinnedItem:
    message = await session.scalar(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.id == message_id, Conversation.project_id == project.id)
    )
    if message is None or block_index >= len(message.blocks):
        raise NotFoundError("We couldn't find that to save.", code="block_not_found")
    block = message.blocks[block_index]
    if block.get("type") in _UNPINNABLE:
        raise AppError("That can't be saved.", code="not_pinnable")
    load_blocks([block])  # refuse anything that is no longer a valid block

    title = str(block.get("title") or "") or _PIN_TITLES.get(str(block.get("type")), "Saved item")
    if block.get("type") in ("markdown", "callout"):
        first_line = str(block.get("text", "")).strip().splitlines()[0:1]
        title = (first_line[0].lstrip("#* ").strip()[:80] if first_line else "") or title
    pin = PinnedItem(project_id=project.id, message_id=message.id, title=title, block=block)
    session.add(pin)
    await session.commit()
    return pin


async def get_pin(session: AsyncSession, user: User, pin_id: uuid.UUID) -> PinnedItem:
    pin: PinnedItem = await _owned(session, user, PinnedItem, pin_id)
    return pin


# --- Experiment data ---------------------------------------------------------


def _normalise(data: DatasetIn) -> tuple[list[str], list[list[str]]]:
    """Makes every row exactly as wide as the header, padding or trimming."""
    width = len(data.columns)
    return list(data.columns), [(row + [""] * width)[:width] for row in data.rows]


async def list_datasets(session: AsyncSession, project: Project) -> list[ExperimentDataset]:
    return list(
        await session.scalars(
            select(ExperimentDataset)
            .where(ExperimentDataset.project_id == project.id)
            .order_by(ExperimentDataset.created_at)
        )
    )


async def create_dataset(
    session: AsyncSession, project: Project, data: DatasetIn
) -> ExperimentDataset:
    columns, rows = _normalise(data)
    dataset = ExperimentDataset(
        project_id=project.id, title=data.title or "My results", columns=columns, rows=rows
    )
    session.add(dataset)
    await session.commit()
    return dataset


async def get_dataset(
    session: AsyncSession, user: User, dataset_id: uuid.UUID
) -> ExperimentDataset:
    dataset: ExperimentDataset = await _owned(session, user, ExperimentDataset, dataset_id)
    return dataset


async def update_dataset(
    session: AsyncSession, dataset: ExperimentDataset, data: DatasetIn
) -> ExperimentDataset:
    dataset.columns, dataset.rows = _normalise(data)
    dataset.title = data.title or dataset.title
    await session.commit()
    # updated_at is set by the database on write, so it has to be read back.
    await session.refresh(dataset)
    return dataset


# --- Uploads -----------------------------------------------------------------


async def save_attachment(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    user: User,
    project: Project,
    *,
    filename: str,
    data: bytes,
) -> Attachment:
    if len(data) > settings.max_upload_bytes:
        limit = settings.max_upload_bytes // (1024 * 1024)
        raise AppError(
            f"That photo is too big. The limit is {limit} MB.",
            code="file_too_large",
            status_code=413,
        )
    kind = sniff_image_type(data)
    if kind is None:
        raise AppError(
            "Only JPEG, PNG or WebP photos can be uploaded.",
            code="unsupported_file_type",
            status_code=415,
        )
    content_type, extension = kind
    attachment_id = uuid.uuid4()
    # The stored name is ours; the learner's filename is kept only as a label.
    key = f"{project.id}/{attachment_id}.{extension}"
    await storage.save(key, data)
    attachment = Attachment(
        id=attachment_id,
        owner_id=user.id,
        project_id=project.id,
        filename=filename[:255] or f"photo.{extension}",
        content_type=content_type,
        size=len(data),
        storage_key=key,
    )
    session.add(attachment)
    await session.commit()
    return attachment


async def get_attachment(session: AsyncSession, user: User, attachment_id: uuid.UUID) -> Attachment:
    attachment: Attachment | None = await session.scalar(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.owner_id == user.id)
    )
    if attachment is None:
        raise NotFoundError("We couldn't find that photo.", code="attachment_not_found")
    return attachment
