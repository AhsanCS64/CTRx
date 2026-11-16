"""Private, self-service account preferences for all roles."""

from base64 import b64encode
from io import BytesIO
from typing import Annotated, Literal

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.dialects.postgresql import insert
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


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    contact_phone: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9]{7,15}$")] | None = None


class ProfileResponse(BaseModel):
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
    if profile is None:
        return ProfileResponse(display_name=None, contact_phone=None, photo_url=None)
    phone = profile.contact_phone_enc
    photo = profile.photo
    return ProfileResponse(
        display_name=profile.display_name,
        contact_phone=Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(phone).decode() if phone else None,
        photo_url="data:image/jpeg;base64," + b64encode(photo).decode("ascii") if photo else None,
        appearance=profile.appearance,
        theme=profile.theme,
    )


def _save(db: Session, user: User, action: str, **values) -> ProfileResponse:
    statement = insert(AccountProfile).values(user_id=user.id, **values)
    db.execute(statement.on_conflict_do_update(index_elements=[AccountProfile.user_id], set_=values))
    log_action(db, action, user.id, user.role, "user", user.id)
    db.commit()
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
    return _save(db, user, "profile.update", display_name=payload.display_name, contact_phone_enc=phone)


@router.put("/photo", response_model=ProfileResponse)
async def upload_photo(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Choose a photo under 4 MB")
        data.extend(chunk)
    photo = await run_in_threadpool(_normalize_photo, bytes(data))
    return await run_in_threadpool(_save, db, user, "profile.photo.update", photo=photo)


@router.put("/appearance", response_model=ProfileResponse)
def update_appearance(payload: AppearanceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _save(db, user, "profile.appearance.update", **payload.model_dump())


@router.delete("/photo", response_model=ProfileResponse)
def remove_photo(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _save(db, user, "profile.photo.remove", photo=None)

