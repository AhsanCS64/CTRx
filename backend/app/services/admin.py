"""Admin service layer for user, area, settings, templates, and audit logs.

All functions expect a SQLAlchemy ``Session`` (e.g. FastAPI ``Depends(get_db)``) and perform
the required CRUD operations while calling ``audit.log_action`` where state changes occur.
"""

from datetime import datetime
import hmac
from typing import Any, List, Optional, Tuple

from sqlalchemy import insert, select, update, and_, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.users import User
from app.db.models.account_profiles import AccountProfile
from app.db.models.official_profiles import OfficialProfile
from app.db.models.areas import Area
from app.db.models.system_settings import SystemSetting
from app.db.models.certificate_templates import CertificateTemplate
from app.db.models.audit_logs import AuditLog
from app.core import security
from app.audit import log_action
from app.core.config import settings

# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_admin(db: Session, payload: Any, bootstrap: bool = False, actor_id: Optional[str] = None) -> User:
    if bootstrap:
        db.execute(text("SELECT pg_advisory_xact_lock(7612451)"))
        if db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar_one():
            raise ValueError("Administrator bootstrap is already complete")
        if not settings.SEED_PASSWORD or not hmac.compare_digest(
            payload.bootstrap_password, settings.SEED_PASSWORD
        ):
            raise ValueError("Invalid bootstrap password")
    elif actor_id is None:
        raise ValueError("An existing administrator is required")

    if db.execute(select(User.id).where(User.email == payload.email)).scalar_one_or_none():
        raise ValueError("Email already registered")
    full_name = payload.full_name.strip()
    if not full_name:
        raise ValueError("Full name is required")

    user = User(
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        role="admin",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(AccountProfile(user_id=user.id, display_name=full_name))
    if actor_id:
        log_action(
            db,
            "admin.create",
            actor_id,
            "admin",
            "users",
            str(user.id),
            {"email": user.email, "full_name": payload.full_name, "bootstrap": False},
        )
    return user

def list_users(
    db: Session,
    search: Optional[str] = None,
    role_filter: Optional[str] = None,
    is_active_filter: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[int, List[User]]:
    """Return total count and a page of ``User`` rows matching the optional filters."""
    stmt = select(User)
    if search:
        stmt = stmt.where(User.email.ilike(f"%{search}%"))
    if role_filter:
        stmt = stmt.where(User.role == role_filter)
    if is_active_filter is not None:
        stmt = stmt.where(User.is_active == is_active_filter)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset(skip).limit(limit)).scalars().all()
    return total, rows


def set_user_active(db: Session, admin_user_id: str, target_user_id: str, is_active: bool) -> User:
    user = db.get(User, target_user_id)
    if not user:
        raise ValueError("User not found")
    user.is_active = is_active
    db.add(user)
    db.flush()
    log_action(db, "user.set_active", admin_user_id, "admin", "users", str(user.id), {"is_active": is_active})
    return user


# ---------------------------------------------------------------------------
# Official creation (government user + profile)
# ---------------------------------------------------------------------------

def create_official(db: Session, admin_user_id: str, payload: Any) -> User:
    # payload expected to have attributes matching OfficialCreate schema
    pwd_hash = security.hash_password(payload.password)
    new_user = User(
        email=payload.email,
        password_hash=pwd_hash,
        role="government",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(new_user)
    db.flush()  # obtain user.id
    profile = OfficialProfile(
        user_id=new_user.id,
        level=payload.level,
        area_id=payload.area_id,
        full_name=payload.full_name,
    )
    db.add(profile)
    db.flush()
    log_action(
        db,
        "official.create",
        admin_user_id,
        "admin",
        "official_profiles",
        str(new_user.id),
        {"level": payload.level, "area_id": payload.area_id},
    )
    return new_user


# ---------------------------------------------------------------------------
# Area management
# ---------------------------------------------------------------------------

def create_area(db: Session, admin_user_id: str, payload: Any) -> Area:
    area = Area(**payload.dict())
    db.add(area)
    db.flush()
    log_action(db, "area.create", admin_user_id, "admin", "areas", str(area.id), payload.model_dump())
    return area


def update_area(db: Session, admin_user_id: str, area_id: int, payload: Any) -> Area:
    area = db.get(Area, area_id)
    if not area:
        raise ValueError("Area not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(area, field, value)
    db.add(area)
    db.flush()
    log_action(db, "area.update", admin_user_id, "admin", "areas", str(area.id), payload.model_dump())
    return area


# ---------------------------------------------------------------------------
# System settings (upsert)
# ---------------------------------------------------------------------------

def get_settings(db: Session) -> List[SystemSetting]:
    return db.execute(select(SystemSetting)).scalars().all()


def update_setting(db: Session, admin_user_id: str, key: str, value: Any) -> SystemSetting:
    stmt = insert(SystemSetting).values(key=key, value=value, updated_by=admin_user_id, updated_at=datetime.utcnow())
    stmt = stmt.on_conflict_do_update(
        index_elements=[SystemSetting.key],
        set_={"value": stmt.excluded.value, "updated_by": admin_user_id, "updated_at": datetime.utcnow()},
    )
    db.execute(stmt)
    db.flush()
    setting = db.get(SystemSetting, key)
    log_action(db, "system_setting.update", admin_user_id, "admin", "system_settings", key, {"value": value})
    return setting


# ---------------------------------------------------------------------------
# Certificate templates
# ---------------------------------------------------------------------------

def list_templates(db: Session) -> List[CertificateTemplate]:
    return db.execute(select(CertificateTemplate)).scalars().all()


def create_template(db: Session, admin_user_id: str, version: str) -> CertificateTemplate:
    tmpl = CertificateTemplate(version=version, name=version)
    db.add(tmpl)
    db.flush()
    log_action(db, "certificate_template.create", admin_user_id, "admin", "certificate_templates", str(tmpl.id), {"version": version})
    return tmpl


def set_default_template(db: Session, admin_user_id: str, template_id: str) -> None:
    # Two separate UPDATE statements as required.
    db.execute(update(CertificateTemplate).values(is_default=False))
    db.execute(update(CertificateTemplate).where(CertificateTemplate.id == template_id).values(is_default=True))
    db.flush()
    log_action(db, "certificate_template.set_default", admin_user_id, "admin", "certificate_templates", template_id, {"is_default": True})


# ---------------------------------------------------------------------------
# Audit log viewer
# ---------------------------------------------------------------------------

def get_audit_logs(
    db: Session,
    filters: Any,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[int, List[AuditLog]]:
    stmt = select(AuditLog)
    if filters.actor_id:
        stmt = stmt.where(AuditLog.actor_id == filters.actor_id)
    if filters.action:
        stmt = stmt.where(AuditLog.action == filters.action)
    if filters.entity_type:
        stmt = stmt.where(AuditLog.entity_type == filters.entity_type)
    if filters.entity_id:
        stmt = stmt.where(AuditLog.entity_id == filters.entity_id)
    if filters.date_from:
        stmt = stmt.where(AuditLog.created_at >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(AuditLog.created_at <= filters.date_to)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset(skip).limit(limit)).scalars().all()
    return total, rows
