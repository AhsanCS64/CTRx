"""Admin API router.

All endpoints require an authenticated user with role='admin'.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from app.db.models.areas import Area
from app.db.models.users import User
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.security import RoleChecker
from app.db.models.users import User
from app.schemas.admin import (
    UserListItem,
    UserListResponse,
    UserUpdateActive,
    AdminCreate,
    OfficialCreate,
    AreaCreate,
    AreaUpdate,
    SystemSettingUpdate,
    CertificateTemplateCreate,
    AuditLogResponse,
    AuditLogFilter,
)
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])

admin_role = RoleChecker("admin")

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@router.get("/users/", response_model=UserListResponse)
def list_users(
    search: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    total, users = admin_service.list_users(db, search, role, is_active, skip, limit)
    return UserListResponse(total=total, users=users)

@router.patch("/users/{user_id}/active", response_model=UserListItem)
def set_user_active(
    user_id: str,
    payload: UserUpdateActive,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    user = admin_service.set_user_active(db, str(current_user.id), user_id, payload.is_active)
    return user

# ---------------------------------------------------------------------------
# Officials (government users)
# ---------------------------------------------------------------------------
@router.post("/officials", response_model=UserListItem)
def create_official(
    payload: OfficialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    official = admin_service.create_official(db, str(current_user.id), payload)
    db.commit()
    return official

@router.post("/admins", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    admin = admin_service.create_admin(db, payload, actor_id=str(current_user.id))
    db.commit()
    return admin

# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------
@router.get("/areas/")
def list_areas(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    admin_role(current_user)
    return db.execute(select(Area)).scalars().all()

@router.post("/areas/")
def create_area(
    payload: AreaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    return admin_service.create_area(db, str(current_user.id), payload)

@router.patch("/areas/{area_id}")
def update_area(
    area_id: int,
    payload: AreaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    return admin_service.update_area(db, str(current_user.id), area_id, payload)

# ---------------------------------------------------------------------------
# System Settings
# ---------------------------------------------------------------------------
@router.get("/settings/")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    admin_role(current_user)
    return admin_service.get_settings(db)

@router.patch("/settings/{key}")
def update_setting(
    key: str,
    payload: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    return admin_service.update_setting(db, str(current_user.id), key, payload.value)

# ---------------------------------------------------------------------------
# Certificate Templates
# ---------------------------------------------------------------------------
@router.get("/templates/")
def list_templates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    admin_role(current_user)
    return admin_service.list_templates(db)

@router.post("/templates/")
def create_template(
    payload: CertificateTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    return admin_service.create_template(db, str(current_user.id), payload.version)

@router.post("/templates/{template_id}/set-default")
def set_default_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    admin_service.set_default_template(db, str(current_user.id), template_id)
    return {"detail": "default set"}

# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------
@router.get("/audit-logs/", response_model=list[AuditLogResponse])
def get_audit_logs(
    filters: AuditLogFilter = Depends(),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin_role(current_user)
    total, logs = admin_service.get_audit_logs(db, filters, skip, limit)
    return logs
