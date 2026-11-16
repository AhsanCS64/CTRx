import traceback
from app.db.session import SessionLocal
from app.services.certificate_issuance import issue_certificate_flow

APP_ID = "8e6d82ee-9514-4f6e-859f-07fb58b37c58"
db = SessionLocal()
try:
    result = issue_certificate_flow(db, APP_ID)
    print("RESULT:", result)
except Exception:
    traceback.print_exc()
finally:
    db.close()
