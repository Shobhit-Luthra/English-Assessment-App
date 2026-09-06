import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Attempt(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    status: str = Field(default="in_progress")  # in_progress | scoring | done | error
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Response(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("attempt_id", "item_id", name="uq_response_attempt_item"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: str = Field(foreign_key="attempt.id", index=True)
    item_id: str = Field(index=True)
    text: Optional[str] = None
    audio_path: Optional[str] = None
    duration_ms: Optional[int] = None


class Score(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: str = Field(foreign_key="attempt.id", index=True)
    dimension: str
    band: int
    evidence: dict = Field(default_factory=dict, sa_column=Column(JSON))
