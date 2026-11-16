from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routers import certificates


class FakeResult:
    def all(self):
        return []


class FakeSession:
    def __init__(self, official=None):
        self.official = official
        self.statement = None

    def get(self, model, _user_id):
        return self.official

    def execute(self, statement):
        self.statement = statement
        return FakeResult()

    def commit(self):
        pass


def test_local_official_certificate_list_is_area_scoped():
    official = SimpleNamespace(level="local", area_id=17)
    db = FakeSession(official)

    assert certificates.list_certificates(
        current_user=SimpleNamespace(id=uuid4(), role="government"), db=db
    ) == []
    sql = str(db.statement)
    assert "ric_applications.area_id" in sql
    assert db.statement.compile().params["area_id_1"] == 17


def test_central_official_certificate_list_remains_nationwide():
    db = FakeSession(SimpleNamespace(level="central", area_id=None))

    certificates.list_certificates(
        current_user=SimpleNamespace(id=uuid4(), role="government"), db=db
    )

    assert db.statement.whereclause is None


def test_local_official_cannot_issue_certificate(monkeypatch):
    db = FakeSession(SimpleNamespace(level="local", area_id=17))
    monkeypatch.setattr(
        certificates,
        "issue_certificate_flow",
        lambda *_args: pytest.fail("issuance must not be called for a local official"),
    )

    with pytest.raises(HTTPException) as exc:
        certificates.issue_certificate(
            str(uuid4()),
            current_user=SimpleNamespace(id=uuid4(), role="government"),
            db=db,
        )

    assert exc.value.status_code == 403


def test_central_official_can_issue_certificate(monkeypatch):
    expected = {"certificate_id": str(uuid4()), "ric_number": "01010100001", "status": "active"}
    db = FakeSession(SimpleNamespace(level="central", area_id=None))
    monkeypatch.setattr(certificates, "issue_certificate_flow", lambda *_args: expected)

    result = certificates.issue_certificate(
        str(uuid4()),
        current_user=SimpleNamespace(id=uuid4(), role="government"),
        db=db,
    )

    assert result.ric_number == expected["ric_number"]
