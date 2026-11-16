"""Security utilities for the CTRx backend.

- Password hashing using **argon2-cffi**.
- JWT creation/verification for **access** and **refresh** tokens.
- Helper functions for setting/clearing the httpOnly refresh‑cookie.

All secrets are loaded from :class:`app.core.config.Settings` and are never
logged.
"""

import datetime
import enum
from typing import Any, Dict, Optional

from argon2 import PasswordHasher
from jose import JWTError, jwt
from fastapi import Response, Request, HTTPException, status

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing (argon2)
# ---------------------------------------------------------------------------

_pwd_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2 hash for *password*.

    The function raises :class:`argon2.exceptions.HashingError` if hashing fails.
    """
    return _pwd_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify *password* against an Argon2 *hashed* value.

    Returns ``True`` when the password matches, ``False`` otherwise.
    """
    try:
        return _pwd_hasher.verify(hashed, password)
    except Exception:
        return False

# ---------------------------------------------------------------------------
# JWT handling
# ---------------------------------------------------------------------------

_jwt_secret = settings.JWT_SECRET_KEY
_jwt_algorithm = settings.JWT_ALGORITHM or "HS256"

_access_token_expires = datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
_refresh_token_expires = datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def _create_token(data: Dict[str, Any], expires_delta: datetime.timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _jwt_secret, algorithm=_jwt_algorithm)


def create_access_token(subject: str, *, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a short‑lived access token.

    ``subject`` is typically the user ``id``. ``extra_claims`` can contain
    additional fields such as ``role`` that you want readily available in the
    token payload.
    """
    payload: Dict[str, Any] = {"sub": subject, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return _create_token(payload, _access_token_expires)


def create_refresh_token(subject: str, *, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a long‑lived refresh token.

    The payload includes ``type": "refresh"`` so we can distinguish the token
    kind when decoding.
    """
    payload: Dict[str, Any] = {"sub": subject, "type": "refresh"}
    if extra_claims:
        payload.update(extra_claims)
    return _create_token(payload, _refresh_token_expires)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode a JWT and return its payload.

    Raises ``HTTPException`` with ``401`` when the token is invalid, expired or
    the signature does not match.
    """
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

# ---------------------------------------------------------------------------
# FastAPI security scheme (Bearer header)
# ---------------------------------------------------------------------------

def get_token_from_header(request: Request) -> Optional[str]:
    """Extract the JWT from the ``Authorization`` header.

    Returns ``None`` when the header is missing or not a Bearer token.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    scheme, separator, credentials = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer":
        return None
    return credentials

# ---------------------------------------------------------------------------
# Refresh‑cookie helpers (httpOnly, Secure, SameSite=Strict)
# ---------------------------------------------------------------------------

_REFRESH_COOKIE_NAME = "refresh_token"


def set_refresh_cookie(response: Response, token: str) -> None:
    """Attach a httpOnly refresh‑token cookie to *response*.

    In production the ``secure`` flag should be ``True`` – the caller can rely on
    ``settings.APP_ENV`` to decide.
    """
    secure = settings.APP_ENV != "development"
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",  # cookie sent to all paths
        max_age=int(_refresh_token_expires.total_seconds()),
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh‑token cookie.
    """
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path="/")


def get_refresh_token_from_cookie(request: Request) -> Optional[str]:
    return request.cookies.get(_REFRESH_COOKIE_NAME)


class RoleChecker:
    def __init__(self, *allowed_roles: str):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Any) -> Any:
        if getattr(user, "role", None) not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted",
            )
        return user

