import uuid
from datetime import datetime, timedelta, timezone
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
    item_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    option_order: dict[str, list[int]] = Field(default_factory=dict, sa_column=Column(JSON))
    user_id: Optional[str] = Field(default=None, foreign_key="user.id", index=True)


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


class Role(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    is_system: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_now)


class Permission(SQLModel, table=True):
    key: str = Field(primary_key=True)
    description: str = ""


class RolePermission(SQLModel, table=True):
    role_id: int = Field(foreign_key="role.id", primary_key=True)
    permission_key: str = Field(foreign_key="permission.key", primary_key=True)


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    display_name: str
    role_id: int = Field(foreign_key="role.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_now)


class CandidateProfile(SQLModel, table=True):
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    full_name: str
    phone: str
    city: Optional[str] = None
    first_language: Optional[str] = None
    decision: str = Field(default="pending")  # pending | hired | rejected
    decided_by: Optional[str] = Field(default=None, foreign_key="user.id")
    decided_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=_now)


class SessionToken(SQLModel, table=True):
    token: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=_now)
    expires_at: datetime
