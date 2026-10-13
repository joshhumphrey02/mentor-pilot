import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.ai.blocks import HelpType
from app.schemas.auth import FullName, Password

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Region = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
Status = Literal["pending", "matched", "in_progress", "completed", "cancelled"]


class MentorProfileIn(BaseModel):
    organisation: Short = ""
    bio: Long = ""
    expertise: Annotated[list[HelpType], Field(min_length=1, max_length=5)]
    regions: Annotated[list[Region], Field(min_length=1, max_length=9)]
    availability: Short = ""
    offers: Long = ""


class MentorRegistration(MentorProfileIn):
    email: EmailStr
    password: Password
    full_name: FullName
    accept_privacy: Literal[True]


class MentorProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organisation: str
    bio: str
    expertise: list[str]
    regions: list[str]
    availability: str
    offers: str
    is_approved: bool


class MentorRequestIn(BaseModel):
    help_types: Annotated[list[HelpType], Field(min_length=1, max_length=5)]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
    ]


class Person(BaseModel):
    """The little a mentor and learner see of each other: a first name only."""

    id: uuid.UUID
    first_name: str


class MentorRequestOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_title: str
    status: Status
    stage_key: str
    help_types: list[str]
    description: str
    province: str
    school_name: str
    snapshot: dict[str, Any]
    learner: Person
    mentor: Person | None
    created_at: datetime
    updated_at: datetime


class MentorMessageIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class MentorMessageOut(BaseModel):
    id: uuid.UUID
    sender: Person | None
    mine: bool
    text: str
    created_at: datetime


class StatusUpdate(BaseModel):
    status: Literal["in_progress", "completed"]


class UsageOut(BaseModel):
    """How much of this month's free mentoring a learner has used."""

    used_this_month: int
    free_per_month: int
    extra_credits: int
    remaining: int


class ExpoEventIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    starts_on: date
    location: Short = ""
    province: Short = ""
    url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""


class ExpoEventOut(ExpoEventIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
