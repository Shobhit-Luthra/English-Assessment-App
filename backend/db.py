from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DB_PATH = Path(__file__).parent / "demo.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

_MISSING_COLUMNS_MSG = (
    "attempt table is missing the item_ids/option_order/user_id columns - delete "
    "backend/demo.db and restart to recreate the schema (dev DB holds only "
    "seeded/throwaway data)"
)


def _assert_attempt_schema_current(bound_engine) -> None:
    """A pre-existing demo.db from before the question-bank change has an
    `attempt` table without `item_ids`/`option_order`. SQLModel's
    `create_all` does not ALTER existing tables, so the mismatch would only
    surface later as an opaque OperationalError. Fail loudly at startup."""
    inspector = inspect(bound_engine)
    if not inspector.has_table("attempt"):
        return
    with bound_engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(attempt)"))}
    if "item_ids" not in cols or "option_order" not in cols or "user_id" not in cols:
        raise RuntimeError(_MISSING_COLUMNS_MSG)


def init_db() -> None:
    _assert_attempt_schema_current(engine)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
