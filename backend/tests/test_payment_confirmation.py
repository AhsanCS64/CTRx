from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.models.ledger_entries import LedgerEntry
from app.services import payments
from app.schemas.payments import PaymentRequestDecide


class FakeSession:
    def __init__(self, payment_request, tenancy):
        self.records = {
            payments.PaymentRequest: payment_request,
            payments.Tenancy: tenancy,
        }
        self.added = []

    def get(self, model, _record_id):
        return self.records.get(model)

    def add(self, record):
        self.added.append(record)

    def commit(self):
        pass

    def refresh(self, _record):
        pass


def create_payment_records(status="pending"):
    tenant_id = uuid4()
    landlord_id = uuid4()
    tenancy_id = uuid4()
    payment_request = SimpleNamespace(
        id=uuid4(),
        tenancy_id=tenancy_id,
        requested_by=landlord_id,
        amount=Decimal("1250.00"),
        period_month=date(2026, 11, 1),
        paid_on=date(2026, 11, 18),
        status=status,
        payment_method=None,
        note=None,
        decided_by=None,
        decided_at=None,
    )
    tenancy = SimpleNamespace(tenant_id=tenant_id, landlord_id=landlord_id)
    return payment_request, tenancy, tenant_id, landlord_id


def test_tenant_payment_report_does_not_create_ledger_entry(monkeypatch):
    payment_request, tenancy, tenant_id, _ = create_payment_records()
    db = FakeSession(payment_request, tenancy)
    monkeypatch.setattr(payments, "log_action", lambda *_args, **_kwargs: None)

    result = payments.submit_payment_report(
        db,
        tenant_user_id=tenant_id,
        request_id=payment_request.id,
        payment_method="Bank transfer",
        note="Ref 123",
    )

    assert result.status == "submitted"
    assert result.payment_method == "Bank transfer"
    assert result.note == "Ref 123"
    assert not any(isinstance(record, LedgerEntry) for record in db.added)


def test_generic_tenant_acceptance_only_submits_payment_report(monkeypatch):
    payment_request, tenancy, tenant_id, _ = create_payment_records()
    db = FakeSession(payment_request, tenancy)
    monkeypatch.setattr(payments, "log_action", lambda *_args, **_kwargs: None)

    result = payments.decide_payment_request(
        db,
        decider_user_id=tenant_id,
        request_id=payment_request.id,
        payload=PaymentRequestDecide(decision="accepted"),
    )

    assert result.status == "submitted"
    assert not any(isinstance(record, LedgerEntry) for record in db.added)


def test_only_owning_landlord_can_confirm_and_create_ledger(monkeypatch):
    payment_request, tenancy, _, landlord_id = create_payment_records(status="submitted")
    db = FakeSession(payment_request, tenancy)
    monkeypatch.setattr(payments, "log_action", lambda *_args, **_kwargs: None)

    result = payments.confirm_payment_receipt(db, landlord_id, payment_request.id)

    ledger_entries = [record for record in db.added if isinstance(record, LedgerEntry)]
    assert result.status == "accepted"
    assert result.decided_by == landlord_id
    assert len(ledger_entries) == 1
    assert ledger_entries[0].created_by == landlord_id
    assert ledger_entries[0].paid_on == payment_request.paid_on


def test_non_owner_cannot_confirm_payment():
    payment_request, tenancy, _, _ = create_payment_records(status="submitted")
    db = FakeSession(payment_request, tenancy)

    with pytest.raises(HTTPException) as error:
        payments.confirm_payment_receipt(db, uuid4(), payment_request.id)

    assert error.value.status_code == 403
