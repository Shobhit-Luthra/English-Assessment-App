import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import db
import main
from models import Attempt


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
        yield c
    main.app.dependency_overrides.clear()


def test_create_attempt_persists_selection(client):
    resp = client.post("/api/attempts", json={"name": "Ada"})
    assert resp.status_code == 200
    attempt_id = resp.json()["attempt_id"]
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
        assert len(attempt.item_ids) == 10
        assert len(set(attempt.item_ids)) == 10
        # every mcq in the selection has a permutation
        for item_id in attempt.item_ids:
            if main._ITEMS_BY_ID[item_id]["type"] == "mcq":
                assert sorted(attempt.option_order[item_id]) == list(
                    range(len(main._ITEMS_BY_ID[item_id]["options"]))
                )


def test_create_attempt_rejects_client_supplied_item_ids_without_env(client):
    resp = client.post("/api/attempts", json={"name": "Mallory", "item_ids": ["g1", "g2"]})
    assert resp.status_code == 400


def test_create_attempt_honours_fixed_selection_with_env(client, monkeypatch):
    monkeypatch.setenv("ASSESSMENT_ALLOW_FIXED_SELECTION", "1")
    ids = ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"]
    resp = client.post("/api/attempts", json={"name": "Seed", "item_ids": ids})
    assert resp.status_code == 200
    with Session(client._engine) as session:
        attempt = session.get(Attempt, resp.json()["attempt_id"])
        assert attempt.item_ids == ids


def test_create_attempt_fixed_selection_rejects_unknown_id(client, monkeypatch):
    monkeypatch.setenv("ASSESSMENT_ALLOW_FIXED_SELECTION", "1")
    resp = client.post("/api/attempts", json={"name": "Seed", "item_ids": ["nope"]})
    assert resp.status_code == 400


def test_get_attempt_items_strips_answer_and_shuffles(client):
    attempt_id = client.post("/api/attempts", json={"name": "Ada"}).json()["attempt_id"]
    resp = client.get(f"/api/attempts/{attempt_id}/items")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 10
    for item in items:
        assert "answer" not in item
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
    first_mcq = next(i for i in items if i["type"] == "mcq")
    perm = attempt.option_order[first_mcq["id"]]
    original = main._ITEMS_BY_ID[first_mcq["id"]]["options"]
    assert first_mcq["options"] == [original[idx] for idx in perm]


def test_get_attempt_items_404_for_unknown_attempt(client):
    assert client.get("/api/attempts/does-not-exist/items").status_code == 404


def test_get_attempt_items_409_after_submit(client):
    attempt_id = client.post("/api/attempts", json={"name": "Ada"}).json()["attempt_id"]
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
        attempt.status = "done"
        session.add(attempt)
        session.commit()
    assert client.get(f"/api/attempts/{attempt_id}/items").status_code == 409


def test_old_items_endpoint_is_gone(client):
    assert client.get("/api/items").status_code == 404


def test_get_attempt_items_409_when_an_item_left_the_bank(client, monkeypatch):
    attempt_id = client.post("/api/attempts", json={"name": "Ada"}).json()["attempt_id"]
    with Session(client._engine) as session:
        dropped = session.get(Attempt, attempt_id).item_ids[0]
    trimmed = {k: v for k, v in main._ITEMS_BY_ID.items() if k != dropped}
    monkeypatch.setattr(main, "_ITEMS_BY_ID", trimmed)
    assert client.get(f"/api/attempts/{attempt_id}/items").status_code == 409


def test_get_attempt_items_includes_saved_writing_answer(client, monkeypatch):
    monkeypatch.setenv("ASSESSMENT_ALLOW_FIXED_SELECTION", "1")
    ids = ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"]
    attempt_id = client.post("/api/attempts", json={"name": "Seed", "item_ids": ids}).json()["attempt_id"]
    essay = "Dear customer, I am sorry about the delay."
    client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": "w1", "text": essay})

    items = client.get(f"/api/attempts/{attempt_id}/items").json()["items"]
    by_id = {i["id"]: i for i in items}
    assert by_id["w1"]["response_text"] == essay
    # mcq answers are never echoed back (canonical letter != shuffled position)
    assert "response_text" not in by_id["g1"]
