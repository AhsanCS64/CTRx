from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routers.rent import _missed_eligible
from app.api.routers.tenancies import FeedbackInput, save_feedback
from app.services.scoring import reliability_history


class HistoryDB:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params):
        assert "t.tenant_id = :tenant" in str(query)
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: self.rows))


def event(tenancy, month, **values):
    row = dict(id=uuid4(), tenancy_id=tenancy, period_month=month, original_id=None,
               created_at=datetime.now(timezone.utc), paid_on=None, on_time=None, amount=None,
               previous_balance=None, balance=None, missed_points=None)
    row.update(values)
    return row


def test_confirmed_payment_clears_missed_points_for_that_tenancy_and_period():
    tenancy = uuid4()
    month = date(2026, 10, 1)
    missed = event(tenancy, month, missed_points=-3)
    other_missed = event(uuid4(), month, missed_points=-3)
    payment = event(tenancy, month, original_id=uuid4(), paid_on=date(2026, 10, 9), on_time=False, amount=Decimal(6000))
    result = reliability_history(HistoryDB([payment, other_missed, missed]), uuid4())
    assert result["score"] == 46
    assert result["confirmed_payment_periods"] == 1
    assert [row["points"] for row in result["events"]] == [-1, -3, 0]


def test_reversed_payment_no_longer_clears_a_missed_event():
    tenancy = uuid4()
    month = date(2026, 10, 1)
    payment_id = uuid4()
    missed = event(tenancy, month, missed_points=-3)
    payment = event(tenancy, month, original_id=payment_id, on_time=True, amount=Decimal(6000))
    correction = event(tenancy, month, original_id=payment_id, on_time=True, amount=Decimal(-6000),
                       previous_balance=Decimal(6000), balance=Decimal(0))
    result = reliability_history(HistoryDB([correction, payment, missed]), uuid4())
    assert result["score"] == 47
    assert result["confirmed_payment_periods"] == 0


def test_no_score_without_history():
    assert reliability_history(HistoryDB([]), uuid4())["score"] is None


def test_only_overdue_unreported_landlord_invoice_can_be_marked_missed():
    landlord = uuid4()
    tenancy = SimpleNamespace(landlord_id=landlord, rent_due_day=31)
    invoice = SimpleNamespace(period_month=date(2000, 2, 1), created_at=datetime(2000, 2, 1, tzinfo=timezone.utc),
                              requested_by=landlord, status="pending")
    assert _missed_eligible(invoice, tenancy)
    invoice.status = "submitted"
    assert not _missed_eligible(invoice, tenancy)
    invoice.status = "pending"
    invoice.created_at = datetime.now(timezone.utc) + timedelta(days=1)
    assert not _missed_eligible(invoice, tenancy)


def test_feedback_requires_tenancy_membership(monkeypatch):
    payer, landlord, outsider = uuid4(), uuid4(), uuid4()
    tenancy = SimpleNamespace(id=uuid4(), tenant_id=payer, landlord_id=landlord, start_date=date(2026, 10, 1), end_date=None)
    writes = []
    db = SimpleNamespace(get=lambda *_: tenancy, execute=lambda *args: writes.append(args), commit=lambda: None)
    monkeypatch.setattr("app.api.routers.tenancies.log_action", lambda *args, **kwargs: None)
    payload = FeedbackInput(period_month=date(2026, 10, 1), rating="concern", remark="  Repair request went unanswered.  ")
    with pytest.raises(HTTPException) as denied:
        save_feedback(tenancy.id, "repairs", payload, db, SimpleNamespace(id=outsider, role="tenant"))
    assert denied.value.status_code == 404
    assert not writes
    for user_id, role in ((payer, "tenant"), (landlord, "landlord")):
        assert save_feedback(tenancy.id, "repairs", payload, db, SimpleNamespace(id=user_id, role=role)) == {"saved": True}
        assert writes[-1][1]["author"] == user_id
        assert writes[-1][1]["remark"] == "Repair request went unanswered."



def test_monthly_feedback_is_explained_separately_from_payments():
    tenant = uuid4()
    months = [date(2026, 10, 1), date(2026, 11, 1)]
    rows = [event(None, month, monthly_feedback=True) for month in months]
    result = reliability_history(HistoryDB(rows), tenant)
    assert result["score"] == 52
    assert result["confirmed_payment_periods"] == 0
    assert [row["event_type"] for row in result["events"]] == ["monthly_feedback", "monthly_feedback"]
    assert len({row["id"] for row in result["events"]}) == 2
    assert result == reliability_history(HistoryDB(rows), tenant)


