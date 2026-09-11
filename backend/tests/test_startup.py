import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import bank
import main


def test_load_bank_populates_globals():
    bank.load_bank()
    assert "g1" in bank.get_all_items()
    assert bank.get_all_items()["g1"]["answer"] == "a"
    assert len(bank.get_bank_by_section()["grammar"]) >= bank.SELECTION_COUNTS["grammar"]


def test_every_bank_item_has_time_limit_and_valid_section():
    bank.load_bank()
    valid_sections = set(bank.SELECTION_COUNTS)
    for item in bank.get_all_items().values():
        assert item["section"] in valid_sections
        assert isinstance(item["time_limit_s"], int) and item["time_limit_s"] > 0


def test_bank_is_large_enough_for_variety():
    bank.load_bank()
    by_section = bank.get_bank_by_section()
    assert len(by_section["grammar"]) >= 60
    assert len(by_section["writing"]) >= 20
    read_aloud = [i for i in by_section["speaking"] if i["type"] == "read_aloud"]
    situational = [i for i in by_section["speaking"] if i["type"] == "situational"]
    assert len(read_aloud) >= 8 and len(situational) >= 8


def test_no_mcq_always_has_answer_a():
    bank.load_bank()
    answers = [i["answer"] for i in bank.get_bank_by_section()["grammar"]]
    assert len(set(answers)) > 1  # correct option is not always the same letter


def test_load_bank_rejects_underfilled_section(tmp_path, monkeypatch):
    thin = tmp_path / "bank.json"
    thin.write_text('{"items": [{"id": "g1", "section": "grammar", "type": "mcq", '
                    '"time_limit_s": 40, "options": ["a"], "answer": "a"}]}', encoding="utf-8")
    monkeypatch.setattr(bank, "BANK_PATH", thin)
    with pytest.raises(RuntimeError, match="grammar"):
        bank.load_bank()


def test_load_bank_requires_both_speaking_types(tmp_path, monkeypatch):
    data = '{"items": [' + ",".join(
        [f'{{"id": "g{i}", "section": "grammar", "type": "mcq", "time_limit_s": 40, '
         f'"options": ["a"], "answer": "a"}}' for i in range(5)]
        + ['{"id": "l1", "section": "listening", "type": "mcq", "time_limit_s": 60, "options": ["a"], "answer": "a"}',
           '{"id": "l2", "section": "listening", "type": "mcq", "time_limit_s": 60, "options": ["a"], "answer": "a"}',
           '{"id": "w1", "section": "writing", "type": "text", "time_limit_s": 180, "prompt": "x"}',
           '{"id": "s1", "section": "speaking", "type": "read_aloud", "time_limit_s": 30, "reference_text": "x"}',
           '{"id": "s2", "section": "speaking", "type": "read_aloud", "time_limit_s": 30, "reference_text": "x"}']
    ) + ']}'
    thin = tmp_path / "bank.json"
    thin.write_text(data, encoding="utf-8")
    monkeypatch.setattr(bank, "BANK_PATH", thin)
    with pytest.raises(RuntimeError, match="situational"):
        bank.load_bank()


def test_startup_seeds_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "seed-admin@corp.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "seed-admin-pw-123")

    import db
    from fastapi.testclient import TestClient
    from models import User

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'startup.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(db, "engine", test_engine)

    with TestClient(main.app):
        pass

    with Session(test_engine) as s:
        user = s.exec(select(User).where(User.email == "seed-admin@corp.com")).first()
        assert user is not None


def test_startup_fails_attempts_left_scoring_by_a_crash(tmp_path, monkeypatch):
    """A BackgroundTasks pipeline dies with the process. An attempt still in
    ``scoring`` at startup can never finish, so it is marked ``error`` with a
    category a recruiter can act on (re-score)."""
    import db
    from fastapi.testclient import TestClient
    from models import Attempt

    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.local")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'stuck.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(db, "engine", test_engine)
    with Session(test_engine) as s:
        s.add(Attempt(id="stuck", name="S", status="scoring"))
        s.add(Attempt(id="fine", name="F", status="in_progress"))
        s.commit()

    with TestClient(main.app):
        pass

    with Session(test_engine) as s:
        assert s.get(Attempt, "stuck").status == "error"
        assert s.get(Attempt, "stuck").error == "interrupted"
        assert s.get(Attempt, "fine").status == "in_progress"
