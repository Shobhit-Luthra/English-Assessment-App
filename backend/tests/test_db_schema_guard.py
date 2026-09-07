import pytest
from sqlalchemy import text
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

import db


def test_init_db_rejects_pre_bank_attempt_table(monkeypatch):
    """An old demo.db whose `attempt` table predates item_ids/option_order
    must fail loudly at startup rather than later with an opaque SQL error."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE attempt ("
                "id VARCHAR PRIMARY KEY, name VARCHAR, status VARCHAR, "
                "error VARCHAR, created_at DATETIME)"
            )
        )
    monkeypatch.setattr(db, "engine", engine)

    with pytest.raises(RuntimeError, match="item_ids"):
        db.init_db()


def test_init_db_accepts_fresh_database(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()  # no attempt table yet -> create_all builds the current schema
