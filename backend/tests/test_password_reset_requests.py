from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

import security
from models import PasswordResetRequest
from tests.conftest import make_user


def _admin(api):
    with Session(api._engine) as s:
        make_user(s, email="admin@reset.test", password="longenough12", role_name="admin")
    assert api.post("/api/auth/login", json={"email": "admin@reset.test", "password": "longenough12"}).status_code == 200


def test_recovery_response_is_generic_and_pending_requests_are_deduplicated(api, monkeypatch):
    monkeypatch.setattr(security, "_RESET_REQUESTS", {})
    with Session(api._engine) as s:
        make_user(s, email="known@reset.test", password="longenough12", role_name="candidate")
    known = api.post("/api/auth/password-reset-requests", json={"email": "KNOWN@reset.test"})
    unknown = api.post("/api/auth/password-reset-requests", json={"email": "unknown@reset.test"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    again = api.post("/api/auth/password-reset-requests", json={"email": "known@reset.test"})
    assert again.status_code == 202
    with Session(api._engine) as s:
        assert len(s.exec(select(PasswordResetRequest).where(PasswordResetRequest.email == "known@reset.test")).all()) == 1


def test_recovery_requests_are_rate_limited_by_email_and_ip(api, monkeypatch):
    monkeypatch.setattr(security, "_RESET_REQUESTS", {})
    monkeypatch.setattr(security, "RESET_REQUEST_MAX", 2)
    for _ in range(2):
        assert api.post("/api/auth/password-reset-requests", json={"email": "limit@reset.test"}).status_code == 202
    assert api.post("/api/auth/password-reset-requests", json={"email": "limit@reset.test"}).status_code == 429
    monkeypatch.setattr(security, "_RESET_REQUESTS", {})
    for email in ("one@reset.test", "two@reset.test"):
        assert api.post("/api/auth/password-reset-requests", json={"email": email}).status_code == 202
    assert api.post("/api/auth/password-reset-requests", json={"email": "three@reset.test"}).status_code == 429


def test_only_admin_can_manage_requests_and_password_change_completes_them(api):
    with Session(api._engine) as s:
        user = make_user(s, email="target@reset.test", password="longenough12", role_name="candidate")
        request = PasswordResetRequest(email=user.email, user_id=user.id,
                                       expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        s.add(request); s.commit(); s.refresh(request)
        request_id, user_id = request.id, user.id
    assert api.post("/api/auth/login", json={"email": "target@reset.test", "password": "longenough12"}).status_code == 200
    assert api.get("/api/admin/password-reset-requests").status_code == 403
    _admin(api)
    listed = api.get("/api/admin/password-reset-requests")
    assert listed.status_code == 200 and listed.json()[0]["email"] == "target@reset.test"
    assert api.patch(f"/api/admin/users/{user_id}", json={"password": "replacementpw12"}).status_code == 200
    with Session(api._engine) as s:
        resolved = s.get(PasswordResetRequest, request_id)
        assert resolved.status == "completed"
        assert resolved.resolved_by is not None and resolved.resolved_at is not None


def test_expired_requests_are_not_listed(api):
    with Session(api._engine) as s:
        s.add(PasswordResetRequest(email="old@reset.test", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        s.commit()
    _admin(api)
    assert api.get("/api/admin/password-reset-requests").json() == []
