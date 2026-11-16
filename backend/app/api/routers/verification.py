"""Public verification endpoint for RIC certificates.

GET /api/verify/{token} calls the PostgreSQL function ``verify_ric`` and returns
the result as ``VerificationResponse``. No authentication is required; the
function only reveals the RIC number, status, and issuance/expiry dates.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps import get_db
from app.schemas.ric import VerificationResponse

router = APIRouter(prefix="/verify", tags=["verification"])

@router.get("/{token}", response_model=VerificationResponse)
def verify(token: str, db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT * FROM verify_ric(:t)"), {"t": token}).mappings().first()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Verification failed") from exc
    if not result:
        raise HTTPException(status_code=404, detail="Token not found")
    # result columns: ric_number, status, issued_at, expires_at
    return VerificationResponse(
        ric_number=result["ric_number"],
        status=result["status"],
        issued_at=result["issued_at"],
        expires_at=result["expires_at"],
    )
