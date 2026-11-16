"""Authentication router.

Provides the public endpoints for user registration, login, token refresh, logout, and
retrieving the current authenticated user (``/me``). All state‑changing actions
call the audit logger (currently a placeholder). The refresh token is stored in
an httpOnly ``refresh_token`` cookie as required by the two‑token flow.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Response, Request, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.schemas.auth import (
    BootstrapAdminRequest,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
    PasswordResetMessage,
    DemoPasswordResetRequest,
)
from app.services.auth import register_user, login as service_login, refresh as service_refresh, logout as service_logout, get_me
from app.services.admin import create_admin
from app.services.password_reset import create_reset_request, consume_reset_token, demo_reset_password, reset_email_ready, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = register_user(db, payload)
    db.commit()
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )

@router.post("/bootstrap-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapAdminRequest, db: Session = Depends(get_db)):
    admin = create_admin(db, payload, bootstrap=True)
    db.commit()
    return UserResponse(
        id=str(admin.id),
        email=admin.email,
        role=admin.role,
        is_active=admin.is_active,
        created_at=admin.created_at,
    )

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    token_resp = service_login(response, db, payload)
    db.commit()
    return token_resp

@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    token_resp = service_refresh(response, db, refresh_token)
    return token_resp

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    service_logout(response, db, refresh_token)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/me", response_model=UserResponse)
def me(current_user: "User" = Depends(get_current_user)):
    return get_me(db=None, current_user=current_user)  # db not needed for this simple response


@router.post("/password-reset/request", response_model=PasswordResetMessage)
def request_password_reset(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not reset_email_ready():
        raise HTTPException(status_code=503, detail="Password reset email is not configured")
    reset = create_reset_request(db, str(payload.email))
    db.commit()
    if reset:
        raw_token, recipient = reset
        background_tasks.add_task(send_password_reset_email, recipient, raw_token)
    return PasswordResetMessage(message="If that address is registered, a password reset link will be sent shortly.")


@router.post("/password-reset/confirm", response_model=PasswordResetMessage)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    consume_reset_token(db, payload.token, payload.password, response)
    db.commit()
    return PasswordResetMessage(message="Password updated. Sign in with your new password.")


@router.post("/password-reset/demo", response_model=PasswordResetMessage)
def demo_password_reset(
    payload: DemoPasswordResetRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    demo_reset_password(db, str(payload.email), payload.password, response)
    db.commit()
    return PasswordResetMessage(message="If that demo account exists, its password has been updated.")
