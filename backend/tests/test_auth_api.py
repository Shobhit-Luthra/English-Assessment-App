from tests.conftest import login, make_user
from sqlmodel import Session


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
