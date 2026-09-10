# backend/tests/test_rbac.py
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import db
import rbac
from models import Permission, Role, RolePermission, SessionToken, User


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)

    app = FastAPI()

    @app.get("/whoami")
    def whoami(user: rbac.CurrentUser):
        return {"email": user.email}

    @app.get("/needs-decide")
    def needs_decide(user=Depends(rbac.require("candidates.decide"))):
        return {"ok": True}

    def _get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[db.get_session] = _get_session
    with Session(engine) as s:
        role = Role(name="recruiter", is_system=True); s.add(role); s.commit()
        s.add(Permission(key="candidates.view", description="")); s.commit()
        s.add(RolePermission(role_id=role.id, permission_key="candidates.view"))
        u = User(email="r@x.com", password_hash="x", display_name="R", role_id=role.id)
        s.add(u); s.commit()
        s.add(SessionToken(token="good", user_id=u.id,
                           expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        s.add(SessionToken(token="stale", user_id=u.id,
                           expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        s.commit()
    return TestClient(app)


def test_no_cookie_is_401(client):
    assert client.get("/whoami").status_code == 401


def test_expired_cookie_is_401(client):
    assert client.get("/whoami", cookies={"session": "stale"}).status_code == 401


def test_valid_cookie_resolves_user(client):
    r = client.get("/whoami", cookies={"session": "good"})
    assert r.status_code == 200 and r.json()["email"] == "r@x.com"


def test_require_missing_permission_is_403(client):
    assert client.get("/needs-decide", cookies={"session": "good"}).status_code == 403
