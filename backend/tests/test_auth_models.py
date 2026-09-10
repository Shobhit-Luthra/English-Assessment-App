from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from models import Attempt, CandidateProfile, Permission, Role, RolePermission, SessionToken, User


def _engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(e)
    return e


def test_role_permission_and_user_round_trip():
    with Session(_engine()) as s:
        role = Role(name="candidate", is_system=True)
        s.add(role)
        s.add(Permission(key="test.take", description="take own test"))
        s.commit()
        s.add(RolePermission(role_id=role.id, permission_key="test.take"))
        user = User(
            email="a@b.com", password_hash="x", display_name="A", role_id=role.id
        )
        s.add(user)
        s.commit()
        s.add(CandidateProfile(user_id=user.id, full_name="A B", phone="123"))
        s.add(SessionToken(
            token="t", user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        ))
        attempt = Attempt(name="A B", user_id=user.id)
        s.add(attempt)
        s.commit()
        attempt_id = attempt.id

        assert s.get(User, user.id).role_id == role.id
        assert s.get(Attempt, attempt_id).user_id == user.id
        assert s.get(CandidateProfile, user.id).decision == "pending"
