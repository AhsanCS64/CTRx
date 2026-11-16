"""Authentication service functions.

- ``register_user``: creates a ``User`` row (hashes password with Argon2).
- ``authenticate_user``: verifies credentials and returns the ``User`` instance.
- ``login``: issues an access token and a refresh token (httpOnly cookie).
- ``refresh``: validates the refresh token cookie, issues a new access token.
- ``logout``: clears the refresh‑token cookie.

All state‑changing actions should call ``audit.log_action`` (TODO placeholder) to record audit logs.
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.security import (
    clear_refresh_cookie,
    create_access_token,
    create_refresh_token,
    hash_password,
    set_refresh_cookie,
    verify_password,
)
from app.db.models.landlord_profiles import LandlordProfile
from app.db.models.users import User
from app.db.models.persons import Person
from app.db.models.tenant_profiles import TenantProfile
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse


# Placeholder audit logger – will be replaced by a proper implementation.
def _audit_log(action: str, user_id: Optional[str] = None, **metadata):
    # In a real implementation this would write to ``audit_logs``.
    pass

def register_user(db: Session, payload: RegisterRequest) -> User:
    # Check for existing email
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Hash password
    pwd_hash = hash_password(payload.password)

    # Create user row
    new_user = User(
        email=payload.email,
        password_hash=pwd_hash,
        role=payload.role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(new_user)
    db.flush()  # obtain generated PK
    if payload.role == "landlord":
        db.add(LandlordProfile(user_id=new_user.id, full_name=payload.full_name))
    elif payload.role == "tenant":
        person = Person(full_name=payload.full_name)
        db.add(person)
        db.flush()
        db.add(TenantProfile(user_id=new_user.id, person_id=person.id, full_name=payload.full_name))
    _audit_log("user.register", user_id=str(new_user.id), role=payload.role)
    return new_user

def authenticate_user(db: Session, payload: LoginRequest) -> User:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    return user

def login(response: Response, db: Session, payload: LoginRequest) -> TokenResponse:
    user = authenticate_user(db, payload)
    access = create_access_token(str(user.id), extra_claims={"role": user.role, "ver": user.token_version})
    refresh = create_refresh_token(str(user.id), extra_claims={"ver": user.token_version})
    set_refresh_cookie(response, refresh)
    _audit_log("user.login", user_id=str(user.id))
    return TokenResponse(access_token=access)

def refresh(response: Response, db: Session, refresh_token: Optional[str]) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    payload = security.decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    if payload.get("ver", 0) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    # Issue new access token
    access = create_access_token(str(user.id), extra_claims={"role": user.role, "ver": user.token_version})
    # Refresh token stays the same (stateless) – optionally rotate, but we keep it simple.
    _audit_log("user.refresh", user_id=str(user.id))
    return TokenResponse(access_token=access)

def logout(response: Response, db: Session, refresh_token: Optional[str]) -> None:
    # If a refresh token is present, we could invalidate it via a revocation list (not implemented).
    clear_refresh_cookie(response)
    # No audit for logout to avoid leaking token existence, but could be added.
    return

def get_me(db: Session, current_user: User) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