def test_fully_reversed_payment_leaves_no_qualifying_history():
    tenancy = uuid4()
    month = date(2026, 10, 1)
    payment_id = uuid4()
    payment = event(tenancy, month, original_id=payment_id, on_time=True, amount=Decimal(6000))
    correction = event(tenancy, month, original_id=payment_id, on_time=True, amount=Decimal(-6000),
                       previous_balance=Decimal(6000), balance=Decimal(0))
    result = reliability_history(HistoryDB([correction, payment]), uuid4())
    assert result["score"] is None
    assert result["confirmed_payment_periods"] == 0
    assert len(result["events"]) == 2


def test_feedback_month_must_be_within_the_tenancy():
    tenant, landlord = uuid4(), uuid4()
    tenancy = SimpleNamespace(id=uuid4(), tenant_id=tenant, landlord_id=landlord,
                              start_date=date(2025, 6, 14), end_date=date(2025, 11, 3))
    db = SimpleNamespace(get=lambda *_: tenancy)
    for invalid in (date(2025, 5, 1), date(2025, 12, 1), date(2025, 10, 15)):
        with pytest.raises(HTTPException) as denied:
            save_feedback(tenancy.id, "conduct", FeedbackInput(period_month=invalid, rating="positive", remark="Good communication"),
                          db, SimpleNamespace(id=landlord, role="landlord"))
        assert denied.value.status_code == 422

def test_only_landlord_can_correct_start_and_end_must_remain_later():
    from app.api.routers.tenancies import TenancyStartUpdate, correct_start_date

    tenancy = SimpleNamespace(id=uuid4(), start_date=date(2025, 6, 1), end_date=date(2025, 7, 1))
    payload = TenancyStartUpdate(start_date=date(2025, 7, 1))
    db = SimpleNamespace(execute=lambda _: SimpleNamespace(scalar_one_or_none=lambda: tenancy))
    for role, status in (("tenant", 403), ("landlord", 422)):
        with pytest.raises(HTTPException) as denied:
            correct_start_date(tenancy.id, payload, db, SimpleNamespace(id=uuid4(), role=role))
        assert denied.value.status_code == status

def test_occupied_property_is_blocked_before_a_listing_is_created(monkeypatch):
    from app.api.routers import properties
    from app.schemas.properties import ListingCreate

    property_record = SimpleNamespace(id=uuid4())
    user = SimpleNamespace(id=uuid4(), role="landlord")
    monkeypatch.setattr(properties, "_owned_property", lambda *_args, **_kwargs: property_record)

    def enforce_occupancy(statement):
        assert "tenancies" in str(statement) and "end_date" in str(statement)
        return True

    db = SimpleNamespace(scalar=enforce_occupancy)
    for status in ("draft", "available"):
        payload = ListingCreate(status=status, title="Apartment", property_id=property_record.id)
        with pytest.raises(HTTPException) as conflict:
            properties.create_listing(str(property_record.id), payload, db, user)
        assert conflict.value.status_code == 409

def test_acknowledged_lease_proposal_does_not_change_existing_dates(monkeypatch):
    from app.api.routers import tenancies

    rng = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), start_date=date(2028, 1, 1), end_date=None)
    lease = SimpleNamespace(tenant_acknowledged_at=datetime.now(timezone.utc), landlord_acknowledged_at=None)
    results = iter([
        SimpleNamespace(scalar_one_or_none=lambda: rng),
        SimpleNamespace(one_or_none=lambda: lease),
        SimpleNamespace(scalar_one=lambda: False),
    ])
    events = []
    db = SimpleNamespace(execute=lambda *_: next(results), commit=lambda: None)
    monkeypatch.setattr(tenancies, "log_action", lambda db, action, *_args, **kwargs: events.append(action))
    monkeypatch.setattr(tenancies, "_notify_start_date", lambda *_: None)
    result = tenancies.correct_start_date(rng.id, tenancies.TenancyStartUpdate(start_date=date(2026, 11, 1)), db,
                                          SimpleNamespace(id=uuid4(), role="landlord"))
    assert result == {"start_date": date(2028, 1, 1), "proposed_start_date": date(2026, 11, 1)}
    assert rng.start_date == date(2028, 1, 1)
    assert events == ["tenancy.start_date.proposed"]
