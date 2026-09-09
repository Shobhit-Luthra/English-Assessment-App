import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import db
import main
from models import Attempt, Score


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(main, "run_scoring_pipeline", lambda *a, **k: None)  # skip Whisper/Ollama

    def _get_session():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[main.get_session] = _get_session
    main._load_bank()
    with TestClient(main.app) as c:
        c._engine = engine
        from tests.conftest import authenticate_candidate
        authenticate_candidate(c)
        yield c
    main.app.dependency_overrides.clear()


def test_grammar_score_total_reflects_attempt_not_whole_bank(client, monkeypatch):
    monkeypatch.setenv("ASSESSMENT_ALLOW_FIXED_SELECTION", "1")
    ids = ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"]
    attempt_id = client.post("/api/attempts", json={"name": "T", "item_ids": ids}).json()["attempt_id"]

    # canonical correct answers for g1-g4; submit_response stores the canonical
    # letter mapped from the client's display-position letter, so we send the
    # display letter that resolves to each correct option under this attempt's shuffle.
    canonical_correct = {"g1": "a", "g2": "c", "g3": "a", "g4": "b", "l1": "b", "l2": "b"}
    letters = ["a", "b", "c", "d"]
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
        option_order = dict(attempt.option_order)
    for item_id, correct in canonical_correct.items():
        perm = option_order.get(item_id)
        if perm is None:
            display = correct
        else:
            original_index = letters.index(correct)
            display = letters[perm.index(original_index)]
        client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": item_id, "text": display})
    client.post(f"/api/attempts/{attempt_id}/submit")

    with Session(client._engine) as session:
        grammar = session.exec(
            select(Score).where(Score.attempt_id == attempt_id, Score.dimension == "grammar")
        ).first()
    assert grammar.evidence["total"] == 4  # the 4 grammar items in THIS attempt
    assert grammar.evidence["correct"] == 4
    assert grammar.band == 6
