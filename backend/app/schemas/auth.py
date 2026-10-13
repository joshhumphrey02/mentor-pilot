from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

# Length is the only composition rule (NIST SP 800-63B): forced symbols and
# digits push people towards predictable patterns without adding real strength.
Password = Annotated[str, Field(min_length=8, max_length=128)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Token = Annotated[str, Field(min_length=20, max_length=200)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: FullName
    # Must be explicitly true: POPIA requires consent to be a positive action.
    accept_privacy: Literal[True]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: Token


class ResetPasswordRequest(BaseModel):
    token: Token
    password: Password


class AuthProvidersResponse(BaseModel):
    google: bool
    # False when accounts are confirmed as they are created (no email server).
    email_verification: bool
