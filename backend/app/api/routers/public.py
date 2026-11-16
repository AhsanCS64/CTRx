from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/statistics")
def statistics(db: Session = Depends(get_db)):
    return dict(db.execute(text("""
        SELECT
          (SELECT count(*) FROM users WHERE is_active = true) AS registered_users,
          (SELECT count(*) FROM properties) AS properties,
          (SELECT count(*) FROM tenancies WHERE status = 'active') AS active_tenancies
    """)).mappings().one())
