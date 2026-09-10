from sqlmodel import Session

from models import Attempt, CandidateProfile, Score
from tests.conftest import make_user


def _make_candidate(api, email="cand@x.com", cir: int = 5):
    """Candidate with a completed attempt and a full band set (incl. both
    speaking items, composite sections + CIR). Returns the user id."""
    user_id = None
    with Session(api._engine) as s:
        user = make_user(s, email=email, password="longenough12",
                         role_name="candidate", with_profile=True)
        attempt = Attempt(name=user.display_name, user_id=user.id, status="done")
        s.add(attempt)
        s.commit()
        s.refresh(attempt)
        s.add(Score(attempt_id=attempt.id, dimension="cir", band=cir, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="grammar", band=6, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="listening", band=5, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="writing_tone", band=4, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="writing", band=5, evidence={}))
        s.add(Score(attempt_id=attempt.id,
                    dimension="situational_task_fulfilment", band=5, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="speaking_fluency_s1", band=5, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="speaking_fluency_s2", band=3, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="speaking", band=3, evidence={}))
        s.commit()
        user_id = user.id
    return user_id


def _login(api, email, password="longenough12"):
    r = api.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def _recruiter(api):
    with Session(api._engine) as s:
        make_user(s, email="rec@x.com", password="longenough12", role_name="recruiter")
    _login(api, "rec@x.com")


def test_recruiter_lists_candidates_with_attempts_and_bands(api):
    _make_candidate(api)
    _recruiter(api)

    rows = api.get("/api/candidates").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["full_name"] == "Test User"
    assert row["decision"] == "pending"
    assert row["decided_by"] is None

    attempts = row["attempts"]
    assert len(attempts) == 1
    summary = attempts[0]
    assert summary["status"] == "done"
    assert summary["cir"] == 5
    assert summary["sections"]["grammar"] == 6
    assert summary["sections"]["listening"] == 5
    # composite sections (from the full judged rubric) win over the fallbacks
    assert summary["sections"]["speaking"] == 3
    assert summary["sections"]["writing"] == 5
    # understanding = mean of grammar + listening: (6 + 5) / 2 == 5.5 -> 6
    assert summary["sections"]["understanding"] == 6
    # a single candidate has no peers to compare against
    assert row["pct_stronger"] == 50.0


def test_benchmark_ranks_candidates_against_peers(api):
    _make_candidate(api, email="strong@x.com", cir=5)
    _make_candidate(api, email="weak@x.com", cir=2)
    _recruiter(api)

    rows = api.get("/api/candidates").json()
    by_email = {r["email"]: r for r in rows}
    assert by_email["strong@x.com"]["pct_stronger"] == 100.0
    assert by_email["weak@x.com"]["pct_stronger"] == 0.0


def test_candidate_cannot_list_candidates(api):
    _make_candidate(api)
    _login(api, "cand@x.com")
    assert api.get("/api/candidates").status_code == 403


def test_unauthenticated_listing_is_401(api):
    assert api.get("/api/candidates").status_code == 401


def test_recruiter_hires_candidate_and_it_is_attributed(api):
    uid = _make_candidate(api, email="hire@x.com")
    _recruiter(api)

    r = api.post(f"/api/candidates/{uid}/decision", json={"decision": "hired"})
    assert r.status_code == 200
    assert r.json() == {"user_id": uid, "decision": "hired"}

    rows = api.get("/api/candidates").json()
    assert rows[0]["decision"] == "hired"
    assert rows[0]["decided_by"] == "rec"
    assert rows[0]["decided_at"] is not None


def test_recruiter_rejects_and_can_reset_to_pending(api):
    uid = _make_candidate(api, email="rej@x.com")
    _recruiter(api)

    assert api.post(f"/api/candidates/{uid}/decision",
                    json={"decision": "rejected"}).status_code == 200
    assert api.post(f"/api/candidates/{uid}/decision",
                    json={"decision": "pending"}).status_code == 200

    rows = api.get("/api/candidates").json()
    assert rows[0]["decision"] == "pending"
    assert rows[0]["decided_by"] is None


def test_candidate_cannot_decide(api):
    uid = _make_candidate(api, email="no-decide@x.com")
    with Session(api._engine) as s:
        make_user(s, email="plain@x.com", password="longenough12", role_name="candidate")
    _login(api, "plain@x.com")
    assert api.post(f"/api/candidates/{uid}/decision",
                    json={"decision": "hired"}).status_code == 403


def test_unknown_candidate_decision_is_404(api):
    _recruiter(api)
    assert api.post("/api/candidates/nope/decision",
                    json={"decision": "hired"}).status_code == 404


def test_invalid_decision_value_rejected(api):
    uid = _make_candidate(api, email="bad-decision@x.com")
    _recruiter(api)
    assert api.post(f"/api/candidates/{uid}/decision",
                    json={"decision": "maybe"}).status_code == 422