import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.ai.blocks import Block

EntryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
Cell = Annotated[str, StringConstraints(max_length=120)]


class LogbookEntryIn(BaseModel):
    text: EntryText


class LogbookEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    stage_key: str
    created_at: datetime
    updated_at: datetime


class PinIn(BaseModel):
    message_id: uuid.UUID
    # Which block of that message to save.
    block_index: Annotated[int, Field(ge=0, le=200)]


class PinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    block: Block
    message_id: uuid.UUID | None
    created_at: datetime


class DatasetIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""
    columns: Annotated[list[Cell], Field(min_length=1, max_length=8)]
    rows: Annotated[list[Annotated[list[Cell], Field(max_length=8)]], Field(max_length=200)]


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    columns: list[str]
    rows: list[list[str]]
    updated_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size: int
