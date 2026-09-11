"""Re-scoring an errored attempt, the user-safe error message on /report,
and the health probe the UI uses before it starts waiting on a score."""

import pytest
from sqlmodel import Session, select

import routes.attempts as attempts_routes
from models import Attempt, Score
from tests.conftest import make_user


@pytest.fixture(autouse=True)
def _no_real_pipeline(monkeypatch):
    calls = []
    monkeypatch.setattr(attempts_routes, "run_scoring_pipeline", lambda *a, **k: calls.append(a))
    return calls


def _errored_attempt(api, email):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "C",
    })
    api.put("/api/candidate/profile", json={"full_name": "C Name", "phone": "1"})
    aid = api.post("/api/attempts", json={}).json()["attempt_id"]
    with Session(api._engine) as s:
        attempt = s.get(Attempt, aid)
        attempt.status = "error"
        attempt.error = "judge_unavailable"
        s.add(attempt)
        s.add(Score(attempt_id=aid, dimension="grammar", band=5, evidence={}))
        s.add(Score(attempt_id=aid, dimension="listening", band=4, evidence={}))
        s.add(Score(attempt_id=aid, dimension="speaking_fluency_s1", band=3,
                    evidence={"item_id": "s1"}))
        s.commit()
    return aid


def _login_recruiter(api):
    api.cookies.clear()
    with Session(api._engine) as s:
        make_user(s, email="rescorer@x.com", password="longenough12", role_name="recruiter")
    api.post("/api/auth/login", json={"email": "rescorer@x.com", "password": "longenough12"})


def test_report_exposes_category_and_safe_message_only(api):
    aid = _errored_attempt(api, "err-owner@x.com")
    report = api.get(f"/api/attempts/{aid}/report").json()
    assert report["status"] == "error"
    assert report["error"] == "judge_unavailable"
    assert "unavailable" in report["error_message"].lower()


def test_report_error_message_is_null_when_no_error(api):
    api.post("/api/auth/signup", json={
        "email": "ok-owner@x.com", "password": "longenough12", "display_name": "C",
    })
    api.put("/api/candidate/profile", json={"full_name": "C Name", "phone": "1"})
    aid = api.post("/api/attempts", json={}).json()["attempt_id"]
    report = api.get(f"/api/attempts/{aid}/report").json()
    assert report["error"] is None and report["error_message"] is None


def test_candidate_cannot_rescore_own_attempt(api):
    aid = _errored_attempt(api, "cand-rescore@x.com")
    assert api.post(f"/api/attempts/{aid}/rescore").status_code == 403


def test_rescore_requires_error_status(api):
    aid = _errored_attempt(api, "not-err@x.com")
    with Session(api._engine) as s:
        attempt = s.get(Attempt, aid)
        attempt.status = "done"
        s.add(attempt)
        s.commit()
    _login_recruiter(api)
    assert api.post(f"/api/attempts/{aid}/rescore").status_code == 409


def test_rescore_unknown_attempt_is_404(api):
    _login_recruiter(api)
    assert api.post("/api/attempts/nope/rescore").status_code == 404


def test_rescore_resets_status_keeps_objective_rows_and_requeues(api, _no_real_pipeline):
    aid = _errored_attempt(api, "rescore-me@x.com")
    _login_recruiter(api)
    resp = api.post(f"/api/attempts/{aid}/rescore")
    assert resp.status_code == 200, resp.text
    with Session(api._engine) as s:
        attempt = s.get(Attempt, aid)
        assert attempt.status == "scoring"
        assert attempt.error is None
        dims = {r.dimension for r in s.exec(select(Score).where(Score.attempt_id == aid)).all()}
    assert dims == {"grammar", "listening"}  # judged/deterministic rows are recomputed
    assert len(_no_real_pipeline) == 1
    assert _no_real_pipeline[0][0] == aid  # (attempt_id, items_by_section)


def test_health_reports_engine_availability(api, monkeypatch):
    import main

    monkeypatch.setattr(main, "_ollama_reachable", lambda: False)
    monkeypatch.setattr(main, "_whisper_loaded", lambda: True)
    resp = api.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ollama": False, "whisper": True}


def test_double_rescore_queues_exactly_one_pipeline(api, _no_real_pipeline):
    aid = _errored_attempt(api, "double@x.com")
    _login_recruiter(api)
    first = api.post(f"/api/attempts/{aid}/rescore").status_code
    second = api.post(f"/api/attempts/{aid}/rescore").status_code
    assert (first, second) == (200, 409)
    assert len(_no_real_pipeline) == 1


def test_report_never_returns_legacy_exception_text(api):
    aid = _errored_attempt(api, "legacy@x.com")
    with Session(api._engine) as s:
        attempt = s.get(Attempt, aid)
        attempt.error = "Traceback: ffmpeg not found at C:\secret\bin"
        s.add(attempt)
        s.commit()
    report = api.get(f"/api/attempts/{aid}/report").json()
    assert report["error"] == "unknown"
    assert "secret" not in report["error_message"]
