"""Payments router – endpoints for payment requests and ledger.

Endpoints
---------
- POST   /payment-requests/               → create payment request (landlord)
- GET    /payment-requests/               → list payment requests (role‑based)
- POST   /payment-requests/{id}/decide    → report/decline payment (tenant)
- POST   /payment-requests/{id}/confirm   → confirm receipt (landlord)
- POST   /ledger/corrections              → create a correction entry
- GET    /ledger/                         → get ledger with running balance
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.schemas.payments import (
    CorrectionCreate,
    LedgerEntryResponse,
    LedgerWithBalance,
    PaymentRequestCreate,
    PaymentRequestDecide,
    PaymentRequestResponse,
)
from app.services.payments import (
    create_correction,
    create_payment_request,
    confirm_payment_receipt,
    decide_payment_request,
    get_ledger,
    get_payment_requests,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/payment-requests/",
    response_model=PaymentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_payment_request(
    payload: PaymentRequestCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role != "landlord":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only landlords can create payment requests",
        )
    pr = create_payment_request(db, current_user.id, payload, role="landlord")
    return PaymentRequestResponse.model_validate(pr)


@router.get("/payment-requests/", response_model=list[PaymentRequestResponse])
def list_payment_requests(
    tenancy_id: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    prs = get_payment_requests(
        db,
        user_id=current_user.id,
        role=current_user.role,
        tenancy_id=tenancy_id,
    )
    return [PaymentRequestResponse.model_validate(p) for p in prs]


@router.post(
    "/payment-requests/{request_id}/decide",
    response_model=PaymentRequestResponse,
)
def decide_request(
    request_id: str,
    payload: PaymentRequestDecide,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Tenants report or decline; only landlords confirm receipt.
    if current_user.role != "tenant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenants may decide payment requests",
        )
    pr = decide_payment_request(
        db,
        decider_user_id=current_user.id,
        request_id=request_id,
        payload=payload,
        role=current_user.role,
    )
    return PaymentRequestResponse.model_validate(pr)


@router.post(
    "/payment-requests/{request_id}/confirm",
    response_model=PaymentRequestResponse,
)
def confirm_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role != "landlord":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only landlords may confirm receipt of payment",
        )
    pr = confirm_payment_receipt(db, current_user.id, request_id)
    return PaymentRequestResponse.model_validate(pr)


@router.post(
    "/ledger/corrections",
    response_model=LedgerEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_correction(
    payload: CorrectionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    entry = create_correction(db, current_user.id, current_user.role, payload)
    return LedgerEntryResponse.model_validate(entry)


@router.get("/ledger/", response_model=LedgerWithBalance)
def get_ledger_endpoint(
    tenancy_id: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_ledger(db, user_id=current_user.id, role=current_user.role, tenancy_id=tenancy_id)
