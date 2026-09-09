from tests.conftest import login, make_user
from sqlmodel import Session

import security


def test_signup_creates_candidate_and_session(api):
    r = api.post("/api/auth/signup", json={
        "email": "New@Person.com", "password": "longenough12", "display_name": "New Person",
    })
    assert r.status_code == 200, r.text
    assert "session" in r.cookies or api.cookies.get("session")
    me = api.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "new@person.com"
    assert body["role"]["name"] == "candidate"
    assert set(body["permissions"]) == {"test.take", "report.view_own"}
    assert body["profile"] is None


def test_signup_duplicate_email_is_409(api):
    payload = {"email": "dup@x.com", "password": "longenough12", "display_name": "Dup"}
    assert api.post("/api/auth/signup", json=payload).status_code == 200
    api.cookies.clear()
    r = api.post("/api/auth/signup", json=payload)
    assert r.status_code == 409


def test_signup_rejects_short_password(api):
    r = api.post("/api/auth/signup", json={
        "email": "x@y.com", "password": "short", "display_name": "X",
    })
    assert r.status_code == 422


def test_me_requires_auth(api):
    assert api.get("/api/auth/me").status_code == 401


def test_logout_invalidates_session(api):
    api.post("/api/auth/signup", json={
        "email": "bye@x.com", "password": "longenough12", "display_name": "Bye",
    })
    assert api.get("/api/auth/me").status_code == 200
    assert api.post("/api/auth/logout").status_code == 204
    assert api.get("/api/auth/me").status_code == 401


def test_login_success_sets_cookie(api):
    api.post("/api/auth/signup", json={
        "email": "log@x.com", "password": "longenough12", "display_name": "Log",
    })
    api.cookies.clear()
    r = api.post("/api/auth/login", json={"email": "LOG@x.com", "password": "longenough12"})
    assert r.status_code == 200
    assert api.get("/api/auth/me").json()["email"] == "log@x.com"


def test_login_wrong_password_is_generic_401(api):
    api.post("/api/auth/signup", json={
        "email": "log2@x.com", "password": "longenough12", "display_name": "Log2",
    })
    api.cookies.clear()
    r = api.post("/api/auth/login", json={"email": "log2@x.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_is_generic_401(api):
    r = api.post("/api/auth/login", json={"email": "ghost@x.com", "password": "whatever123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_throttles_after_repeated_failure(api, monkeypatch):
    monkeypatch.setattr(security, "_FAILURES", {})
    monkeypatch.setattr(security, "MAX_FAILURES", 3)
    for _ in range(3):
        api.post("/api/auth/login", json={"email": "t@x.com", "password": "bad"})
    r = api.post("/api/auth/login", json={"email": "t@x.com", "password": "bad"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
