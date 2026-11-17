"""Pydantic schemas for authentication endpoints.

- ``RegisterRequest``: data required to create a new user.
- ``LoginRequest``: credentials for login.
- ``TokenResponse``: access token returned after login/refresh.
- ``UserResponse``: minimal user info (id, email, role, is_active).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict

class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email address (CITEXT).")
    password: str = Field(..., min_length=8, description="Plain‑text password.")
    full_name: str = Field(..., description="Full name of the user.")
    role: str = Field(..., description="One of: tenant, landlord, government, admin.")

    @validator("role")
    def validate_role(cls, v: str) -> str:
        allowed = {"tenant", "landlord", "government", "admin"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v

class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address.")
    password: str = Field(..., description="Plain‑text password.")

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=128)
    password: str = Field(..., min_length=8, max_length=128)

class PasswordResetMessage(BaseModel):
    message: str

class DemoPasswordResetRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class BootstrapAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    bootstrap_password: str = Field(..., min_length=1)

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field(default="bearer")

class UserResponse(BaseModel):
    id: str = Field(..., description="User UUID.")
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
