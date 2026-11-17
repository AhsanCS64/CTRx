"""Private, self-service account preferences for all roles."""

from base64 import b64encode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.core.config import settings
from app.db.models.account_profiles import AccountProfile
from app.db.models.users import User

router = APIRouter(prefix="/profile", tags=["profile"])
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000


MaritalStatus = Literal["single", "married", "other"]
LivingArrangement = Literal["alone", "with_family", "with_partner", "with_roommates", "other"]


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    marital_status: MaritalStatus | None = None
    living_arrangement: LivingArrangement | None = None
    contact_phone: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9]{7,15}$")] | None = None


class ProfileResponse(BaseModel):
    marital_status: MaritalStatus | None = None
    living_arrangement: LivingArrangement | None = None
    display_name: str | None
    contact_phone: str | None
    photo_url: str | None
    appearance: Literal["light", "dark"] = "light"
    theme: Literal["teal", "indigo", "amber", "rose", "forest", "ocean"] = "teal"


class AppearanceUpdate(BaseModel):
    appearance: Literal["light", "dark"]
    theme: Literal["teal", "indigo", "amber", "rose", "forest", "ocean"]


def _profile_response(db: Session, user: User) -> ProfileResponse:
    profile = db.get(AccountProfile, user.id)
    phone = profile.contact_phone_enc if profile else None
    photo = _read_profile_photo(db, user.id)
    if photo is None and profile:
        photo = profile.photo
    return ProfileResponse(
        display_name=profile.display_name if profile else None,
        marital_status=profile.marital_status if profile else None,
        living_arrangement=profile.living_arrangement if profile else None,
        contact_phone=Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(phone).decode() if phone else None,
        photo_url="data:image/jpeg;base64," + b64encode(photo).decode("ascii") if photo else None,
        appearance=profile.appearance if profile else "light",
        theme=profile.theme if profile else "teal",
    )


def _storage_path(storage_key: str) -> Path | None:
    root = Path(settings.STORAGE_DIR).resolve()
    candidate = (root / storage_key).resolve()
    return candidate if candidate.parent == root else None


def _read_profile_photo(db: Session, user_id) -> bytes | None:
    row = db.execute(text("""
        SELECT m.storage_key
        FROM photos p JOIN media_files m ON m.id = p.media_id
        WHERE p.user_id = :user_id AND p.photo_type = 'profile'
          AND p.is_primary AND m.deleted_at IS NULL
        ORDER BY p.created_at DESC LIMIT 1
    """), {"user_id": user_id}).mappings().first()
    if not row:
        return None
    path = _storage_path(row["storage_key"])
    if path is None:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _save(db: Session, user: User, action: str, **values) -> ProfileResponse:
    statement = insert(AccountProfile).values(user_id=user.id, **values)
    db.execute(statement.on_conflict_do_update(index_elements=[AccountProfile.user_id], set_=values))
    log_action(db, action, user.id, user.role, "user", user.id)
    db.commit()
    return _profile_response(db, user)


def _save_profile_photo(db: Session, user: User, photo: bytes) -> ProfileResponse:
    storage_key = f"profile_{uuid4().hex}.jpg"
    path = _storage_path(storage_key)
    if path is None:
        raise HTTPException(500, "Profile photo storage is not available")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(photo)
    old_path = None
    try:
        db.execute(
            insert(AccountProfile)
            .values(user_id=user.id)
            .on_conflict_do_nothing(index_elements=[AccountProfile.user_id])
        )
        previous = db.execute(text("""
            SELECT m.id, m.storage_key
            FROM photos p JOIN media_files m ON m.id = p.media_id
            WHERE p.user_id = :user_id AND p.photo_type = 'profile' AND p.is_primary
            FOR UPDATE OF p, m
        """), {"user_id": user.id}).mappings().first()
        if previous:
            old_path = _storage_path(previous["storage_key"])
            db.execute(text("UPDATE photos SET is_primary = false, updated_at = now() WHERE user_id = :user_id AND photo_type = 'profile' AND is_primary"), {"user_id": user.id})
            db.execute(text("UPDATE media_files SET deleted_at = now() WHERE id = :media_id"), {"media_id": previous["id"]})
        media_id = db.execute(text("""
            INSERT INTO media_files
                (storage_key, original_filename, mime_type, file_size_bytes, width, height, sha256, uploaded_by)
            VALUES (:key, 'profile.jpg', 'image/jpeg', :size, 256, 256, :sha, :user_id)
            RETURNING id
        """), {"key": storage_key, "size": len(photo), "sha": sha256(photo).hexdigest(), "user_id": user.id}).scalar_one()
        db.execute(text("""
            INSERT INTO photos (media_id, user_id, photo_type, is_primary, verification_status)
            VALUES (:media_id, :user_id, 'profile', true, 'unverified')
        """), {"media_id": media_id, "user_id": user.id})
        db.execute(text("UPDATE account_profiles SET photo = NULL WHERE user_id = :user_id"), {"user_id": user.id})
        log_action(db, "profile.photo.update", user.id, user.role, "user", user.id)
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    if old_path:
        old_path.unlink(missing_ok=True)
    return _profile_response(db, user)


def _remove_profile_photo(db: Session, user: User) -> ProfileResponse:
    row = db.execute(text("""
        SELECT m.id, m.storage_key
        FROM photos p JOIN media_files m ON m.id = p.media_id
        WHERE p.user_id = :user_id AND p.photo_type = 'profile' AND p.is_primary
        FOR UPDATE OF p, m
    """), {"user_id": user.id}).mappings().first()
    db.execute(text("UPDATE photos SET is_primary = false, updated_at = now() WHERE user_id = :user_id AND photo_type = 'profile' AND is_primary"), {"user_id": user.id})
    if row:
        db.execute(text("UPDATE media_files SET deleted_at = now() WHERE id = :media_id"), {"media_id": row["id"]})
    db.execute(text("UPDATE account_profiles SET photo = NULL WHERE user_id = :user_id"), {"user_id": user.id})
    log_action(db, "profile.photo.remove", user.id, user.role, "user", user.id)
    db.commit()
    if row:
        path = _storage_path(row["storage_key"])
        if path:
            path.unlink(missing_ok=True)
    return _profile_response(db, user)


def _normalize_photo(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(400, "Choose an image of at most 16 megapixels")
            photo = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (256, 256))
            result = BytesIO()
            photo.save(result, format="JPEG", quality=85)
            return result.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise HTTPException(400, "Choose a valid JPEG, PNG or WebP photo") from exc


@router.get("", response_model=ProfileResponse)
def get_profile(response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return _profile_response(db, user)


@router.put("", response_model=ProfileResponse)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    phone = Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(payload.contact_phone.encode()) if payload.contact_phone else None
    household = payload.model_dump(include={"marital_status", "living_arrangement"}, exclude_unset=True)
    return _save(db, user, "profile.update", display_name=payload.display_name, contact_phone_enc=phone, **household)


@router.put("/photo", response_model=ProfileResponse)
async def upload_photo(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Choose a photo under 4 MB")
        data.extend(chunk)
    photo = await run_in_threadpool(_normalize_photo, bytes(data))
    return await run_in_threadpool(_save_profile_photo, db, user, photo)


@router.put("/appearance", response_model=ProfileResponse)
def update_appearance(payload: AppearanceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _save(db, user, "profile.appearance.update", **payload.model_dump())


@router.delete("/photo", response_model=ProfileResponse)
def remove_photo(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _remove_profile_photo(db, user)

