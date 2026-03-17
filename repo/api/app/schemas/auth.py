from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, root_validator


class RegisterIn(BaseModel):
    account: str | None = Field(None, min_length=3, max_length=64)
    email: str | None = Field(None, min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    code: str | None = Field(None, min_length=1, max_length=32)

    @root_validator(pre=True)
    def fill_account(cls, values: dict):
        if not values.get("account") and values.get("email"):
            values["account"] = values.get("email")
        return values


class LoginIn(BaseModel):
    account: str | None = Field(None, min_length=3, max_length=64)
    email: str | None = Field(None, min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @root_validator(pre=True)
    def fill_account(cls, values: dict):
        if not values.get("account") and values.get("email"):
            values["account"] = values.get("email")
        return values


class AuthUserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class AuthTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: AuthUserOut
