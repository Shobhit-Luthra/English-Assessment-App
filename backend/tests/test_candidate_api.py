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


def test_me_returns_profile_and_decision(api):
    from sqlmodel import Session, select

    from models import CandidateProfile, User

    _signup(api, "own@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Cee", "phone": "999"})
    me = api.get("/api/me")
    assert me.status_code == 200
    assert me.json()["full_name"] == "Cee"
    assert me.json()["decision"] == "pending"

    with Session(api._engine) as s:
        u = s.exec(select(User).where(User.email == "own@x.com")).first()
        s.get(CandidateProfile, u.id).decision = "hired"
        s.commit()
    assert api.get("/api/me").json()["decision"] == "hired"


def test_me_attempts_include_cir_for_done_attempts(api):
    from sqlmodel import Session, select

    from models import Attempt, Score, User

    _signup(api, "own@x.com")
    with Session(api._engine) as s:
        u = s.exec(select(User).where(User.email == "own@x.com")).first()
        a = Attempt(name="Cee", user_id=u.id, status="done")
        s.add(a)
        s.flush()
        s.add(Score(attempt_id=a.id, dimension="cir", band=6))
        s.add(Score(attempt_id=a.id, dimension="grammar", band=5))
        s.commit()
        attempt_id = a.id
    rows = api.get("/api/me/attempts").json()
    assert rows[0]["attempt_id"] == attempt_id
    assert rows[0]["cir"] == 6
    assert rows[0]["status"] == "done"
