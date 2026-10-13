import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.schemas.auth import FullName

Language = Literal["en", "af", "xh"]
LearningStyle = Literal["visual", "hands_on", "reading", "step_by_step"]
EducationLevel = Literal["high_school", "university", "other"]
Interest = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=2, max_length=40)
]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
SchoolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    province: str
    town: str | None
    is_verified: bool


class SchoolCreate(BaseModel):
    name: SchoolName
    province: ShortText
    town: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None


class StudentProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    school: SchoolOut | None
    education_level: str
    grade: str | None
    province: str | None
    interests: list[str]
    learning_style: str | None
    date_of_birth: date | None
    guardian_consent: bool
    guardian_email: str | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    preferred_language: str
    is_verified: bool
    is_onboarded: bool
    has_password: bool
    privacy_accepted: bool
    created_at: datetime
    student_profile: StudentProfileOut | None


class UserUpdate(BaseModel):
    full_name: FullName | None = None
    preferred_language: Language | None = None


class OnboardingRequest(BaseModel):
    full_name: FullName
    date_of_birth: date
    # Exactly one of these: pick a school from search, or add a new one.
    school_id: uuid.UUID | None = None
    new_school: SchoolCreate | None = None
    education_level: EducationLevel = "high_school"
    grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    province: ShortText
    interests: Annotated[list[Interest], Field(min_length=1, max_length=12)]
    learning_style: LearningStyle
    preferred_language: Language = "en"
    guardian_consent: bool = False
    guardian_email: EmailStr | None = None
    # Only needed for accounts that have not accepted it yet (Google sign-in).
    accept_privacy: bool = False

    @model_validator(mode="after")
    def _one_school(self) -> Self:
        if self.school_id is not None and self.new_school is not None:
            raise ValueError("Choose an existing school or add a new one, not both.")
        return self


class DeleteAccountRequest(BaseModel):
    # Typed by the user, so a stray click or replayed request cannot delete an account.
    confirm: Literal["DELETE"]
    password: Annotated[str, Field(max_length=128)] | None = None
