from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from app.api.routers import rental_identity_sharing as sharing
from app.core.security import _create_token, create_access_token, decode_token


def test_tenant_can_share_only_their_active_certificate(monkeypatch):
    certificate = SimpleNamespace(id=uuid4())
    owner = SimpleNamespace(id=uuid4(), email="tenant@example.test", role="tenant")
    db = SimpleNamespace(commit=lambda: None)
    monkeypatch.setattr(sharing, "_active_certificate", lambda *_: (certificate, owner.email, "Tenant"))
    monkeypatch.setattr(sharing, "log_action", lambda *_: None)

    other = SimpleNamespace(email="different@example.test")
    with pytest.raises(HTTPException) as denied:
        sharing.share_certificate(certificate.id, Response(), other, db)
    assert denied.value.status_code == 404

    result = sharing.share_certificate(certificate.id, Response(), owner, db)
    claims = decode_token(result["token"])
    assert claims["sub"] == str(certificate.id)
    assert claims["type"] == "rental_identity_share"
    assert owner.email not in str(claims)
    assert result["expires_in_hours"] == 24


def test_public_verification_uses_share_tokens_and_returns_only_summary(monkeypatch):
    certificate = SimpleNamespace(id=uuid4(), ric_number="123456789012", status="active", issued_at=datetime.now(timezone.utc))
    tenant_id = uuid4()
    db = SimpleNamespace(scalar=lambda _: tenant_id)
    monkeypatch.setattr(sharing, "_active_certificate", lambda *_: (certificate, "tenant@example.test", "Tenant"))
    monkeypatch.setattr(sharing, "reliability_history", lambda *_: {
        "score": 52, "confirmed_payment_periods": 1, "events": [{"period_month": "2026-11", "id": uuid4(), "paid_on": "2026-11-01"}],
    })
    for token in (
        create_access_token(str(tenant_id)),
        _create_token({"type": "rental_identity_share", "sub": str(certificate.id)}, timedelta(seconds=-10)),
    ):
        with pytest.raises(HTTPException):
            sharing.verify_shared_identity(sharing.ShareVerificationRequest(token=token), Response(), db)

    token = _create_token({"type": "rental_identity_share", "sub": str(certificate.id)}, timedelta(minutes=1))
    response = Response()
    assert sharing.verify_shared_identity(sharing.ShareVerificationRequest(token=token), response, db) == {
        "applicant_name": "Tenant",
        "ric_number": certificate.ric_number,
        "issued_at": certificate.issued_at,
        "status": "active",
        "recorded_payment_periods": 1,
        "reliability_score": 52,
    }
    assert response.headers["Cache-Control"] == "no-store"


def test_expired_certificate_is_unavailable():
    certificate = SimpleNamespace(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    db = SimpleNamespace(execute=lambda _: SimpleNamespace(one_or_none=lambda: (certificate, "tenant@example.test", "Tenant")))
    with pytest.raises(HTTPException) as denied:
        sharing._active_certificate(db, uuid4())
    assert denied.value.status_code == 404
