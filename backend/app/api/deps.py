"""FastAPI dependencies for database sessions and authentication.

- ``get_db``: yields a SQLAlchemy ``Session`` (imported from ``app.db.session``).
- ``get_current_user``: validates the Bearer access token, loads the ``User``
  model, and returns it. Raises 401 if token missing/invalid or user inactive.
- ``require_role``: dependency that checks the user has one of the allowed
  roles.
- ``require_official_level``: checks a government user has the required official
  level (local or central) and, for ``local``, that the ``area_id`` matches the
  request's ``area_id`` when applicable.
"""

from typing import Iterator, List, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import security, config
from app.db.session import SessionLocal
from app.db.models import users as user_models
from app.db.models import official_profiles as official_models

# ---------------------------------------------------------------------------
# Database session dependency (re‑export for easy import in routers)
# ---------------------------------------------------------------------------

def get_db() -> Iterator[Session]:
    """FastAPI dependency that provides a database session.

    Usage::

        def some_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> user_models.User:
    token = security.get_token_from_header(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = security.decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(user_models.User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("ver", 0) != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(allowed_roles: List[str]):
    """Dependency factory that ensures the current user has one of ``allowed_roles``.
    """

    async def dependency(user: user_models.User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user.role}' not allowed",
            )
        return user

    return dependency


def require_official_level(level: Optional[str] = None, area_id: Optional[int] = None):
    """Ensure the current user is a government official with the specified *level*.

    For ``local`` level, optionally verify that the official's ``area_id`` matches
    the provided ``area_id`` (used by some endpoints).
    """

    async def dependency(user: user_models.User = Depends(get_current_user), db: Session = Depends(get_db)):
        if user.role != "government":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Government role required",
            )
        profile = db.get(official_models.OfficialProfile, user.id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Official profile missing",
            )
        if level is not None and profile.level != level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Official level '{profile.level}' does not match required '{level}'",
            )
        if level == "local" and area_id is not None and profile.area_id != area_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Local official out of area",
            )
        return profile

    return dependency
