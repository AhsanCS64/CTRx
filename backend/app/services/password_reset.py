"""Single-use, short-lived password reset links delivered by configured SMTP."""

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import logging
import secrets
import smtplib
import ssl
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote, urlsplit

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.audit import log_action
from app.core.config import settings
from app.core.security import clear_refresh_cookie, hash_password
from app.db.models.password_reset_tokens import PasswordResetToken
from app.db.models.users import User

logger = logging.getLogger(__name__)
MAX_REQUESTS_PER_EMAIL_PER_HOUR = 3


def email_digest(email: str) -> str:
    normalized = email.strip().casefold().encode("utf-8")
    value = b"ctrx-password-reset-email:" + normalized
    return hmac.new(settings.HMAC_SECRET.encode("utf-8"), value, hashlib.sha256).hexdigest()


def create_reset_request(db: Session, email: str) -> tuple[str, str] | None:
    """Persist an attempt for throttling; only return a token for an eligible account."""
    now = datetime.now(timezone.utc)
    digest = email_digest(email)
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.created_at < now - timedelta(days=30)))
    recent_requests = db.scalar(
        select(func.count()).select_from(PasswordResetToken).where(
            PasswordResetToken.email_digest == digest,
            PasswordResetToken.created_at >= now - timedelta(hours=1),
        )
    ) or 0
    user = db.scalar(select(User).where(User.email == email.strip()))

    raw_token = secrets.token_urlsafe(32) if user and user.is_active and recent_requests < MAX_REQUESTS_PER_EMAIL_PER_HOUR else None
    reset_row = PasswordResetToken(
        user_id=user.id if raw_token and user else None,
        email_digest=digest,
        token_digest=hashlib.sha256(raw_token.encode("ascii")).hexdigest() if raw_token else None,
        created_at=now,
        expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
    )
    db.add(reset_row)
    db.flush()
    return (raw_token, user.email) if raw_token and user else None


def consume_reset_token(db: Session, raw_token: str, new_password: str, response) -> None:
    digest = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
    now = datetime.now(timezone.utc)
    reset_row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_digest == digest,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        ).with_for_update()
    )
    user = db.get(User, reset_row.user_id) if reset_row and reset_row.user_id else None
    if not reset_row or not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid or expired. Request a new one.")

    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    clear_refresh_cookie(response)
    log_action(db, "auth.password_reset", str(user.id), user.role, "user", str(user.id))


def demo_reset_password(db: Session, email: str, new_password: str, response) -> None:
    """Direct password replacement for disposable interview-demo accounts only."""
    if not settings.DEMO_ALLOW_UNVERIFIED_PASSWORD_RESET:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo reset is disabled")

    user = db.scalar(select(User).where(User.email == email.strip()))
    if user and user.is_active:
        user.password_hash = hash_password(new_password)
        user.token_version += 1
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=datetime.now(timezone.utc))
        )
        log_action(
            db,
            "auth.demo_password_reset",
            entity_type="user",
            entity_id=str(user.id),
            metadata={"mode": "unverified_demo_reset"},
        )
    clear_refresh_cookie(response)


def reset_email_ready() -> bool:
    if not settings.password_reset_email_configured:
        return False
    if settings.APP_ENV != "development":
        parsed = urlsplit(settings.FRONTEND_BASE_URL)
        if parsed.scheme != "https" or not parsed.netloc:
            return False
        if not settings.RESEND_API_KEY and not settings.SMTP_USE_SSL and not settings.SMTP_STARTTLS:
            return False
    return True


def send_password_reset_email(recipient: str, raw_token: str) -> None:
    """Send the reset link. Delivery errors are logged without logging the address or token."""
    try:
        base_url = settings.FRONTEND_BASE_URL.rstrip("/")
        reset_url = f"{base_url}/?reset_token={quote(raw_token, safe='')}"
        message_text = (
            "We received a request to reset your CTRx password.\n\n"
            f"Use this one-time link within {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes:\n"
            f"{reset_url}\n\n"
            "If you did not request this reset, you can ignore this message."
        )

        sender = settings.EMAIL_FROM or settings.SMTP_FROM_EMAIL
        if settings.RESEND_API_KEY:
            api_request = Request(
                "https://api.resend.com/emails",
                data=json.dumps({
                    "from": sender,
                    "to": [recipient],
                    "subject": "Reset your CTRx password",
                    "text": message_text,
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(api_request, timeout=15) as api_response:
                if not 200 <= api_response.status < 300:
                    raise RuntimeError(f"Resend API returned HTTP {api_response.status}")
            return

        message = EmailMessage()
        message["Subject"] = "Reset your CTRx password"
        message["From"] = sender
        message["To"] = recipient
        message.set_content(message_text)

        context = ssl.create_default_context()
        if settings.SMTP_USE_SSL:
            client = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=context)
        else:
            client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        with client as smtp:
            if settings.SMTP_STARTTLS and not settings.SMTP_USE_SSL:
                smtp.starttls(context=context)
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (HTTPError, URLError) as exc:
        logger.error("Password reset email delivery failed (%s)", type(exc).__name__)
    except Exception as exc:  # Delivery errors must not expose account existence or token data.
        logger.error("Password reset email delivery failed (%s)", type(exc).__name__)
