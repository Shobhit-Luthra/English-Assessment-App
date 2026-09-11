from sqlmodel import Session, select
from models import Attempt, Score
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


def test_recruiter_can_view_any_report(api):
    aid = _finished_attempt(api, "rep-owner3@x.com")
    api.cookies.clear()
    with Session(api._engine) as s:
        make_user(s, email="viewer@x.com", password="longenough12", role_name="recruiter")
    api.post("/api/auth/login", json={"email": "viewer@x.com", "password": "longenough12"})
    assert api.get(f"/api/attempts/{aid}/report").status_code == 200


def test_report_includes_speaking_item_metadata(api):
    aid = _finished_attempt(api, "meta@x.com")
    with Session(api._engine) as s:
        attempt = s.exec(select(Attempt).where(Attempt.id == aid)).one()
        s.add(Score(
            attempt_id=attempt.id,
            dimension="speaking_fluency_s1",
            band=5,
            evidence={"item_id": "s1", "transcript": "Thank you for calling..."},
        ))
        s.commit()
    report = api.get(f"/api/attempts/{aid}/report").json()
    speaking = [x for x in report["scores"] if x["dimension"] == "speaking_fluency_s1"][0]
    assert speaking["evidence"]["item_type"] == "read_aloud"
    assert speaking["evidence"]["reference_text"]
    assert "delayed delivery" in speaking["evidence"]["reference_text"]
