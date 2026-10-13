import re
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Request, Response, UploadFile, status

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.core.errors import AppError, error_responses
from app.core.rate_limit import limiter
from app.schemas.workspace import (
    AttachmentOut,
    DatasetIn,
    DatasetOut,
    LogbookEntryIn,
    LogbookEntryOut,
    PinIn,
    PinOut,
)
from app.services import projects as project_service
from app.services import workspace
from app.services.export_pdf import build_project_pdf
from app.services.storage import Storage

router = APIRouter(tags=["workspace"], responses=error_responses(401, 404))

NO_CONTENT = Response(status_code=status.HTTP_204_NO_CONTENT)


def get_storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


# --- Logbook -----------------------------------------------------------------


@router.get("/projects/{project_id}/logbook", response_model=list[LogbookEntryOut])
async def list_logbook(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[LogbookEntryOut]:
    project = await project_service.get(session, user, project_id)
    entries = await workspace.list_logbook(session, project)
    return [LogbookEntryOut.model_validate(entry) for entry in entries]


@router.post(
    "/projects/{project_id}/logbook",
    response_model=LogbookEntryOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_logbook_entry(
    project_id: uuid.UUID, body: LogbookEntryIn, user: CurrentUser, session: SessionDep
) -> LogbookEntryOut:
    project = await project_service.get(session, user, project_id)
    return LogbookEntryOut.model_validate(
        await workspace.add_logbook_entry(session, project, body.text)
    )


@router.put("/logbook/{entry_id}", response_model=LogbookEntryOut)
async def edit_logbook_entry(
    entry_id: uuid.UUID, body: LogbookEntryIn, user: CurrentUser, session: SessionDep
) -> LogbookEntryOut:
    """Edits the text. The original date is kept: a logbook is a dated record."""
    entry = await workspace.get_logbook_entry(session, user, entry_id)
    entry.text = body.text
    await session.commit()
    await session.refresh(entry)  # updated_at is set by the database
    return LogbookEntryOut.model_validate(entry)


@router.delete("/logbook/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logbook_entry(
    entry_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    await session.delete(await workspace.get_logbook_entry(session, user, entry_id))
    await session.commit()
    return NO_CONTENT


# --- Saved blocks ------------------------------------------------------------


@router.get("/projects/{project_id}/pins", response_model=list[PinOut])
async def list_pins(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> list[PinOut]:
    project = await project_service.get(session, user, project_id)
    return [PinOut.model_validate(pin) for pin in await workspace.list_pins(session, project)]


@router.post(
    "/projects/{project_id}/pins", response_model=PinOut, status_code=status.HTTP_201_CREATED
)
async def pin_block(
    project_id: uuid.UUID, body: PinIn, user: CurrentUser, session: SessionDep
) -> PinOut:
    """Saves one block of a mentor reply (a diagram, circuit, materials list) to the project."""
    project = await project_service.get(session, user, project_id)
    pin = await workspace.pin_block(session, project, body.message_id, body.block_index)
    return PinOut.model_validate(pin)


@router.delete("/pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unpin(pin_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    await session.delete(await workspace.get_pin(session, user, pin_id))
    await session.commit()
    return NO_CONTENT


# --- Experiment data ---------------------------------------------------------


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetOut])
async def list_datasets(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[DatasetOut]:
    project = await project_service.get(session, user, project_id)
    found = await workspace.list_datasets(session, project)
    return [DatasetOut.model_validate(dataset) for dataset in found]


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    project_id: uuid.UUID, body: DatasetIn, user: CurrentUser, session: SessionDep
) -> DatasetOut:
    project = await project_service.get(session, user, project_id)
    return DatasetOut.model_validate(await workspace.create_dataset(session, project, body))


@router.put("/datasets/{dataset_id}", response_model=DatasetOut)
async def update_dataset(
    dataset_id: uuid.UUID, body: DatasetIn, user: CurrentUser, session: SessionDep
) -> DatasetOut:
    dataset = await workspace.get_dataset(session, user, dataset_id)
    return DatasetOut.model_validate(await workspace.update_dataset(session, dataset, body))


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    await session.delete(await workspace.get_dataset(session, user, dataset_id))
    await session.commit()
    return NO_CONTENT


# --- Uploads -----------------------------------------------------------------


@router.post(
    "/projects/{project_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(413, 415),
)
@limiter.limit("30/hour")
async def upload_photo(
    request: Request,
    project_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="A JPEG, PNG or WebP photo.")],
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> AttachmentOut:
    """Uploads a photo (of a sketch, circuit or setup) to attach to a message."""
    project = await project_service.get(session, user, project_id)
    # Read one byte past the limit: enough to know it is too big without
    # holding an arbitrarily large upload in memory.
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise AppError("That file is empty.", code="empty_file")
    attachment = await workspace.save_attachment(
        session,
        get_storage(request),
        settings,
        user,
        project,
        filename=file.filename or "",
        data=data,
    )
    return AttachmentOut.model_validate(attachment)


@router.get("/attachments/{attachment_id}")
async def get_photo(
    attachment_id: uuid.UUID, request: Request, user: CurrentUser, session: SessionDep
) -> Response:
    attachment = await workspace.get_attachment(session, user, attachment_id)
    data = await get_storage(request).read(attachment.storage_key)
    return Response(
        data,
        media_type=attachment.content_type,
        headers={
            # Private: only this learner may cache it. It never changes.
            "Cache-Control": "private, max-age=31536000, immutable",
            # Uploaded bytes are only ever shown as an image, never run.
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


# --- Export ------------------------------------------------------------------


@router.get("/projects/{project_id}/export.pdf", response_class=Response)
@limiter.limit("20/hour")
async def export_project_pdf(
    request: Request, project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    """A printable project summary: idea, progress, materials, data and logbook."""
    project = await project_service.get(session, user, project_id)
    pdf = await build_project_pdf(session, user, project)
    await session.commit()
    name = re.sub(r"[^A-Za-z0-9]+", "-", project.title).strip("-").lower() or "project"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}-summary.pdf"'},
    )
