"""End-to-end scoring over the normal random selection path (no fixed ids).

Guards against regressions where option shuffling, canonical-letter mapping,
or attempt-scoped `total` counts drift apart: a candidate who picks every
correct answer must score a perfect objective band whatever subset was drawn.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import db
import main
from bank import get_all_items, load_bank
from models import Attempt, Score

_LETTERS = ["a", "b", "c", "d", "e", "f"]


@pytest.fixture
def client(monkeypatch):
    import scoring.pipeline

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(scoring.pipeline, "run_scoring_pipeline", lambda *a, **k: None)

    def _get_session():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[db.get_session] = _get_session
    load_bank()
    with TestClient(main.app) as c:
        c._engine = engine
        from tests.conftest import authenticate_candidate
        authenticate_candidate(c)
        yield c
    main.app.dependency_overrides.clear()


def test_random_attempt_all_correct_scores_perfect_objective_bands(client):
    attempt_id = client.post("/api/attempts", json={"name": "Ada"}).json()["attempt_id"]
    payload = client.get(f"/api/attempts/{attempt_id}/items").json()

    # the answer key must never reach the client
    assert '"answer"' not in json.dumps(payload)

    for served in payload["items"]:
        if served["type"] != "mcq":
            continue
        bank_item = get_all_items()[served["id"]]
        correct_text = bank_item["options"][_LETTERS.index(bank_item["answer"])]
        display_pos = served["options"].index(correct_text)
        client.post(
            f"/api/attempts/{attempt_id}/response",
            json={"item_id": served["id"], "text": _LETTERS[display_pos]},
        )

    assert client.post(f"/api/attempts/{attempt_id}/submit").status_code == 200

    with Session(client._engine) as session:
        scores = {
            s.dimension: s
            for s in session.exec(select(Score).where(Score.attempt_id == attempt_id)).all()
        }

    assert scores["grammar"].evidence["total"] == 5
    assert scores["grammar"].evidence["correct"] == 5
    assert scores["grammar"].band == 6
    assert scores["listening"].evidence["total"] == 2
    assert scores["listening"].evidence["correct"] == 2
    assert scores["listening"].band == 6
