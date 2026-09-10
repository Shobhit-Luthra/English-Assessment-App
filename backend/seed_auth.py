# backend/seed_auth.py
import logging
import os
import secrets

from sqlmodel import Session, select

from models import CandidateProfile, Permission, Role, RolePermission, User
from security import hash_password

logger = logging.getLogger(__name__)

PERMISSIONS: dict[str, str] = {
    "test.take": "Create, answer, and submit one's own attempts",
    "report.view_own": "View the report for one's own attempts",
    "candidates.view": "List all candidates and view any candidate's attempts and reports",
    "candidates.decide": "Set a candidate's Hire / Reject decision",
    "analytics.view": "View the aggregate analytics dashboard",
    "roles.manage": "Manage roles, permissions, users, and password resets",
    "settings.manage": "Edit system settings",
}

SYSTEM_ROLES: dict[str, list[str]] = {
    "admin": list(PERMISSIONS),
    "recruiter": ["candidates.view", "candidates.decide", "analytics.view"],
    "candidate": ["test.take", "report.view_own"],
}


def _upsert_permissions(session: Session) -> None:
    existing = set(session.exec(select(Permission.key)).all())
    for key, desc in PERMISSIONS.items():
        if key not in existing:
            session.add(Permission(key=key, description=desc))
    session.commit()


def _upsert_role(session: Session, name: str) -> Role:
    role = session.exec(select(Role).where(Role.name == name)).first()
    if role is None:
        role = Role(name=name, is_system=True)
        session.add(role)
        session.commit()
        session.refresh(role)
    elif not role.is_system:
        role.is_system = True
        session.add(role)
        session.commit()
    return role


def _grant(session: Session, role_id: int, keys: list[str]) -> None:
    have = set(session.exec(
        select(RolePermission.permission_key).where(RolePermission.role_id == role_id)
    ).all())
    for key in keys:
        if key not in have:
            session.add(RolePermission(role_id=role_id, permission_key=key))
    session.commit()


def seed_auth(session: Session) -> None:
    _upsert_permissions(session)
    for name, keys in SYSTEM_ROLES.items():
        role = _upsert_role(session, name)
        # admin always gets the full catalogue, even permissions added later
        grant_keys = list(PERMISSIONS) if name == "admin" else keys
        _grant(session, role.id, grant_keys)


def ensure_default_admin(session: Session) -> None:
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    recruiter_role = session.exec(select(Role).where(Role.name == "recruiter")).first()
    if admin_role is None or recruiter_role is None:
        raise RuntimeError("seed_auth must run before ensure_default_admin")

    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "admin12345")
    try:
        pwd_hash = hash_password(password)
    except Exception:
        pwd_hash = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdHNhbHQ1Njc4OTAxMg$7QZf7k6m0F7iW8N1pX5y9A"

    admin_user = session.exec(select(User).where(User.email == email)).first()
    if admin_user is None:
        admin_user = User(
            email=email, password_hash=pwd_hash,
            display_name="Administrator", role_id=admin_role.id,
        )
    else:
        admin_user.password_hash = pwd_hash
    session.add(admin_user)
    session.commit()

    try:
        rec_hash = hash_password("recruiter12345")
    except Exception:
        rec_hash = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdHNhbHQ1Njc4OTAxMg$7QZf7k6m0F7iW8N1pX5y9A"

    recruiter_user = session.exec(select(User).where(User.email == "recruiter@example.com")).first()
    if recruiter_user is None:
        recruiter_user = User(
            email="recruiter@example.com", password_hash=rec_hash,
            display_name="Demo Recruiter", role_id=recruiter_role.id,
        )
    else:
        recruiter_user.password_hash = rec_hash
    session.add(recruiter_user)
    session.commit()



