def _signup(api, email="c@x.com"):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "C",
    })


def test_put_profile_upserts(api):
    _signup(api)
    r = api.put("/api/candidate/profile", json={
        "full_name": "Cee Andidate", "phone": "9991112222", "city": "Pune",
    })
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Cee Andidate"
    r2 = api.put("/api/candidate/profile", json={"full_name": "Cee A", "phone": "9991112222"})
    assert r2.status_code == 200
    assert api.get("/api/auth/me").json()["profile"]["full_name"] == "Cee A"


def test_profile_requires_permission(api):
    # recruiter has no test.take
    from tests.conftest import make_user
    from sqlmodel import Session
    with Session(api._engine) as s:
        make_user(s, email="rec@x.com", password="longenough12", role_name="recruiter")
    api.post("/api/auth/login", json={"email": "rec@x.com", "password": "longenough12"})
    r = api.put("/api/candidate/profile", json={"full_name": "X", "phone": "1"})
    assert r.status_code == 403


def test_me_attempts_empty_for_new_candidate(api):
    _signup(api, "own@x.com")
    r = api.get("/api/me/attempts")
    assert r.status_code == 200 and r.json() == []
