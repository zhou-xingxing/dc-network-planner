from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

UserRole = Literal["administrator", "user"]


class PermittedRegion(BaseModel):
    id: str
    name: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: UserRole
    is_active: bool
    permitted_regions: list[PermittedRegion] = []
    created_at: str
    updated_at: str


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    role: UserRole
    is_active: bool
    permitted_regions: list[PermittedRegion] = []
    permissions: list[str] = []


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUserResponse


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)
    role: UserRole = "user"
    is_active: bool = True
    permitted_region_ids: list[str] = []


class UserUpdate(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    permitted_region_ids: Optional[list[str]] = None


class PasswordReset(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)
