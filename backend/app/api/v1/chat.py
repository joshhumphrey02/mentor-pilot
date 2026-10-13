import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response, status
from sse_starlette import EventSourceResponse

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import error_responses
from app.core.rate_limit import limiter
from app.schemas.chat import (
    ChatStreamEvents,
    ConversationOut,
    ConversationUpdate,
    FeedbackRequest,
    MessageOut,
    MessagePage,
    SendMessageRequest,
)
from app.services import chat as chat_service
from app.services import projects as project_service
from app.services.chat import ChatService

router = APIRouter(tags=["chat"], responses=error_responses(401, 404))

CHAT_LIMIT = "30/minute"

# Documents the event stream in OpenAPI, which also generates the event
# payload types for the frontend.
STREAM_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "A Server-Sent Events stream. Each event's `data` is JSON; the "
        "event names and payloads are the fields of ChatStreamEvents.",
        "content": {"text/event-stream": {"schema": ChatStreamEvents.model_json_schema()}},
    },
    **error_responses(409, 429),
}


def get_chat(request: Request) -> ChatService:
    service: ChatService = request.app.state.chat
    return service


def _stream(chat: ChatService, turn: chat_service.Turn) -> EventSourceResponse:
    return EventSourceResponse(
        chat.stream(turn),
        ping=15,
        # Stops nginx-style proxies from buffering the stream into one lump.
        headers={"X-Accel-Buffering": "no"},
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: uuid.UUID, body: ConversationUpdate, user: CurrentUser, session: SessionDep
) -> ConversationOut:
    conversation, _ = await project_service.get_conversation(session, user, conversation_id)
    renamed = await project_service.rename_conversation(session, conversation, body.title)
    return ConversationOut.model_validate(renamed)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    conversation, _ = await project_service.get_conversation(session, user, conversation_id)
    await project_service.delete_conversation(session, conversation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
async def list_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    before: Annotated[int | None, Query(description="Cursor from `next_before`.")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    conversation, _ = await project_service.get_conversation(session, user, conversation_id)
    messages, cursor = await chat_service.list_messages(
        session, conversation, before=before, limit=limit
    )
    return MessagePage(
        messages=[MessageOut.model_validate(message) for message in messages], next_before=cursor
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=EventSourceResponse,
    responses=STREAM_RESPONSES,
)
@limiter.limit(CHAT_LIMIT)
async def send_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    user: CurrentUser,
    session: SessionDep,
) -> EventSourceResponse:
    """Sends a message and streams the mentor's reply.

    The reply is saved even if this connection drops: fetch it afterwards with
    `GET /messages/{assistant_message_id}` (the id arrives in `message_start`).
    """
    chat = get_chat(request)
    turn = await chat.begin_turn(session, user, conversation_id, body.text)
    return _stream(chat, turn)


@router.post(
    "/conversations/{conversation_id}/regenerate",
    response_class=EventSourceResponse,
    responses=STREAM_RESPONSES,
)
@limiter.limit(CHAT_LIMIT)
async def regenerate_reply(
    request: Request, conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> EventSourceResponse:
    """Discards the mentor's latest reply and streams a new one."""
    chat = get_chat(request)
    turn = await chat.begin_regeneration(session, user, conversation_id)
    return _stream(chat, turn)


@router.get("/messages/{message_id}", response_model=MessageOut)
async def get_message(message_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> MessageOut:
    """One message. Poll this after a dropped stream until `status` leaves `streaming`."""
    return MessageOut.model_validate(await chat_service.get_message(session, user, message_id))


@router.post("/messages/{message_id}/feedback", response_model=MessageOut)
async def give_feedback(
    message_id: uuid.UUID, body: FeedbackRequest, user: CurrentUser, session: SessionDep
) -> MessageOut:
    message = await chat_service.get_message(session, user, message_id)
    return MessageOut.model_validate(await chat_service.set_feedback(session, message, body.value))
