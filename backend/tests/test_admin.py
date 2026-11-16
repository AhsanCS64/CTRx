"""Tests for the Admin console implementation.

These tests cover basic access control and core admin operations.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from sqlalchemy.orm import Session
from app.db.models.users import User
from app.core.security import create_access_token

client = TestClient(app)

# Helper to create auth headers for a given user role
def auth_headers(user_id: str, role: str):
    token = create_access_token(user_id, extra_claims={"role": role})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def admin_user(db: Session):
    admin = User(email="admin@example.com", password_hash="hash", role="admin", is_active=True, created_at="now")
    db.add(admin)
    db.flush()
    return admin

@pytest.fixture
def non_admin_user(db: Session):
    user = User(email="user@example.com", password_hash="hash", role="government", is_active=True, created_at="now")
    db.add(user)
    db.flush()
    return user

def test_non_admin_cannot_access_admin_endpoints(non_admin_user: User):
    headers = auth_headers(str(non_admin_user.id), non_admin_user.role)
    response = client.get("/admin/users/", headers=headers)
    assert response.status_code == 403

def test_admin_can_create_official(admin_user: User, db: Session):
    headers = auth_headers(str(admin_user.id), admin_user.role)
    payload = {
        "email": "official@example.com",
        "password": "secret",
        "full_name": "Official Name",
        "level": "local",
        "area_id": None,
    }
    response = client.post("/admin/officials", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == payload["email"]
    # Verify official profile row exists
    official = db.query(User).filter(User.email == payload["email"]).first()
    assert official is not None
    profile = db.query(app.db.models.official_profiles.OfficialProfile).filter(app.db.models.official_profiles.OfficialProfile.user_id == official.id).first()
    assert profile is not None

def test_admin_activate_deactivate_user(admin_user: User, db: Session):
    # create target user
    target = User(email="target@example.com", password_hash="hash", role="government", is_active=False, created_at="now")
    db.add(target)
    db.flush()
    headers = auth_headers(str(admin_user.id), admin_user.role)
    # activate
    response = client.patch(f"/admin/users/{target.id}/active", json={"is_active": True}, headers=headers)
    assert response.status_code == 200
    db.refresh(target)
    assert target.is_active is True
    # deactivate
    response = client.patch(f"/admin/users/{target.id}/active", json={"is_active": False}, headers=headers)
    assert response.status_code == 200
    db.refresh(target)
    assert target.is_active is False

def test_system_setting_upsert(admin_user: User, db: Session):
    headers = auth_headers(str(admin_user.id), admin_user.role)
    key = "site_name"
    # first set
    response = client.patch(f"/admin/settings/{key}", json={"value": "CTRx"}, headers=headers)
    assert response.status_code == 200
    setting = db.get(app.db.models.system_settings.SystemSetting, key)
    assert setting.value == "CTRx"
    # update
    response = client.patch(f"/admin/settings/{key}", json={"value": "CTRx Updated"}, headers=headers)
    assert response.status_code == 200
    setting = db.get(app.db.models.system_settings.SystemSetting, key)
    assert setting.value == "CTRx Updated"

def test_audit_log_viewer(admin_user: User, db: Session):
    headers = auth_headers(str(admin_user.id), admin_user.role)
    # assume some audit logs exist; just request endpoint
    response = client.get("/admin/audit-logs/", headers=headers)
    assert response.status_code == 200
    # should return a list (could be empty)
    assert isinstance(response.json(), list)
