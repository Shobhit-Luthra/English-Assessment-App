from sqlmodel import Session

from models import Attempt, CandidateProfile, Score
from tests.conftest import make_user


def _login_recruiter(api, email="ana-viewer@x.com"):
    with Session(api._engine) as s:
        make_user(s, email=email, password="longenough12", role_name="recruiter")
    api.post("/api/auth/login", json={"email": email, "password": "longenough12"})


def test_candidate_cannot_view_analytics(api):
    api.post("/api/auth/signup", json={
        "email": "noanalytics@x.com", "password": "longenough12", "display_name": "C",
    })
    assert api.get("/api/analytics/overview").status_code == 403


def test_recruiter_and_admin_can_view_analytics(api):
    _login_recruiter(api)
    data = api.get("/api/analytics/overview")
    assert data.status_code == 200
    api.cookies.clear()

    with Session(api._engine) as s:
        make_user(s, email="ana-admin@x.com", password="longenough12", role_name="admin")
    api.post("/api/auth/login", json={"email": "ana-admin@x.com", "password": "longenough12"})
    assert api.get("/api/analytics/overview").status_code == 200


def test_aggregates_cir_sections_and_decisions(api):
    with Session(api._engine) as s:
        u1 = make_user(s, email="c1@x.com", password="longenough12", role_name="candidate",
                       with_profile=True)
        u2 = make_user(s, email="c2@x.com", password="longenough12", role_name="candidate",
                       with_profile=True)
        s.get(CandidateProfile, u1.id).decision = "hired"
        s.get(CandidateProfile, u2.id).decision = "rejected"
        a1 = Attempt(user_id=u1.id, name="C One", status="done")
        a2 = Attempt(user_id=u2.id, name="C Two", status="done")
        a3 = Attempt(user_id=u2.id, name="C Two retake", status="in_progress")
        s.add_all([a1, a2, a3])
        s.commit()
        for a in (a1, a2):
            s.refresh(a)
        s.add_all([
            Score(attempt_id=a1.id, dimension="grammar", band=5, evidence={}),
            Score(attempt_id=a1.id, dimension="listening", band=4, evidence={}),
            Score(attempt_id=a1.id, dimension="speaking_fluency_s1", band=5, evidence={}),
            Score(attempt_id=a1.id, dimension="speaking_fluency_s2", band=3, evidence={}),
            Score(attempt_id=a1.id, dimension="writing_tone", band=6, evidence={}),
            Score(attempt_id=a1.id, dimension="situational_task_fulfilment", band=4, evidence={}),
            Score(attempt_id=a1.id, dimension="cir", band=5, evidence={}),
            Score(attempt_id=a2.id, dimension="grammar", band=3, evidence={}),
            Score(attempt_id=a2.id, dimension="cir", band=3, evidence={}),
        ])
        s.commit()

    _login_recruiter(api, "ana-data@x.com")
    data = api.get("/api/analytics/overview").json()

    assert data["total_candidates_tested"] == 2
    assert data["total_attempts"] == 3
    assert data["completed_attempts"] == 2
    assert data["in_progress_attempts"] == 1
    assert data["cir"] == {
        "average": 4.0,
        "recommended": 1,
        "borderline": 0,
        "not_recommended": 1,
        "pass_rate": 0.5,
    }
    assert data["sections"]["grammar"] == 4.0      # (5 + 3) / 2
    assert data["sections"]["speaking"] == 4.0     # fluent fallback for pre-fix rows
    assert data["sections"]["writing"] == 6.0
    assert data["sections"]["task_fulfilment"] == 4.0
    assert data["sections"]["listening"] == 4.0
    # per-candidate understanding: u1 (5,4)->4.5, u2 (3)->3.0 => 3.75
    assert data["sections"]["understanding"] == 3.75

    # candidates treated once using their latest done attempt: cirs [3, 5]
    assert data["benchmarks"]["median"] == 4.0
    assert data["benchmarks"]["top_25"] == 4.5
    assert data["decisions"] == {"hired": 1, "rejected": 1, "pending": 0, "total": 2}


def test_empty_state_is_well_formed(api):
    _login_recruiter(api, "ana-empty@x.com")
    data = api.get("/api/analytics/overview").json()
    assert data["total_candidates_tested"] == 0
    assert data["cir"] == {
        "average": None,
        "recommended": 0,
        "borderline": 0,
        "not_recommended": 0,
        "pass_rate": None,
    }
    assert data["benchmarks"] == {"median": None, "top_25": None}
    assert data["decisions"] == {"hired": 0, "rejected": 0, "pending": 0, "total": 0}