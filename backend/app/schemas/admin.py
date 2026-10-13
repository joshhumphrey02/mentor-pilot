import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.mentoring import MentorProfileOut


class ProviderStatusOut(BaseModel):
    name: str
    active: bool
    configured: bool
    model: str | None
    fast_model: str | None
    # Present only when a health check was requested.
    healthy: bool | None = None
    detail: str | None = None


class TestChatRequest(BaseModel):
    message: Annotated[str, Field(min_length=1, max_length=2000)] = "Say hello in five words."
    task: Literal["chat", "title"] = "chat"


class TestChatResponse(BaseModel):
    provider: str
    model: str
    ok: bool
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None
    error: str | None = None


# --- Admin panels --------------------------------------------------------------

Role = Literal["student", "mentor", "school_admin", "admin"]


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class AdminSchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    province: str
    town: str | None
    is_verified: bool
    learners: int = 0


class AdminSchoolUpdate(BaseModel):
    is_verified: bool


class AdminMentorOut(BaseModel):
    user: AdminUserOut
    profile: MentorProfileOut


class ApproveMentor(BaseModel):
    approved: bool


class AssignMentor(BaseModel):
    mentor_id: uuid.UUID


class UsageRow(BaseModel):
    key: str
    label: str
    calls: int
    input_tokens: int
    output_tokens: int
    # Null when none of the calls could be priced.
    cost_usd: Decimal | None


class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    direction: str
    categories: list[str]
    checked: bool
    content: str
    status: str
    created_at: datetime


class DeliverableIn(BaseModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class StageDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    position: int
    title: str
    goal: str
    deliverables: list[DeliverableIn]
    exit_criteria: list[str]
    instructions: str
    handoff: bool
    version: int


class StageDefinitionUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=400)]
    deliverables: Annotated[list[DeliverableIn], Field(min_length=1, max_length=10)]
    exit_criteria: Annotated[
        list[
            Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
        ],
        Field(min_length=1, max_length=8),
    ]
    instructions: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class CreditGrant(BaseModel):
    user_id: uuid.UUID | None = None
    school_id: uuid.UUID | None = None
    delta: Annotated[int, Field(ge=-100000, le=100000)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
