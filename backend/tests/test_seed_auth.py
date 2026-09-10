# backend/tests/test_seed_auth.py
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import seed_auth
from models import Permission, Role, RolePermission, User


def _session():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(e)
    return Session(e)


def test_seed_is_idempotent_and_grants_admin_everything():
    with _session() as s:
        seed_auth.seed_auth(s)
        seed_auth.seed_auth(s)  # twice — no duplicates, no error

        perms = set(s.exec(select(Permission.key)).all())
        assert perms == set(seed_auth.PERMISSIONS)

        roles = {r.name: r for r in s.exec(select(Role)).all()}
        assert roles["admin"].is_system and roles["recruiter"].is_system and roles["candidate"].is_system

        admin_perms = set(s.exec(
            select(RolePermission.permission_key).where(RolePermission.role_id == roles["admin"].id)
        ).all())
        assert admin_perms == set(seed_auth.PERMISSIONS)

        cand_perms = set(s.exec(
            select(RolePermission.permission_key).where(RolePermission.role_id == roles["candidate"].id)
        ).all())
        assert cand_perms == {"test.take", "report.view_own"}


def test_ensure_default_admin_creates_one(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@corp.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "supersecret123")
    with _session() as s:
        seed_auth.seed_auth(s)
        seed_auth.ensure_default_admin(s)
        seed_auth.ensure_default_admin(s)  # idempotent
        admins = s.exec(select(User).where(User.email == "boss@corp.com")).all()
        assert len(admins) == 1
