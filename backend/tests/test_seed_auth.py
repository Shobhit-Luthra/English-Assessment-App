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


def test_bootstrap_accounts_keep_passwords_changed_after_first_start(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@corp.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "first-admin-password")
    monkeypatch.setenv("DEMO_SEED_USERS", "1")
    with _session() as s:
        seed_auth.seed_auth(s)
        seed_auth.ensure_default_admin(s)
        admin = s.exec(select(User).where(User.email == "boss@corp.com")).one()
        recruiter = s.exec(select(User).where(User.email == "recruiter@example.com")).one()
        admin.password_hash = seed_auth.hash_password("changed-admin-password")
        recruiter.password_hash = seed_auth.hash_password("changed-recruiter-password")
        s.add(admin)
        s.add(recruiter)
        s.commit()

        seed_auth.ensure_default_admin(s)
        s.refresh(admin)
        s.refresh(recruiter)
        from security import verify_password
        assert verify_password("changed-admin-password", admin.password_hash)
        assert verify_password("changed-recruiter-password", recruiter.password_hash)


def test_bootstrap_requires_explicit_credentials_outside_demo(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_SEED_USERS", raising=False)
    with _session() as s:
        seed_auth.seed_auth(s)
        import pytest
        with pytest.raises(RuntimeError, match="ADMIN_EMAIL"):
            seed_auth.ensure_default_admin(s)
