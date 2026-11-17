import os
import json
import hashlib
import hmac
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal
from app.core.config import settings
from app.scripts.seed_areas import insert_areas
from argon2 import PasswordHasher

logger = logging.getLogger(__name__)
ph = PasswordHasher()

# Load backend/.env so SEED_PASSWORD (and DATABASE_URL) are available to os.getenv.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

# Helper to hash passwords using Argon2
def hash_password(pw: str) -> str:
    return ph.hash(pw)

# Helper to compute HMAC for identity numbers
def compute_hmac(nid: str) -> str:
    # settings.HMAC_SECRET must be set (validated in Settings)
    return hmac.new(settings.HMAC_SECRET.encode(), nid.encode(), hashlib.sha256).hexdigest()

def seed():
    """Idempotent seed script for CTRx.
    Run with: python -m app.scripts.seed
    """
    db = SessionLocal()
    try:
        # ---- AREAS (DIVISION/DISTRICT/UPAZILA) ----
        insert_areas(db)
        logger.info("Areas seeded")

        # ---- AMENITIES ----
        amenities = [
            "Parking",
            "Generator",
            "Lift/Elevator",
            "Gas",
            "Security Guard",
            "Intercom",
            "Rooftop Access",
        ]
        for amen in amenities:
            code = amen.lower().replace(" ", "_").replace("/", "_")
            stmt = text(
                """
                INSERT INTO amenities (code, label) VALUES (:code, :label) ON CONFLICT (code) DO NOTHING
                """
            )
            db.execute(stmt, {"code": code, "label": amen})
        logger.info("Amenities seeded")

        # ---- CERTIFICATE TEMPLATES ----
        stmt = text(
            """
            INSERT INTO certificate_templates (code, version, name, is_default)
            VALUES ('ric-standard', 1, 'v1-placeholder', true)
            ON CONFLICT (code, version) DO NOTHING
            """
        )
        db.execute(stmt)
        logger.info("Certificate templates seeded")

        # ---- USERS ----
        seed_password = os.getenv("SEED_PASSWORD")
        if not seed_password:
            raise RuntimeError("SEED_PASSWORD environment variable not set")
        pw_hash = hash_password(seed_password)

        user_data = [
            # email, role, extra_profile_sql (insert into other tables), person json etc.
            ("admin@ctrx.test", "admin", None),
            ("central@ctrx.test", "government", "INSERT INTO official_profiles (user_id, level, area_id, full_name) SELECT u.id, 'central', NULL, 'Central Official' FROM users u WHERE u.email = :email ON CONFLICT (user_id) DO NOTHING"),
            ("local1@ctrx.test", "government", "INSERT INTO official_profiles (user_id, level, area_id, full_name) SELECT u.id, 'local', a.id, 'Local Official' FROM users u, areas a WHERE u.email = :email AND a.name = 'Dhanmondi' ON CONFLICT (user_id) DO NOTHING"),
            ("tenant1@ctrx.test", "tenant", [
                "INSERT INTO persons (full_name, identity_number_enc, identity_number_hmac) VALUES ('Sample Tenant One', NULL, :hmac_val) ON CONFLICT (identity_number_hmac) DO NOTHING",
                "INSERT INTO tenant_profiles (user_id, person_id, full_name) SELECT u.id, p.id, 'Sample Tenant One' FROM users u, persons p WHERE u.email = :email AND p.full_name = 'Sample Tenant One' AND p.identity_number_hmac = :hmac_val ON CONFLICT (user_id) DO NOTHING",
            ]),
            ("tenant2@ctrx.test", "tenant", [
                "INSERT INTO persons (full_name, identity_number_enc, identity_number_hmac) VALUES ('Sample Tenant Two', NULL, :hmac_val) ON CONFLICT (identity_number_hmac) DO NOTHING",
                "INSERT INTO tenant_profiles (user_id, person_id, full_name) SELECT u.id, p.id, 'Sample Tenant Two' FROM users u, persons p WHERE u.email = :email AND p.full_name = 'Sample Tenant Two' AND p.identity_number_hmac = :hmac_val ON CONFLICT (user_id) DO NOTHING",
            ]),
            ("landlord1@ctrx.test", "landlord", "INSERT INTO landlord_profiles (user_id, full_name) VALUES ((SELECT id FROM users WHERE email = :email), 'Sample Landlord One') ON CONFLICT (user_id) DO NOTHING"),
        ]
        for email, role, extra_sql in user_data:
            stmt = text(
                """
                INSERT INTO users (email, role, password_hash)
                VALUES (:email, :role, :pw_hash)
                ON CONFLICT (email) DO NOTHING
                """
            )
            db.execute(stmt, {"email": email, "role": role, "pw_hash": pw_hash})
            if extra_sql:
                # For tenants we need HMAC value; compute if needed.
                params = {"email": email}
                if isinstance(extra_sql, list):
                    if any("identity_number_hmac" in s for s in extra_sql):
                        nid = f"SAMPLE-NID-{email.split('@')[0].split('tenant')[-1].upper()}"
                        params["hmac_val"] = compute_hmac(nid)
                    for statement in extra_sql:
                        db.execute(text(statement), params)
                else:
                    if "identity_number_hmac" in extra_sql:
                        nid = f"SAMPLE-NID-{email.split('@')[0].split('tenant')[-1].upper()}"
                        params["hmac_val"] = compute_hmac(nid)
                    db.execute(text(extra_sql), params)
        logger.info("Users and related profiles seeded")

        db.commit()
        print("Seed complete.")
    except Exception as e:
        db.rollback()
        logger.exception("Seeding failed")
        raise

if __name__ == "__main__":
    seed()
