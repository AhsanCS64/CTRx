"""Idempotently seed Bangladesh divisions, districts and upazila areas."""

import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


AREA_DATA = Path(__file__).resolve().parents[1] / "data" / "bangladesh_areas.json"


def insert_areas(db: Session) -> int:
    rows = json.loads(AREA_DATA.read_text(encoding="utf-8"))
    if len(rows) != 501:
        raise ValueError(f"Expected 501 area rows in {AREA_DATA}, found {len(rows)}")
    result = db.execute(
        text("""
            INSERT INTO areas (division, division_code, district, district_code, name, upazila_code)
            VALUES (:division, :division_code, :district, :district_code, :name, :upazila_code)
            ON CONFLICT DO NOTHING
        """),
        rows,
    )
    return result.rowcount or 0


def seed_areas() -> int:
    db = SessionLocal()
    try:
        inserted = insert_areas(db)
        db.commit()
        print(f"Area seed complete: inserted {inserted} rows.")
        return inserted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_areas()
