from sqlmodel import Session
from tests.conftest import make_user


def _finished_attempt(api, email):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "C",
    })
    api.put("/api/candidate/profile", json={"full_name": "C Name", "phone": "1"})
    return api.post("/api/attempts", json={}).json()["attempt_id"]


def test_owner_can_view_own_report(api):
    aid = _finished_attempt(api, "rep-owner@x.com")
    assert api.get(f"/api/attempts/{aid}/report").status_code == 200


def test_stranger_candidate_cannot_view_report(api):
    aid = _finished_attempt(api, "rep-owner2@x.com")
    api.cookies.clear()
    _finished_attempt(api, "rep-stranger@x.com")
    assert api.get(f"/api/attempts/{aid}/report").status_code in (403, 404)


def test_recruiter_can_view_any_report_and_list(api):
    aid = _finished_attempt(api, "rep-owner3@x.com")
    api.cookies.clear()
    with Session(api._engine) as s:
        make_user(s, email="viewer@x.com", password="longenough12", role_name="recruiter")
    api.post("/api/auth/login", json={"email": "viewer@x.com", "password": "longenough12"})
    assert api.get(f"/api/attempts/{aid}/report").status_code == 200
    lst = api.get("/api/attempts")
    assert lst.status_code == 200 and any(row["attempt_id"] == aid for row in lst.json())


def test_candidate_cannot_list_attempts(api):
    _finished_attempt(api, "nolist@x.com")
    assert api.get("/api/attempts").status_code == 403
