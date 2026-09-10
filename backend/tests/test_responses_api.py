import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import db
import main
from models import Attempt, Response


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)

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


def _attempt_with(client, ids):
    import os
    os.environ["ASSESSMENT_ALLOW_FIXED_SELECTION"] = "1"
    try:
        return client.post("/api/attempts", json={"name": "T", "item_ids": ids}).json()["attempt_id"]
    finally:
        del os.environ["ASSESSMENT_ALLOW_FIXED_SELECTION"]


def test_submit_response_rejects_item_not_in_attempt(client):
    attempt_id = _attempt_with(client, ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"])
    # pick a grammar id that exists in the bank but is not in this fixed selection
    outside = next(
        i for i in main._ITEMS_BY_ID
        if i not in {"g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"}
    )
    resp = client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": outside, "text": "a"})
    assert resp.status_code == 400


def test_mcq_answer_stored_as_canonical_letter(client):
    attempt_id = _attempt_with(client, ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"])
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
        perm = attempt.option_order["g1"]  # g1 canonical answer is "a" -> original index 0
    display_pos_of_correct = perm.index(0)  # where original option 0 now sits
    display_letter = ["a", "b", "c", "d"][display_pos_of_correct]
    client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": "g1", "text": display_letter})
    with Session(client._engine) as session:
        stored = session.exec(select(Response).where(Response.item_id == "g1")).first()
    assert stored.text == "a"  # canonical, regardless of shuffled display position


def test_writing_text_stored_verbatim(client):
    attempt_id = _attempt_with(client, ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"])
    essay = "Dear customer, I apologise for the delay."
    client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": "w1", "text": essay})
    with Session(client._engine) as session:
        stored = session.exec(select(Response).where(Response.item_id == "w1")).first()
    assert stored.text == essay
