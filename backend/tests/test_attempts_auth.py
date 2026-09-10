def _candidate(api, email="cand@x.com"):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "Cand",
    })


def test_create_attempt_requires_auth(api):
    api.cookies.clear()
    assert api.post("/api/attempts", json={}).status_code == 401


def test_create_attempt_requires_profile(api):
    _candidate(api)
    r = api.post("/api/attempts", json={})
    assert r.status_code == 409


def test_create_attempt_stamps_user_and_name(api):
    _candidate(api, "stamp@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Stamp Ed", "phone": "1"})
    r = api.post("/api/attempts", json={"name": "IGNORED"})
    assert r.status_code == 200
    from sqlmodel import Session
    from models import Attempt
    with Session(api._engine) as s:
        a = s.get(Attempt, r.json()["attempt_id"])
        assert a.name == "Stamp Ed"
        assert a.user_id is not None


def test_other_candidate_cannot_touch_my_attempt(api):
    _candidate(api, "owner@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Owner", "phone": "1"})
    attempt_id = api.post("/api/attempts", json={}).json()["attempt_id"]

    api.cookies.clear()
    _candidate(api, "intruder@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Intruder", "phone": "1"})

    assert api.get(f"/api/attempts/{attempt_id}/items").status_code == 404
    assert api.post(f"/api/attempts/{attempt_id}/response",
                    json={"item_id": "g1", "text": "a"}).status_code == 404
    assert api.post(f"/api/attempts/{attempt_id}/submit").status_code == 404


def test_me_attempts_lists_only_own(api):
    _candidate(api, "own2@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Own Er", "phone": "1"})
    api.post("/api/attempts", json={})
    r = api.get("/api/me/attempts")
    assert r.status_code == 200 and len(r.json()) == 1
