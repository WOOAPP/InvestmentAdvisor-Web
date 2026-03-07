"""Auth request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str = ""

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Hasło musi mieć co najmniej 8 znaków")
        if not any(c.isdigit() or not c.isalpha() for c in v):
            raise ValueError("Hasło musi zawierać co najmniej jedną cyfrę lub znak specjalny")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 50:
            raise ValueError("Nazwa wyświetlana może mieć maksymalnie 50 znaków")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    is_admin: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
