"""Pydantic schemas for the Admin console.

Provides request and response models for user management, areas, system settings,
certificate templates, and audit log querying.
"""

from datetime import datetime
from typing import List, Optional, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator, ConfigDict

# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
class UserListItem(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class UserListResponse(BaseModel):
    total: int
    users: List[UserListItem]

    model_config = ConfigDict(from_attributes=True)

class UserUpdateActive(BaseModel):
    is_active: bool

class AdminCreate(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    full_name: str

# ---------------------------------------------------------------------------
# Official creation (government user + profile)
# ---------------------------------------------------------------------------
class OfficialCreate(BaseModel):
    email: str
    password: str
    full_name: str
    level: str  # "local" or "central"
    area_id: Optional[int] = None

    @validator("level")
    def validate_level(cls, v: str) -> str:
        if v not in {"local", "central"}:
            raise ValueError("level must be 'local' or 'central'")
        return v

# ---------------------------------------------------------------------------
# Area management
# ---------------------------------------------------------------------------
class AreaBase(BaseModel):
    division: str
    division_code: str = Field(..., min_length=2, max_length=2)
    district: str
    district_code: str = Field(..., min_length=2, max_length=2)
    name: str
    upazila_code: str = Field(..., min_length=3, max_length=3)

class AreaCreate(AreaBase):
    pass

class AreaUpdate(BaseModel):
    division: Optional[str] = None
    division_code: Optional[str] = None
    district: Optional[str] = None
    district_code: Optional[str] = None
    name: Optional[str] = None
    upazila_code: Optional[str] = None

# ---------------------------------------------------------------------------
# System settings
# ---------------------------------------------------------------------------
class SystemSettingUpdate(BaseModel):
    value: Any

# ---------------------------------------------------------------------------
# Certificate templates
# ---------------------------------------------------------------------------
class CertificateTemplateCreate(BaseModel):
    version: str
    name: Optional[str] = None
    renderer: Optional[str] = None
    config: Optional[dict] = None

# ---------------------------------------------------------------------------
# Audit log querying
# ---------------------------------------------------------------------------
class AuditLogResponse(BaseModel):
    id: int
    actor_id: UUID
    actor_role: str
    action: str
    entity_type: str
    entity_id: UUID
    metadata: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditLogFilter(BaseModel):
    actor_id: Optional[UUID] = None
    action: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    @validator("date_to")
    def check_dates(cls, v, values):
        if v and values.get("date_from") and v < values["date_from"]:
            raise ValueError("date_to must be after date_from")
        return v
