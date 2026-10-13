import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.ai.blocks import Block

Title = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]


class ProjectCreate(BaseModel):
    title: Title = ""


class ProjectUpdate(BaseModel):
    title: Title | None = None
    status: Literal["active", "completed", "archived"] | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    current_stage: str
    status: str
    idea: dict[str, Any] | None
    last_activity_at: datetime
    created_at: datetime


class ConversationCreate(BaseModel):
    title: Title = ""


class ConversationUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    last_message_at: datetime
    created_at: datetime


class ProjectDetail(ProjectOut):
    """A project plus the conversation to open first."""

    latest_conversation: ConversationOut | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant"]
    status: Literal["streaming", "complete", "error", "blocked"]
    blocks: list[Block]
    feedback: int | None
    created_at: datetime


class SendMessageRequest(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class FeedbackRequest(BaseModel):
    # 1 = helpful, -1 = not helpful, 0 = clear.
    value: Literal[-1, 0, 1]


# --- Server-sent events ------------------------------------------------------
# One model per event name, so the frontend's stream handler is typed from the
# same source as everything else.


class MessageStartEvent(BaseModel):
    """The turn has begun. Carries the ids needed to recover if the stream drops."""

    user_message: MessageOut | None
    assistant_message_id: uuid.UUID


class BlockStartEvent(BaseModel):
    index: int
    type: str


class TextDeltaEvent(BaseModel):
    index: int
    text: str


class BlockCompleteEvent(BaseModel):
    index: int
    block: Block


class ToolStatusEvent(BaseModel):
    """A short progress note while a tool runs, e.g. "Finding photos of an LDR…"."""

    tool: str
    text: str


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int


class DoneEvent(BaseModel):
    """The final, saved message. It replaces whatever was streamed."""

    message: MessageOut


class ConversationEvent(BaseModel):
    """The conversation changed (it was given a title)."""

    conversation: ConversationOut


class ChatStreamEvents(BaseModel):
    """Not sent as-is: documents the SSE event names and their payloads."""

    message_start: MessageStartEvent
    block_start: BlockStartEvent
    text_delta: TextDeltaEvent
    block_complete: BlockCompleteEvent
    tool_status: ToolStatusEvent
    usage: UsageOut
    done: DoneEvent
    conversation: ConversationEvent


class MessagePage(BaseModel):
    messages: list[MessageOut]
    # Pass as `before` to load older messages; null when there are none.
    next_before: int | None = Field(default=None)
