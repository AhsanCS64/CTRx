from datetime import datetime
from typing import Tuple, List

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.audit import log_action
from app.schemas.disputes import DisputeCreate, DisputeReview, DisputeResponse


def _verify_party(db: Session, user_id: str, role: str, entity_type: str, entity_id: str):
    """Raise HTTPException(403) if the user is not a party to the given entity.
    Implements the PARTY VERIFICATION RULES.
    """
    if entity_type == "tenancy":
        tenancy = db.get(db_models.Tenancy, entity_id)
        if not tenancy:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenancy not found")
        if user_id not in {str(tenancy.tenant_id), str(tenancy.landlord_id)}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not a party to tenancy")
        return
    if entity_type == "payment_request":
        pr = db.get(db_models.PaymentRequest, entity_id)
        if not pr:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment request not found")
        tenancy = db.get(db_models.Tenancy, pr.tenancy_id)
        if not tenancy:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenancy for payment request not found")
        if user_id not in {str(tenancy.tenant_id), str(tenancy.landlord_id)}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not a party to payment request")
        return
    if entity_type == "ledger_entry":
        le = db.get(db_models.LedgerEntry, entity_id)
        if not le:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found")
        tenancy = db.get(db_models.Tenancy, le.tenancy_id)
        if not tenancy:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenancy for ledger entry not found")
        if user_id not in {str(tenancy.tenant_id), str(tenancy.landlord_id)}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not a party to ledger entry")
        return
    if entity_type == "reliability_score":
        score = db.get(db_models.ReliabilityScore, entity_id)
        if not score:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reliability score not found")
        if str(score.tenant_id) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not a party to reliability score")
        return
    if entity_type == "ric_application":
        app = db.get(db_models.RicApplication, entity_id)
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RIC application not found")
        if str(app.applicant_user_id) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not applicant of RIC application")
        return
    if entity_type == "household":
        # user must have a household_member linked to a tenant_profile belonging to the household
        hm = (
            db.query(db_models.HouseholdMember)
            .join(db_models.Person)
            .join(db_models.TenantProfile, db_models.Person.id == db_models.TenantProfile.person_id)
            .filter(db_models.HouseholdMember.household_id == db_models.Household.id)
            .filter(db_models.TenantProfile.user_id == user_id)
            .first()
        )
        if not hm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not a member of household")
        return
    if entity_type == "certificate":
        cert = db.get(db_models.Certificate, entity_id)
        if not cert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
        # primary holder is linked via household primary holder relationship (assume certificate has household_id)
        household = db.get(db_models.Household, cert.household_id)
        if not household:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household for certificate not found")
        primary = (
            db.query(db_models.HouseholdMember)
            .filter(db_models.HouseholdMember.household_id == household.id, db_models.HouseholdMember.is_primary == True)
            .first()
        )
        if not primary or str(primary.user_id) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not primary holder of household for certificate")
        return
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported entity_type for dispute")


def create_dispute(db: Session, user_id: str, role: str, payload: DisputeCreate) -> DisputeResponse:
    # Verify party
    _verify_party(db, user_id, role, payload.entity_type, str(payload.entity_id))
    dispute = db_models.Dispute(
        raised_by=user_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        reason=payload.reason,
    )
    db.add(dispute)
    db.flush()  # populate id
    log_action(
        db,
        action="dispute_created",
        actor_id=user_id,
        actor_role=role,
        entity_type="dispute",
        entity_id=str(dispute.id),
        metadata=payload.model_dump(mode="json"),
    )
    db.commit()
    return DisputeResponse.model_validate(dispute)


def review_dispute(db: Session, reviewer_user_id: str, reviewer_role: str, dispute_id: str, payload: DisputeReview) -> DisputeResponse:
    if reviewer_role not in {"admin", "government"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin or central government can review disputes")
    dispute = db.get(db_models.Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    # Validate transition
    if dispute.status == "open":
        if payload.status != "under_review":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only transition open->under_review allowed")
    elif dispute.status == "under_review":
        if payload.status not in {"resolved", "rejected"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only resolve or reject from under_review")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dispute already finalised")
    # Apply changes
    dispute.status = payload.status.value
    if payload.status in {DisputeReviewStatus.resolved, DisputeReviewStatus.rejected}:
        dispute.resolution_note = payload.resolution_note
        dispute.resolved_by = reviewer_user_id
        dispute.resolved_at = datetime.utcnow()
    db.add(dispute)
    log_action(
        db,
        action="dispute_reviewed",
        actor_id=reviewer_user_id,
        actor_role=reviewer_role,
        entity_type="dispute",
        entity_id=str(dispute.id),
        metadata=payload.model_dump(),
    )
    db.commit()
    return DisputeResponse.model_validate(dispute)


def list_disputes(db: Session, user_id: str, role: str, skip: int = 0, limit: int = 100) -> Tuple[int, List[DisputeResponse]]:
    query = db.query(db_models.Dispute)
    if role not in {"admin", "government"}:
        query = query.filter(db_models.Dispute.raised_by == user_id)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return total, [DisputeResponse.model_validate(d) for d in items]
