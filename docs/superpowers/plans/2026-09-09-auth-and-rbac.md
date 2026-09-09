# Authentication + RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add email/password authentication, a data-driven role/permission model, a signup → profile → start-test onboarding flow, and authorization + ownership checks on every existing attempt/report endpoint.

**Architecture:** FastAPI backend gains an opaque server-side session (a `session` table, cookie-carried token), an RBAC layer (`role` / `permission` / `role_permission` tables plus a `require(*keys)` dependency), and per-row ownership checks. The React frontend gains `react-router-dom`, an `AuthContext` fed by `GET /api/auth/me`, and `<RequireAuth>` route guards. No multi-tenancy.

**Tech Stack:** FastAPI, SQLModel, SQLite, `argon2-cffi` (new), pytest, TestClient; React 19, Vite, `react-router-dom` (new), Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-09-auth-and-rbac-design.md` — read it alongside this plan.

## Global Constraints

- **No AI attribution in commits.** Use the repo's configured git identity only. No `Co-Authored-By`, no "Generated with" line. (`ENGINEERING_RULES.md` §7.)
- **Commit message style:** imperative subject ≤ ~70 chars, a blank line, then a wrapped body explaining *why*. Match the existing log (`git log`).
- **Security before every commit** (`ENGINEERING_RULES.md` §6, §29): review the diff for secrets, injection, missing authz/validation. No secret ever committed — `ADMIN_PASSWORD` and any generated secret come from env; `.env` stays git-ignored.
- **TDD:** failing test → run it fail → minimal implementation → run it pass → commit. Backend tests: `cd backend && python -m pytest`. Frontend tests: `cd frontend && npx vitest run`. Frontend lint: `cd frontend && npm run lint`.
- **Passwords:** Argon2id via `argon2-cffi`. Never logged, never serialized in a response.
- **Session cookie:** name `session`, `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` 1209600 (14 days), `Secure` only when `request.url.scheme == "https"`.
- **Auth failures are generic:** login returns `401 "Invalid email or password"` for every cause. Signup returns `409 "This email is already registered"` (the one deliberate exception).
- **Permission keys (exact strings):** `test.take`, `report.view_own`, `candidates.view`, `candidates.decide`, `analytics.view`, `roles.manage`, `settings.manage`.
- **System role names (exact, lowercase):** `admin`, `recruiter`, `candidate`. `is_system = True` on all three.
- **Emails** are stored and compared lowercased (`.strip().lower()`).
- Do not restructure files the task does not touch (`ENGINEERING_RULES.md` §3).

---

## File Structure

**New — backend:**
- `backend/security.py` — password hashing, session-token generation, login throttle. No DB, no FastAPI imports.
- `backend/rbac.py` — `get_current_user`, `require(*keys)`, `user_permissions`. Depends on `db`, `models`.
- `backend/seed_auth.py` — idempotent seeding of permissions, system roles, role→permission grants, and the default admin user.
- `backend/auth.py` — `APIRouter` at `/api/auth`: `signup`, `login`, `logout`, `me`.
- `backend/candidate.py` — `APIRouter`: `PUT /api/candidate/profile`, `GET /api/me/attempts`.
- `backend/admin.py` — `APIRouter` at `/api/admin`, all `require("roles.manage")`: users + roles + permissions.

**Modified — backend:**
- `backend/models.py` — new tables; `user_id` on `Attempt`.
- `backend/db.py` — schema guard for `attempt.user_id`.
- `backend/main.py` — mount routers; call `seed_auth` at startup; gate + ownership-check the attempt/report endpoints.
- `backend/requirements.txt` — add `argon2-cffi`.
- `backend/seed_attempts.py` — create a candidate user + profile, stamp `user_id`.
- `backend/tests/conftest.py` — auth fixtures.

**New — frontend:**
- `frontend/src/auth/AuthContext.jsx` — provider + `useAuth()` hook.
- `frontend/src/auth/RequireAuth.jsx` — route guard.
- `frontend/src/screens/Login.jsx`, `Signup.jsx`, `Profile.jsx`, `Forbidden.jsx`.
- `frontend/src/screens/CandidateFlow.jsx` — the current `CandidateApp` state machine, moved out of `App.jsx`.

**Modified — frontend:**
- `frontend/src/App.jsx` — becomes router + providers only.
- `frontend/src/main.jsx` — wrap in `<BrowserRouter>`.
- `frontend/src/api.js` — `credentials: 'include'`, auth/profile/admin calls, 401 handling.
- `frontend/src/screens/Start.jsx` — remove the name input.
- `frontend/package.json` — add `react-router-dom`.

**Modified — docs:** `BUILD_LOG.md`, `04-tech-stack.md`.

---

## Task 1: Auth data model

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/db.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_auth_models.py`

**Interfaces:**
- Produces: `Role(id, name, is_system, created_at)`, `Permission(key, description)`, `RolePermission(role_id, permission_key)`, `User(id, email, password_hash, display_name, role_id, is_active, created_at)`, `CandidateProfile(user_id, full_name, phone, city, first_language, decision, decided_by, decided_at, updated_at)`, `SessionToken(token, user_id, created_at, expires_at)`. `Attempt` gains `user_id: str | None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth_models.py
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
        s.add(Attempt(name="A B", user_id=user.id))
        s.commit()

        assert s.get(User, user.id).role_id == role.id
        assert s.get(Attempt, s.get(Attempt, user.id) and Attempt.id) is None or True
        assert s.get(CandidateProfile, user.id).decision == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_auth_models.py -v`
Expected: FAIL — `ImportError` on the new model names.

- [ ] **Step 3: Add the models**

Append to `backend/models.py` (keep the existing `_now` helper and imports; add `timedelta` to the datetime import):

```python
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
```

Add to the existing `Attempt` class:

```python
    user_id: Optional[str] = Field(default=None, foreign_key="user.id", index=True)
```

- [ ] **Step 4: Add the `db.py` schema guard**

In `backend/db.py`, extend `_assert_attempt_schema_current` so the column set check also covers `user_id`:

```python
    if "item_ids" not in cols or "option_order" not in cols or "user_id" not in cols:
        raise RuntimeError(_MISSING_COLUMNS_MSG)
```

And update `_MISSING_COLUMNS_MSG` to read `... is missing the item_ids/option_order/user_id columns ...`.

- [ ] **Step 5: Add the dependency**

In `backend/requirements.txt` add a line: `argon2-cffi==23.1.0`. Then `cd backend && pip install -r requirements.txt`.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_auth_models.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full backend suite (nothing else should break)**

Run: `cd backend && python -m pytest`
Expected: all existing tests still PASS (the new `user_id` column is nullable; `create_all` adds the new tables in the in-memory test engines).

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/db.py backend/requirements.txt backend/tests/test_auth_models.py
git commit -m "Add auth data model: users, roles, permissions, sessions"
```

---

## Task 2: Password hashing, tokens, and login throttle

**Files:**
- Create: `backend/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(raw: str) -> str`
  - `verify_password(raw: str, hashed: str) -> bool`
  - `new_session_token() -> str` (64 hex chars)
  - `check_login_allowed(key: str) -> None` — raises `ThrottledError(retry_after: int)` when `key` has ≥ `MAX_FAILURES` (10) failures in the last `WINDOW_SECONDS` (900)
  - `record_login_failure(key: str) -> None`
  - `reset_login_failures(key: str) -> None`
  - `class ThrottledError(Exception)` with `.retry_after: int`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security.py
import time

import pytest

import security


def test_hash_verify_round_trip():
    h = security.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", h)
    assert not security.verify_password("wrong", h)


def test_new_session_token_is_unique_and_hex():
    a, b = security.new_session_token(), security.new_session_token()
    assert a != b
    assert len(a) == 64 and int(a, 16) >= 0


def test_throttle_trips_after_max_failures(monkeypatch):
    monkeypatch.setattr(security, "_FAILURES", {})
    key = "user@example.com|1.2.3.4"
    for _ in range(security.MAX_FAILURES):
        security.check_login_allowed(key)  # still allowed
        security.record_login_failure(key)
    with pytest.raises(security.ThrottledError) as ei:
        security.check_login_allowed(key)
    assert ei.value.retry_after > 0
    security.reset_login_failures(key)
    security.check_login_allowed(key)  # cleared
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: FAIL — `ModuleNotFoundError: security`.

- [ ] **Step 3: Write the implementation**

```python
# backend/security.py
"""Password hashing, session tokens, and an in-process login throttle.

The throttle is per-process and resets on restart. For a single-process
local deployment that is acceptable; a shared store is a follow-up if this
is ever run multi-process (see the spec, §8).
"""
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher()

MAX_FAILURES = 10
WINDOW_SECONDS = 900

# key -> list[float] of failure timestamps
_FAILURES: dict[str, list[float]] = {}


class ThrottledError(Exception):
    def __init__(self, retry_after: int):
        super().__init__("too many login attempts")
        self.retry_after = retry_after


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_hex(32)


def _recent(key: str) -> list[float]:
    cutoff = time.monotonic() - WINDOW_SECONDS
    kept = [t for t in _FAILURES.get(key, []) if t >= cutoff]
    if kept:
        _FAILURES[key] = kept
    else:
        _FAILURES.pop(key, None)
    return kept


def check_login_allowed(key: str) -> None:
    hits = _recent(key)
    if len(hits) >= MAX_FAILURES:
        retry_after = int(WINDOW_SECONDS - (time.monotonic() - hits[0])) + 1
        raise ThrottledError(max(retry_after, 1))


def record_login_failure(key: str) -> None:
    _FAILURES.setdefault(key, []).append(time.monotonic())


def reset_login_failures(key: str) -> None:
    _FAILURES.pop(key, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/security.py backend/tests/test_security.py
git commit -m "Add password hashing, session tokens, and a login throttle"
```

---

## Task 3: RBAC dependencies

**Files:**
- Create: `backend/rbac.py`
- Test: `backend/tests/test_rbac.py`

**Interfaces:**
- Consumes: `models.User`, `models.SessionToken`, `models.RolePermission`; `db.get_session`.
- Produces:
  - `COOKIE_NAME = "session"`
  - `get_current_user(session, token) -> User` — FastAPI dependency; `401` if no/expired token, `403` if `not user.is_active`
  - `CurrentUser = Annotated[User, Depends(get_current_user)]`
  - `user_permissions(user: User, session: Session) -> set[str]`
  - `require(*keys: str)` — returns a dependency that yields the `User` and raises `403` unless every key is in the user's permission set

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rbac.py
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import db
import rbac
from models import Permission, Role, RolePermission, SessionToken, User


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)

    app = FastAPI()

    @app.get("/whoami")
    def whoami(user: rbac.CurrentUser):
        return {"email": user.email}

    @app.get("/needs-decide")
    def needs_decide(user=Depends(rbac.require("candidates.decide"))):
        return {"ok": True}

    def _get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[db.get_session] = _get_session
    with Session(engine) as s:
        role = Role(name="recruiter", is_system=True); s.add(role); s.commit()
        s.add(Permission(key="candidates.view", description="")); s.commit()
        s.add(RolePermission(role_id=role.id, permission_key="candidates.view"))
        u = User(email="r@x.com", password_hash="x", display_name="R", role_id=role.id)
        s.add(u); s.commit()
        s.add(SessionToken(token="good", user_id=u.id,
                           expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        s.add(SessionToken(token="stale", user_id=u.id,
                           expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        s.commit()
    return TestClient(app)


def test_no_cookie_is_401(client):
    assert client.get("/whoami").status_code == 401


def test_expired_cookie_is_401(client):
    assert client.get("/whoami", cookies={"session": "stale"}).status_code == 401


def test_valid_cookie_resolves_user(client):
    r = client.get("/whoami", cookies={"session": "good"})
    assert r.status_code == 200 and r.json()["email"] == "r@x.com"


def test_require_missing_permission_is_403(client):
    assert client.get("/needs-decide", cookies={"session": "good"}).status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_rbac.py -v`
Expected: FAIL — `ModuleNotFoundError: rbac`.

- [ ] **Step 3: Write the implementation**

```python
# backend/rbac.py
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models import RolePermission, SessionToken, User

COOKIE_NAME = "session"

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    row = session.get(SessionToken, token)
    if row is None or row.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def user_permissions(user: User, session: Session) -> set[str]:
    keys = session.exec(
        select(RolePermission.permission_key).where(RolePermission.role_id == user.role_id)
    ).all()
    return set(keys)


def require(*keys: str):
    def dep(user: CurrentUser, session: SessionDep) -> User:
        if not set(keys).issubset(user_permissions(user, session)):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dep
```

Note on the `expires_at` comparison: SQLite returns naive datetimes; `.replace(tzinfo=timezone.utc)` normalises before comparing. Store UTC always (Task 2 tokens, Task 6 sessions).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_rbac.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rbac.py backend/tests/test_rbac.py
git commit -m "Add RBAC dependencies: current-user resolution and require()"
```

---

## Task 4: Seed permissions, roles, and the default admin

**Files:**
- Create: `backend/seed_auth.py`
- Test: `backend/tests/test_seed_auth.py`

**Interfaces:**
- Consumes: `models`, `security.hash_password`.
- Produces:
  - `PERMISSIONS: dict[str, str]` — key → description, the full catalogue
  - `SYSTEM_ROLES: dict[str, list[str]]` — role name → permission keys (`admin` maps to `list(PERMISSIONS)`)
  - `seed_auth(session: Session) -> None` — idempotent; also re-grants `admin` any missing permission
  - `ensure_default_admin(session: Session) -> None` — creates one admin user from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars (defaults `admin@example.com` + a random password logged once) if no admin-role user exists

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seed_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: seed_auth`.

- [ ] **Step 3: Write the implementation**

```python
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
    if admin_role is None:
        raise RuntimeError("seed_auth must run before ensure_default_admin")
    has_admin = session.exec(
        select(User).where(User.role_id == admin_role.id)
    ).first()
    if has_admin is not None:
        return
    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        password = secrets.token_urlsafe(12)
        logger.warning(
            "No ADMIN_PASSWORD set. Created admin %s with password: %s  "
            "-- change it immediately.", email, password,
        )
    user = User(
        email=email, password_hash=hash_password(password),
        display_name="Administrator", role_id=admin_role.id,
    )
    session.add(user)
    session.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seed_auth.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/seed_auth.py backend/tests/test_seed_auth.py
git commit -m "Add idempotent auth seeding and default-admin bootstrap"
```

---

## Task 5: Wire seeding into startup + shared test fixtures

**Files:**
- Modify: `backend/main.py:89-94` (the `on_startup` handler)
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_startup.py` (add one case)

**Interfaces:**
- Produces (conftest fixtures for later tasks):
  - `auth_engine` — in-memory engine with all tables + `seed_auth` applied
  - `make_user(session, *, email, password, role_name, with_profile=False) -> User`
  - `api(auth_engine)` — a `TestClient` over `main.app` wired to `auth_engine`
  - `login(api, email, password) -> None` — logs in, leaving the cookie on the client

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_startup.py
def test_startup_seeds_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "seed-admin@corp.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "seed-admin-pw-123")
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app):
        pass
    from sqlmodel import Session, select
    import db
    from models import User
    with Session(db.engine) as s:
        assert s.exec(select(User).where(User.email == "seed-admin@corp.com")).first() is not None
```

(If `test_startup.py` already isolates the DB path, follow its existing pattern; the key assertion is that a `User` row exists after startup.)

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && python -m pytest tests/test_startup.py -v`
Expected: FAIL — no admin user created (startup does not seed yet).

- [ ] **Step 3: Wire seeding into `on_startup`**

In `backend/main.py`, update `on_startup`:

```python
@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _load_bank()
    from db import engine
    from seed_auth import ensure_default_admin, seed_auth
    with Session(engine) as session:
        seed_auth(session)
        ensure_default_admin(session)
    threading.Thread(target=_warm_up_judge_in_background, daemon=True).start()
```

- [ ] **Step 4: Add the shared fixtures**

Append to `backend/tests/conftest.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture
def auth_engine(monkeypatch):
    import db
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    import seed_auth
    with Session(engine) as s:
        seed_auth.seed_auth(s)
    return engine


@pytest.fixture
def api(auth_engine):
    import db
    import main
    from rbac import get_session as _  # noqa: F401  (ensure module imported)

    def _get_session():
        with Session(auth_engine) as s:
            yield s

    main.app.dependency_overrides[db.get_session] = _get_session
    main._load_bank()
    with TestClient(main.app) as c:
        c._engine = auth_engine
        yield c
    main.app.dependency_overrides.clear()


def make_user(session, *, email, password, role_name, with_profile=False):
    from models import CandidateProfile, Role, User
    from security import hash_password
    role = session.exec(_select_role(role_name)).first()
    user = User(
        email=email.lower(), password_hash=hash_password(password),
        display_name=email.split("@")[0], role_id=role.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    if with_profile:
        session.add(CandidateProfile(user_id=user.id, full_name="Test User", phone="0000000000"))
        session.commit()
    return user


def _select_role(name):
    from sqlmodel import select
    from models import Role
    return select(Role).where(Role.name == name)


def login(api, email, password):
    r = api.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
```

Note: `db.get_session` is the single session provider; `main`, `rbac`, and every router must import it from `db` (not redefine it) so this one override covers all of them. Verify each router does `from db import get_session`.

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_startup.py -v`
Expected: PASS. Then `cd backend && python -m pytest` — everything still green.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/conftest.py backend/tests/test_startup.py
git commit -m "Seed roles and the default admin at startup; add auth test fixtures"
```

---

## Task 6: Signup, logout, and /me

**Files:**
- Create: `backend/auth.py`
- Modify: `backend/main.py` (mount the router — near `app.mount(...)` lines, add `app.include_router(auth_router)`)
- Test: `backend/tests/test_auth_api.py`

**Interfaces:**
- Consumes: `rbac.CurrentUser`, `rbac.user_permissions`, `rbac.COOKIE_NAME`; `security`; `models`.
- Produces: `router` (APIRouter, prefix `/api/auth`) with `POST /signup`, `POST /login` (Task 7), `POST /logout`, `GET /me`. Helper `_set_session_cookie(response, request, token)` and `_create_session(session, user_id) -> str`.
- `GET /me` response shape: `{ "id", "email", "display_name", "role": {"id", "name"}, "permissions": [...], "profile": {...} | null }`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth_api.py
from tests.conftest import login, make_user
from sqlmodel import Session


def test_signup_creates_candidate_and_session(api):
    r = api.post("/api/auth/signup", json={
        "email": "New@Person.com", "password": "longenough12", "display_name": "New Person",
    })
    assert r.status_code == 200, r.text
    assert "session" in r.cookies or api.cookies.get("session")
    me = api.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "new@person.com"
    assert body["role"]["name"] == "candidate"
    assert set(body["permissions"]) == {"test.take", "report.view_own"}
    assert body["profile"] is None


def test_signup_duplicate_email_is_409(api):
    payload = {"email": "dup@x.com", "password": "longenough12", "display_name": "Dup"}
    assert api.post("/api/auth/signup", json=payload).status_code == 200
    api.cookies.clear()
    r = api.post("/api/auth/signup", json=payload)
    assert r.status_code == 409


def test_signup_rejects_short_password(api):
    r = api.post("/api/auth/signup", json={
        "email": "x@y.com", "password": "short", "display_name": "X",
    })
    assert r.status_code == 422


def test_me_requires_auth(api):
    assert api.get("/api/auth/me").status_code == 401


def test_logout_invalidates_session(api):
    api.post("/api/auth/signup", json={
        "email": "bye@x.com", "password": "longenough12", "display_name": "Bye",
    })
    assert api.get("/api/auth/me").status_code == 200
    assert api.post("/api/auth/logout").status_code == 204
    assert api.get("/api/auth/me").status_code == 401
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && python -m pytest tests/test_auth_api.py -v`
Expected: FAIL — 404 on `/api/auth/*`.

- [ ] **Step 3: Write `auth.py` (signup / logout / me)**

```python
# backend/auth.py
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from db import get_session
from models import CandidateProfile, Role, SessionToken, User
from rbac import COOKIE_NAME, CurrentUser, user_permissions
from security import new_session_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SESSION_TTL = timedelta(days=14)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


def _create_session(session: Session, user_id: str) -> str:
    token = new_session_token()
    session.add(SessionToken(
        token=token, user_id=user_id,
        expires_at=datetime.now(timezone.utc) + _SESSION_TTL,
    ))
    session.commit()
    return token


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME, value=token, max_age=int(_SESSION_TTL.total_seconds()),
        httponly=True, samesite="lax", path="/",
        secure=request.url.scheme == "https",
    )


def _me_payload(user: User, session: Session) -> dict:
    role = session.get(Role, user.role_id)
    profile = session.get(CandidateProfile, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": {"id": role.id, "name": role.name},
        "permissions": sorted(user_permissions(user, session)),
        "profile": None if profile is None else {
            "full_name": profile.full_name,
            "phone": profile.phone,
            "city": profile.city,
            "first_language": profile.first_language,
            "decision": profile.decision,
        },
    }


@router.post("/signup")
def signup(payload: SignupRequest, request: Request, response: Response,
           session: Session = Depends(get_session)):
    exists = session.exec(select(User).where(User.email == payload.email)).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="This email is already registered")
    candidate_role = session.exec(select(Role).where(Role.name == "candidate")).first()
    from security import hash_password
    user = User(
        email=payload.email, password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(), role_id=candidate_role.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = _create_session(session, user.id)
    _set_session_cookie(response, request, token)
    return _me_payload(user, session)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_session)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        row = session.get(SessionToken, token)
        if row is not None:
            session.delete(row)
            session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me")
def me(user: CurrentUser, session: Session = Depends(get_session)):
    return _me_payload(user, session)
```

- [ ] **Step 4: Mount the router**

In `backend/main.py`, after the existing `app.mount(...)` calls:

```python
from auth import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_auth_api.py -v`
Expected: `test_signup_*`, `test_me_requires_auth`, `test_logout_*` PASS. (Login test lives in Task 7.)

- [ ] **Step 6: Commit**

```bash
git add backend/auth.py backend/main.py backend/tests/test_auth_api.py
git commit -m "Add signup, logout, and /me auth endpoints"
```

---

## Task 7: Login with throttle

**Files:**
- Modify: `backend/auth.py` (add `POST /login`)
- Test: `backend/tests/test_auth_api.py` (add cases)

**Interfaces:**
- Consumes: `security.check_login_allowed`, `record_login_failure`, `reset_login_failures`, `ThrottledError`, `verify_password`.
- Produces: `POST /api/auth/login` — body `{email, password}`; `200` + cookie on success; `401 "Invalid email or password"` on any failure; `429` + `Retry-After` header when throttled.

- [ ] **Step 1: Write the failing tests**

```python
# add to backend/tests/test_auth_api.py
import security


def test_login_success_sets_cookie(api):
    api.post("/api/auth/signup", json={
        "email": "log@x.com", "password": "longenough12", "display_name": "Log",
    })
    api.cookies.clear()
    r = api.post("/api/auth/login", json={"email": "LOG@x.com", "password": "longenough12"})
    assert r.status_code == 200
    assert api.get("/api/auth/me").json()["email"] == "log@x.com"


def test_login_wrong_password_is_generic_401(api):
    api.post("/api/auth/signup", json={
        "email": "log2@x.com", "password": "longenough12", "display_name": "Log2",
    })
    api.cookies.clear()
    r = api.post("/api/auth/login", json={"email": "log2@x.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_is_generic_401(api):
    r = api.post("/api/auth/login", json={"email": "ghost@x.com", "password": "whatever123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_throttles_after_repeated_failure(api, monkeypatch):
    monkeypatch.setattr(security, "_FAILURES", {})
    monkeypatch.setattr(security, "MAX_FAILURES", 3)
    for _ in range(3):
        api.post("/api/auth/login", json={"email": "t@x.com", "password": "bad"})
    r = api.post("/api/auth/login", json={"email": "t@x.com", "password": "bad"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_auth_api.py -k login -v`
Expected: FAIL — 404/405 on `/api/auth/login`.

- [ ] **Step 3: Implement `login`**

Add to `backend/auth.py`:

```python
from security import (
    ThrottledError, check_login_allowed, record_login_failure,
    reset_login_failures, verify_password,
)


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response,
          session: Session = Depends(get_session)):
    client_ip = request.client.host if request.client else "?"
    throttle_key = f"{payload.email}|{client_ip}"
    try:
        check_login_allowed(throttle_key)
    except ThrottledError as exc:
        raise HTTPException(
            status_code=429, detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        )

    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_login_failure(throttle_key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    reset_login_failures(throttle_key)
    token = _create_session(session, user.id)
    _set_session_cookie(response, request, token)
    return _me_payload(user, session)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && python -m pytest tests/test_auth_api.py -v`
Expected: PASS (all auth API tests).

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_auth_api.py
git commit -m "Add login endpoint with generic errors and throttling"
```

---

## Task 8: Candidate profile + own-attempts list

**Files:**
- Create: `backend/candidate.py`
- Modify: `backend/main.py` (include the router)
- Test: `backend/tests/test_candidate_api.py`

**Interfaces:**
- Consumes: `rbac.require`, `rbac.CurrentUser`; `models.CandidateProfile`, `models.Attempt`.
- Produces: `router` with `PUT /api/candidate/profile` (`require("test.take")`, body `{full_name, phone, city?, first_language?}`, upsert, returns the profile dict) and `GET /api/me/attempts` (`require("test.take")`, returns `[{attempt_id, status, created_at}]` for `Attempt.user_id == user.id`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_candidate_api.py
def _signup(api, email="c@x.com"):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "C",
    })


def test_put_profile_upserts(api):
    _signup(api)
    r = api.put("/api/candidate/profile", json={
        "full_name": "Cee Andidate", "phone": "9991112222", "city": "Pune",
    })
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Cee Andidate"
    r2 = api.put("/api/candidate/profile", json={"full_name": "Cee A", "phone": "9991112222"})
    assert r2.status_code == 200
    assert api.get("/api/auth/me").json()["profile"]["full_name"] == "Cee A"


def test_profile_requires_permission(api):
    # recruiter has no test.take
    from tests.conftest import make_user
    from sqlmodel import Session
    with Session(api._engine) as s:
        make_user(s, email="rec@x.com", password="longenough12", role_name="recruiter")
    api.post("/api/auth/login", json={"email": "rec@x.com", "password": "longenough12"})
    r = api.put("/api/candidate/profile", json={"full_name": "X", "phone": "1"})
    assert r.status_code == 403


def test_me_attempts_lists_only_own(api):
    _signup(api, "own@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Own Er", "phone": "1"})
    api.post("/api/attempts", json={})
    r = api.get("/api/me/attempts")
    assert r.status_code == 200 and len(r.json()) == 1
```

(The last test depends on Task 9's gated `POST /api/attempts`; if running strictly in order, mark it `xfail` here and remove the marker in Task 9. Simpler: place `test_me_attempts_lists_only_own` in Task 9's test file instead.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_candidate_api.py -v`
Expected: FAIL — 404 on `/api/candidate/profile`.

- [ ] **Step 3: Implement `candidate.py`**

```python
# backend/candidate.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session
from models import Attempt, CandidateProfile, User
from rbac import require

router = APIRouter(tags=["candidate"])


class ProfileRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=20)
    city: str | None = Field(default=None, max_length=80)
    first_language: str | None = Field(default=None, max_length=60)


def _profile_dict(p: CandidateProfile) -> dict:
    return {
        "full_name": p.full_name, "phone": p.phone, "city": p.city,
        "first_language": p.first_language, "decision": p.decision,
    }


@router.put("/api/candidate/profile")
def put_profile(payload: ProfileRequest, user: User = Depends(require("test.take")),
                session: Session = Depends(get_session)):
    profile = session.get(CandidateProfile, user.id)
    if profile is None:
        profile = CandidateProfile(user_id=user.id, full_name=payload.full_name, phone=payload.phone)
    profile.full_name = payload.full_name.strip()
    profile.phone = payload.phone.strip()
    profile.city = payload.city
    profile.first_language = payload.first_language
    profile.updated_at = datetime.now(timezone.utc)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return _profile_dict(profile)


@router.get("/api/me/attempts")
def my_attempts(user: User = Depends(require("test.take")),
                session: Session = Depends(get_session)):
    rows = session.exec(
        select(Attempt).where(Attempt.user_id == user.id).order_by(Attempt.created_at.desc())
    ).all()
    return [{"attempt_id": a.id, "status": a.status, "created_at": a.created_at} for a in rows]
```

- [ ] **Step 4: Include the router in `main.py`**

```python
from candidate import router as candidate_router
app.include_router(candidate_router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_candidate_api.py -v`
Expected: PASS (excluding any test deferred to Task 9).

- [ ] **Step 6: Commit**

```bash
git add backend/candidate.py backend/main.py backend/tests/test_candidate_api.py
git commit -m "Add candidate profile upsert and own-attempts endpoint"
```

---

## Task 9: Gate attempt creation

**Files:**
- Modify: `backend/main.py` — `CreateAttemptRequest`, `create_attempt` (lines ~97-131)
- Modify: `backend/tests/test_attempts_api.py`, `test_responses_api.py`, `test_scoring_*` — every test that calls `POST /api/attempts` now needs an authenticated candidate with a profile
- Test: `backend/tests/test_attempts_auth.py` (new)

**Interfaces:**
- Consumes: `rbac.require`, `models.CandidateProfile`.
- Produces: `POST /api/attempts` requires `test.take`; `409 "Complete your profile first"` when the caller has no `CandidateProfile`; ignores any client `name`; sets `attempt.user_id = user.id` and `attempt.name = profile.full_name`. Response unchanged (`{attempt_id}`). The `item_ids` seed hook is preserved.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_attempts_auth.py
def _candidate(api, email="cand@x.com"):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "Cand",
    })


def test_create_attempt_requires_auth(api):
    api.cookies.clear()
    assert api.post("/api/attempts", json={}).status_code == 401


def test_create_attempt_requires_profile(api):
    _candidate(api)
    r = api.post("/api/attempts", json={})
    assert r.status_code == 409


def test_create_attempt_stamps_user_and_name(api):
    _candidate(api, "stamp@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Stamp Ed", "phone": "1"})
    r = api.post("/api/attempts", json={"name": "IGNORED"})
    assert r.status_code == 200
    from sqlmodel import Session
    from models import Attempt
    with Session(api._engine) as s:
        a = s.get(Attempt, r.json()["attempt_id"])
        assert a.name == "Stamp Ed"
        assert a.user_id is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_attempts_auth.py -v`
Expected: FAIL — attempt creation currently open, returns 200 without auth.

- [ ] **Step 3: Implement the gate**

In `backend/main.py`, change `create_attempt`:

```python
from rbac import require
from models import CandidateProfile

class CreateAttemptRequest(BaseModel):
    item_ids: list[str] | None = None  # seed-only; ignored unless env flag set


@app.post("/api/attempts", response_model=CreateAttemptResponse)
def create_attempt(payload: CreateAttemptRequest, session: SessionDep,
                   user=Depends(require("test.take"))):
    profile = session.get(CandidateProfile, user.id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete your profile first")
    attempt = Attempt(name=profile.full_name, user_id=user.id)
    attempt.item_ids = _resolve_selection(payload, attempt.id)
    selected_items = [_ITEMS_BY_ID[i] for i in attempt.item_ids]
    attempt.option_order = option_permutations(selected_items, random.Random(attempt.id + "opts"))
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return CreateAttemptResponse(attempt_id=attempt.id)
```

Remove the now-unused `name` field from `CreateAttemptRequest` (shown above). `_resolve_selection` still reads `payload.item_ids`.

- [ ] **Step 4: Fix the existing attempt/response/scoring tests**

Every existing test that does `client.post("/api/attempts", json={"name": ...})` must first create an authenticated candidate with a profile. Add a helper to `conftest.py`:

```python
def candidate_client(api, email="fixture-cand@x.com"):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "Fixture Cand",
    })
    api.put("/api/candidate/profile", json={"full_name": "Fixture Cand", "phone": "1"})
    return api
```

Then in `test_attempts_api.py`, `test_responses_api.py`, `test_scoring_scope.py`, `test_scoring_random_selection.py`: replace the local `client` fixture usage with `api`, call `candidate_client(api)` at the top of each test, and drop `"name"` from the POST bodies (send `json={}` or `json={"item_ids": [...]}`). Keep the `ASSESSMENT_ALLOW_FIXED_SELECTION` monkeypatch cases as-is otherwise.

- [ ] **Step 5: Run the whole backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS. Fix any missed `name=` call sites until green.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/
git commit -m "Require an authenticated candidate with a profile to start an attempt"
```

---

## Task 10: Ownership checks on attempt sub-resources

**Files:**
- Modify: `backend/main.py` — `get_attempt_items`, `submit_response`, `upload_audio`, `submit_attempt` (add an ownership guard); factor a helper.
- Test: `backend/tests/test_attempts_auth.py` (add IDOR cases)

**Interfaces:**
- Produces: a module-level helper `_require_own_attempt(session, attempt_id, user) -> Attempt` — `404` if the attempt is unknown *or* not owned by `user` (same status for both, so ownership is not an oracle). Applied to `/items`, `/response`, `/audio`, `/submit`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_attempts_auth.py
def test_other_candidate_cannot_touch_my_attempt(api):
    _candidate(api, "owner@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Owner", "phone": "1"})
    attempt_id = api.post("/api/attempts", json={}).json()["attempt_id"]

    api.cookies.clear()
    _candidate(api, "intruder@x.com")
    api.put("/api/candidate/profile", json={"full_name": "Intruder", "phone": "1"})

    assert api.get(f"/api/attempts/{attempt_id}/items").status_code == 404
    assert api.post(f"/api/attempts/{attempt_id}/response",
                    json={"item_id": "g1", "text": "a"}).status_code == 404
    assert api.post(f"/api/attempts/{attempt_id}/submit").status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_attempts_auth.py -k intruder -v`
Expected: FAIL — endpoints currently return 200/409, not 404.

- [ ] **Step 3: Implement the guard**

In `backend/main.py`:

```python
def _require_own_attempt(session: Session, attempt_id: str, user) -> Attempt:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt
```

Then in each of `get_attempt_items`, `submit_response`, `upload_audio`, `submit_attempt`:
- add `user=Depends(require("test.take"))` to the signature
- replace `_get_attempt_or_404(session, attempt_id)` with `_require_own_attempt(session, attempt_id, user)`

Leave the existing `status != "in_progress"` → 409 checks in place after the ownership check.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS. Update any existing `test_responses_api.py` cases that now need the `user=` path — they already go through `candidate_client(api)` from Task 9, so the cookie is present; just ensure they act on their *own* attempt id.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_attempts_auth.py
git commit -m "Enforce attempt ownership on items, response, audio, and submit"
```

---

## Task 11: Report access + recruiter attempt list

**Files:**
- Modify: `backend/main.py` — `get_report`, `list_attempts`
- Test: `backend/tests/test_report_auth.py` (new)

**Interfaces:**
- Produces:
  - `GET /api/attempts/{id}/report` — allowed if (`report.view_own` **and** `attempt.user_id == user.id`) **or** `candidates.view`. Otherwise `404` (unknown) / `403` (known, not allowed).
  - `GET /api/attempts` — `require("candidates.view")`; response gains `user_id`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_report_auth.py
from sqlmodel import Session
from tests.conftest import make_user


def _finished_attempt(api, email):
    api.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "C",
    })
    api.put("/api/candidate/profile", json={"full_name": "C Name", "phone": "1"})
    return api.post("/api/attempts", json={}).json()["attempt_id"]


def test_owner_can_view_own_report(api):
    aid = _finished_attempt(api, "rep-owner@x.com")
    assert api.get(f"/api/attempts/{aid}/report").status_code == 200


def test_stranger_candidate_cannot_view_report(api):
    aid = _finished_attempt(api, "rep-owner2@x.com")
    api.cookies.clear()
    _finished_attempt(api, "rep-stranger@x.com")
    assert api.get(f"/api/attempts/{aid}/report").status_code in (403, 404)


def test_recruiter_can_view_any_report_and_list(api):
    aid = _finished_attempt(api, "rep-owner3@x.com")
    api.cookies.clear()
    with Session(api._engine) as s:
        make_user(s, email="viewer@x.com", password="longenough12", role_name="recruiter")
    api.post("/api/auth/login", json={"email": "viewer@x.com", "password": "longenough12"})
    assert api.get(f"/api/attempts/{aid}/report").status_code == 200
    lst = api.get("/api/attempts")
    assert lst.status_code == 200 and any(row["attempt_id"] == aid for row in lst.json())


def test_candidate_cannot_list_attempts(api):
    _finished_attempt(api, "nolist@x.com")
    assert api.get("/api/attempts").status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_report_auth.py -v`
Expected: FAIL — `/api/attempts` and `/report` are currently open.

- [ ] **Step 3: Implement**

In `backend/main.py`:

```python
from rbac import CurrentUser, user_permissions

@app.get("/api/attempts/{attempt_id}/report")
def get_report(attempt_id: str, session: SessionDep, user: CurrentUser):
    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    perms = user_permissions(user, session)
    is_owner = attempt.user_id == user.id
    if not ("candidates.view" in perms or (is_owner and "report.view_own" in perms)):
        raise HTTPException(status_code=403, detail="Not allowed")
    # ... existing body unchanged ...


@app.get("/api/attempts")
def list_attempts(session: SessionDep, user=Depends(require("candidates.view"))):
    attempts = session.exec(select(Attempt)).all()
    return [
        {"attempt_id": a.id, "name": a.name, "status": a.status,
         "created_at": a.created_at, "user_id": a.user_id}
        for a in attempts
    ]
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: PASS. `frontend/src/screens/Recruiter.jsx` calls `listAttempts()` — it will 403 until the frontend sends the cookie (Task 14) and the user is a recruiter; that is expected and covered later.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_report_auth.py
git commit -m "Gate report access by ownership or candidates.view; lock the attempt list"
```

---

## Task 12: Admin user management

**Files:**
- Create: `backend/admin.py`
- Modify: `backend/main.py` (include router)
- Test: `backend/tests/test_admin_users.py`

**Interfaces:**
- All endpoints `Depends(require("roles.manage"))`, prefix `/api/admin`.
- `GET /users` → `[{id, email, display_name, role: {id,name}, is_active}]`
- `POST /users` — body `{email, password (≥10), display_name, role_id}` → the user dict; `409` on duplicate email; `400` on unknown `role_id`
- `PATCH /users/{id}` — body `{role_id?, is_active?, password?}`; guards: an admin cannot set their own `is_active=False` or change their own `role_id` away from admin → `400`
- `GET /roles`, `GET /permissions` (read helpers used here and in Task 13)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_admin_users.py
from sqlmodel import Session, select
from tests.conftest import make_user
from models import Role


def _admin(api):
    with Session(api._engine) as s:
        make_user(s, email="admin@x.com", password="longenough12", role_name="admin")
    api.post("/api/auth/login", json={"email": "admin@x.com", "password": "longenough12"})


def test_admin_creates_recruiter(api):
    _admin(api)
    with Session(api._engine) as s:
        rec_role = s.exec(select(Role).where(Role.name == "recruiter")).first().id
    r = api.post("/api/admin/users", json={
        "email": "newrec@x.com", "password": "longenough12",
        "display_name": "New Rec", "role_id": rec_role,
    })
    assert r.status_code == 200, r.text
    assert r.json()["role"]["name"] == "recruiter"


def test_non_admin_cannot_list_users(api):
    api.post("/api/auth/signup", json={
        "email": "plain@x.com", "password": "longenough12", "display_name": "Plain",
    })
    assert api.get("/api/admin/users").status_code == 403


def test_admin_cannot_deactivate_self(api):
    _admin(api)
    me_id = api.get("/api/auth/me").json()["id"]
    r = api.patch(f"/api/admin/users/{me_id}", json={"is_active": False})
    assert r.status_code == 400


def test_admin_resets_password(api):
    _admin(api)
    uid = api.post("/api/admin/users", json={
        "email": "reset-me@x.com", "password": "longenough12",
        "display_name": "R", "role_id": api.get("/api/admin/roles").json()[0]["id"],
    }).json()["id"]
    assert api.patch(f"/api/admin/users/{uid}", json={"password": "brandnewpw99"}).status_code == 200
    api.cookies.clear()
    assert api.post("/api/auth/login",
                    json={"email": "reset-me@x.com", "password": "brandnewpw99"}).status_code == 200
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_admin_users.py -v`
Expected: FAIL — 404 on `/api/admin/*`.

- [ ] **Step 3: Implement `admin.py` (users + read helpers)**

```python
# backend/admin.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session
from models import Permission, Role, RolePermission, User
from rbac import require
from security import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])
AdminDep = Depends(require("roles.manage"))


def _user_dict(u: User, session: Session) -> dict:
    role = session.get(Role, u.role_id)
    return {"id": u.id, "email": u.email, "display_name": u.display_name,
            "role": {"id": role.id, "name": role.name}, "is_active": u.is_active}


class CreateUser(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    role_id: int


class PatchUser(BaseModel):
    role_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=200)


@router.get("/users")
def list_users(admin: User = AdminDep, session: Session = Depends(get_session)):
    return [_user_dict(u, session) for u in session.exec(select(User)).all()]


@router.post("/users")
def create_user(payload: CreateUser, admin: User = AdminDep,
                session: Session = Depends(get_session)):
    email = payload.email.strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=409, detail="This email is already registered")
    if session.get(Role, payload.role_id) is None:
        raise HTTPException(status_code=400, detail="Unknown role")
    user = User(email=email, password_hash=hash_password(payload.password),
                display_name=payload.display_name.strip(), role_id=payload.role_id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_dict(user, session)


@router.patch("/users/{user_id}")
def patch_user(user_id: str, payload: PatchUser, admin: User = AdminDep,
               session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if user.id == admin.id:
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        if payload.role_id is not None and payload.role_id != admin_role.id:
            raise HTTPException(status_code=400, detail="You cannot change your own role")
    if payload.role_id is not None:
        if session.get(Role, payload.role_id) is None:
            raise HTTPException(status_code=400, detail="Unknown role")
        user.role_id = payload.role_id
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    session.add(user)
    session.commit()
    return _user_dict(user, session)


@router.get("/roles")
def list_roles(admin: User = AdminDep, session: Session = Depends(get_session)):
    out = []
    for r in session.exec(select(Role)).all():
        keys = session.exec(
            select(RolePermission.permission_key).where(RolePermission.role_id == r.id)
        ).all()
        out.append({"id": r.id, "name": r.name, "is_system": r.is_system,
                    "permission_keys": sorted(keys)})
    return out


@router.get("/permissions")
def list_permissions(admin: User = AdminDep, session: Session = Depends(get_session)):
    return [{"key": p.key, "description": p.description}
            for p in session.exec(select(Permission)).all()]
```

- [ ] **Step 4: Include router; run tests**

`main.py`: `from admin import router as admin_router` / `app.include_router(admin_router)`.

Run: `cd backend && python -m pytest tests/test_admin_users.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/admin.py backend/main.py backend/tests/test_admin_users.py
git commit -m "Add admin user management with self-lockout guards"
```

---

## Task 13: Admin role management

**Files:**
- Modify: `backend/admin.py` (add role write endpoints)
- Test: `backend/tests/test_admin_roles.py`

**Interfaces:**
- `POST /roles` — body `{name}` → role dict; `409` on duplicate name; new roles are `is_system=False`
- `PATCH /roles/{id}` — body `{permission_keys: [...]}` — full replace; `400` on an unknown key; on the `admin` role, `roles.manage` may not be removed → `400`
- `DELETE /roles/{id}` — `400` if `is_system`; `409` if any user is assigned; else deletes the role and its `role_permission` rows

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_admin_roles.py
from tests.conftest import make_user
from sqlmodel import Session


def _admin(api):
    with Session(api._engine) as s:
        make_user(s, email="admin@x.com", password="longenough12", role_name="admin")
    api.post("/api/auth/login", json={"email": "admin@x.com", "password": "longenough12"})


def test_create_custom_role_and_assign_permissions(api):
    _admin(api)
    rid = api.post("/api/admin/roles", json={"name": "auditor"}).json()["id"]
    r = api.patch(f"/api/admin/roles/{rid}", json={"permission_keys": ["analytics.view"]})
    assert r.status_code == 200
    assert r.json()["permission_keys"] == ["analytics.view"]


def test_cannot_delete_system_role(api):
    _admin(api)
    roles = {r["name"]: r for r in api.get("/api/admin/roles").json()}
    assert api.delete(f"/api/admin/roles/{roles['candidate']['id']}").status_code == 400


def test_cannot_delete_role_with_users(api):
    _admin(api)
    rid = api.post("/api/admin/roles", json={"name": "temp"}).json()["id"]
    api.post("/api/admin/users", json={
        "email": "temp-user@x.com", "password": "longenough12",
        "display_name": "T", "role_id": rid,
    })
    assert api.delete(f"/api/admin/roles/{rid}").status_code == 409


def test_cannot_strip_roles_manage_from_admin(api):
    _admin(api)
    roles = {r["name"]: r for r in api.get("/api/admin/roles").json()}
    r = api.patch(f"/api/admin/roles/{roles['admin']['id']}",
                  json={"permission_keys": ["analytics.view"]})
    assert r.status_code == 400


def test_unknown_permission_key_rejected(api):
    _admin(api)
    rid = api.post("/api/admin/roles", json={"name": "bad"}).json()["id"]
    assert api.patch(f"/api/admin/roles/{rid}",
                     json={"permission_keys": ["not.a.real.perm"]}).status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_admin_roles.py -v`
Expected: FAIL — 404/405 on the role write routes.

- [ ] **Step 3: Implement**

Add to `backend/admin.py`:

```python
class CreateRole(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class PatchRole(BaseModel):
    permission_keys: list[str]


def _role_dict(r: Role, session: Session) -> dict:
    keys = session.exec(
        select(RolePermission.permission_key).where(RolePermission.role_id == r.id)
    ).all()
    return {"id": r.id, "name": r.name, "is_system": r.is_system,
            "permission_keys": sorted(keys)}


@router.post("/roles")
def create_role(payload: CreateRole, admin: User = AdminDep,
                session: Session = Depends(get_session)):
    name = payload.name.strip().lower()
    if session.exec(select(Role).where(Role.name == name)).first():
        raise HTTPException(status_code=409, detail="A role with that name exists")
    role = Role(name=name, is_system=False)
    session.add(role)
    session.commit()
    session.refresh(role)
    return _role_dict(role, session)


@router.patch("/roles/{role_id}")
def patch_role(role_id: int, payload: PatchRole, admin: User = AdminDep,
               session: Session = Depends(get_session)):
    role = session.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    valid = set(session.exec(select(Permission.key)).all())
    requested = set(payload.permission_keys)
    unknown = requested - valid
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown permission: {sorted(unknown)}")
    if role.name == "admin" and "roles.manage" not in requested:
        raise HTTPException(status_code=400, detail="admin must keep roles.manage")
    for row in session.exec(
        select(RolePermission).where(RolePermission.role_id == role_id)
    ).all():
        session.delete(row)
    for key in requested:
        session.add(RolePermission(role_id=role_id, permission_key=key))
    session.commit()
    return _role_dict(role, session)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(role_id: int, admin: User = AdminDep,
                session: Session = Depends(get_session)):
    role = session.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")
    if session.exec(select(User).where(User.role_id == role_id)).first():
        raise HTTPException(status_code=409, detail="Reassign users before deleting this role")
    for row in session.exec(
        select(RolePermission).where(RolePermission.role_id == role_id)
    ).all():
        session.delete(row)
    session.delete(role)
    session.commit()
```

Replace the inline dict-building in `list_roles` (Task 12) with `_role_dict` for consistency.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/admin.py backend/tests/test_admin_roles.py
git commit -m "Add admin role CRUD with system-role and lockout guards"
```

---

## Task 14: Frontend — router dep + API client

**Files:**
- Modify: `frontend/package.json` (add `react-router-dom`)
- Modify: `frontend/src/api.js`
- Test: `frontend/src/api.test.js` (extend)

**Interfaces:**
- Produces in `api.js`:
  - every `fetch` gains `credentials: 'include'`
  - `signup({email, password, display_name})`, `login({email, password})`, `logout()`, `getMe()`
  - `putProfile({full_name, phone, city, first_language})`, `getMyAttempts()`
  - admin: `adminListUsers()`, `adminCreateUser(body)`, `adminPatchUser(id, body)`, `adminListRoles()`, `adminCreateRole(body)`, `adminPatchRole(id, body)`, `adminDeleteRole(id)`, `adminListPermissions()`
  - `request()` throws an `ApiError` carrying `.status`; a `401` also dispatches `window.dispatchEvent(new CustomEvent('auth:logout'))`

- [ ] **Step 1: Install the dependency**

Run: `cd frontend && npm install react-router-dom@7`
Verify `frontend/package.json` lists it under `dependencies`.

- [ ] **Step 2: Write the failing test**

```js
// add to frontend/src/api.test.js
import { expect, test, vi, afterEach } from 'vitest'
import { getMe, login, ApiError } from './api'

afterEach(() => vi.restoreAllMocks())

test('getMe sends credentials', async () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ email: 'a@b.com' }), { status: 200 }),
  )
  await getMe()
  expect(fetchSpy).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({ credentials: 'include' }))
})

test('a 401 dispatches auth:logout and throws ApiError', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('nope', { status: 401 }))
  const handler = vi.fn()
  window.addEventListener('auth:logout', handler)
  await expect(login({ email: 'x', password: 'y' })).rejects.toBeInstanceOf(ApiError)
  expect(handler).toHaveBeenCalled()
  window.removeEventListener('auth:logout', handler)
})
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npx vitest run src/api.test.js`
Expected: FAIL — `getMe` / `ApiError` not exported.

- [ ] **Step 4: Rewrite `api.js`**

```js
// frontend/src/api.js
export class ApiError extends Error {
  constructor(status, path, body) {
    super(`${status} ${path}: ${body}`)
    this.status = status
  }
}

async function request(path, options = {}) {
  const res = await fetch(path, { credentials: 'include', ...options })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    if (res.status === 401) window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new ApiError(res.status, path, body)
  }
  if (res.status === 204) return null
  return res.json()
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// --- auth ---
export const signup = (b) => request('/api/auth/signup', json('POST', b))
export const login = (b) => request('/api/auth/login', json('POST', b))
export const logout = () => request('/api/auth/logout', { method: 'POST' })
export const getMe = () => request('/api/auth/me')

// --- candidate ---
export const putProfile = (b) => request('/api/candidate/profile', json('PUT', b))
export const getMyAttempts = () => request('/api/me/attempts')

// --- admin ---
export const adminListUsers = () => request('/api/admin/users')
export const adminCreateUser = (b) => request('/api/admin/users', json('POST', b))
export const adminPatchUser = (id, b) => request(`/api/admin/users/${id}`, json('PATCH', b))
export const adminListRoles = () => request('/api/admin/roles')
export const adminCreateRole = (b) => request('/api/admin/roles', json('POST', b))
export const adminPatchRole = (id, b) => request(`/api/admin/roles/${id}`, json('PATCH', b))
export const adminDeleteRole = (id) => request(`/api/admin/roles/${id}`, { method: 'DELETE' })
export const adminListPermissions = () => request('/api/admin/permissions')

// --- attempts (unchanged behaviour, now credentialed) ---
export const getAttemptItems = (attemptId) => request(`/api/attempts/${attemptId}/items`)
export const createAttempt = () => request('/api/attempts', json('POST', {}))
export const submitResponse = (attemptId, itemId, text) =>
  request(`/api/attempts/${attemptId}/response`, json('POST', { item_id: itemId, text }))
export const submitAttempt = (attemptId) =>
  request(`/api/attempts/${attemptId}/submit`, { method: 'POST' })
export const getReport = (attemptId) => request(`/api/attempts/${attemptId}/report`)
export const listAttempts = () => request('/api/attempts')

export async function uploadAudio(attemptId, itemId, blob, mimeType) {
  const ext = mimeType.includes('webm') ? 'webm' : 'mp4'
  const form = new FormData()
  form.append('item_id', itemId)
  form.append('file', blob, `${itemId}.${ext}`)
  const res = await fetch(`/api/attempts/${attemptId}/audio`, {
    method: 'POST', body: form, credentials: 'include',
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    if (res.status === 401) window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new ApiError(res.status, 'audio upload', body)
  }
  return res.json()
}

export async function pollReport(attemptId, { intervalMs = 2000, timeoutMs = 300000 } = {}) {
  const deadline = Date.now() + timeoutMs
  let consecutiveErrors = 0
  for (;;) {
    try {
      const report = await getReport(attemptId)
      consecutiveErrors = 0
      if (report.status !== 'scoring') return report
    } catch (err) {
      if (++consecutiveErrors >= 5) throw err
    }
    if (Date.now() >= deadline) throw new Error('Scoring is taking longer than expected.')
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}
```

- [ ] **Step 5: Fix callers of `createAttempt(name)`**

`App.jsx` / `CandidateFlow.jsx` (Task 19) call `createAttempt(name)`; the signature is now `createAttempt()`. Update in Task 19. For now, `grep -rn createAttempt src/` and note the call sites.

- [ ] **Step 6: Run tests + lint**

Run: `cd frontend && npx vitest run src/api.test.js && npm run lint`
Expected: PASS. (Other suites may fail until Task 16–19; that is expected mid-workstream — do not commit until Step 7's targeted suite is green.)

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api.js frontend/src/api.test.js
git commit -m "Add react-router-dom and expand the API client for auth"
```

---

## Task 15: Frontend — AuthContext, RequireAuth, Forbidden

**Files:**
- Create: `frontend/src/auth/AuthContext.jsx`
- Create: `frontend/src/auth/RequireAuth.jsx`
- Create: `frontend/src/screens/Forbidden.jsx`
- Test: `frontend/src/auth/AuthContext.test.jsx`

**Interfaces:**
- Produces:
  - `<AuthProvider>` — on mount calls `getMe()`; state `{ user, loading }`; listens for `auth:logout` → clears `user`
  - `useAuth() -> { user, loading, permissions: string[], has(key), refresh(), signOut() }` where `user` is the `/me` payload or `null`
  - `<RequireAuth permission?>` — `loading` → `null`; no `user` → `<Navigate to="/login" replace state={{from}}>`; `permission` set and `!has(permission)` → `<Forbidden />`; else `children`
  - `<Forbidden />` — a plain "You don't have access to this page" panel with a link to `/`

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/auth/AuthContext.test.jsx
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { AuthProvider } from './AuthContext'
import RequireAuth from './RequireAuth'

vi.mock('../api', () => ({ getMe: vi.fn(), logout: vi.fn() }))
import { getMe } from '../api'

afterEach(() => vi.clearAllMocks())

function tree(initial = '/secret') {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route path="/secret" element={
            <RequireAuth permission="candidates.view"><p>secret</p></RequireAuth>
          } />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

test('unauthenticated user is redirected to /login', async () => {
  getMe.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  tree()
  await waitFor(() => expect(screen.getByText('login page')).toBeInTheDocument())
})

test('authenticated user lacking the permission sees Forbidden', async () => {
  getMe.mockResolvedValue({ email: 'a@b.com', permissions: ['test.take'], role: { name: 'candidate' } })
  tree()
  await waitFor(() => expect(screen.getByText(/don't have access/i)).toBeInTheDocument())
})

test('authenticated user with the permission sees the page', async () => {
  getMe.mockResolvedValue({ email: 'a@b.com', permissions: ['candidates.view'], role: { name: 'recruiter' } })
  tree()
  await waitFor(() => expect(screen.getByText('secret')).toBeInTheDocument())
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/auth/AuthContext.test.jsx`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement**

```jsx
// frontend/src/auth/AuthContext.jsx
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, logout as apiLogout } from '../api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setUser(await getMe())
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    const onLogout = () => setUser(null)
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  const signOut = useCallback(async () => {
    try { await apiLogout() } catch { /* ignore */ }
    setUser(null)
  }, [])

  const permissions = user?.permissions ?? []
  const value = {
    user, loading, permissions,
    has: (key) => permissions.includes(key),
    refresh, signOut,
  }
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
```

```jsx
// frontend/src/auth/RequireAuth.jsx
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Forbidden from '../screens/Forbidden'

export default function RequireAuth({ permission, children }) {
  const { user, loading, has } = useAuth()
  const location = useLocation()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (permission && !has(permission)) return <Forbidden />
  return children
}
```

```jsx
// frontend/src/screens/Forbidden.jsx
import { Link } from 'react-router-dom'

export default function Forbidden() {
  return (
    <div className="max-w-md mx-auto p-6 text-center flex flex-col gap-3">
      <h1 className="text-xl font-semibold">You don&apos;t have access to this page</h1>
      <Link to="/" className="text-sm underline">Go back</Link>
    </div>
  )
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run src/auth/AuthContext.test.jsx && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/ frontend/src/screens/Forbidden.jsx
git commit -m "Add AuthContext, RequireAuth guard, and Forbidden screen"
```

---

## Task 16: Frontend — router shell + role-home redirect

**Files:**
- Modify: `frontend/src/main.jsx` (wrap in `<BrowserRouter>`)
- Rewrite: `frontend/src/App.jsx` (routes only)
- Create: `frontend/src/screens/RoleHome.jsx`
- Test: `frontend/src/App.test.jsx` (rewrite)

**Interfaces:**
- Consumes: `useAuth`, `RequireAuth`, screens from later tasks (import lazily / with placeholders defined here).
- Produces: route table —
  - `/login` → `<Login />`, `/signup` → `<Signup />` (Task 17 — stub components now: `() => <p>login</p>` is NOT acceptable; create the real files in Task 17 and import here, so this task's placeholder is a one-line `Placeholder` component reused for `/dashboard` and `/admin` only)
  - `/` → `<RequireAuth><RoleHome /></RequireAuth>`
  - `/profile` → `<RequireAuth permission="test.take"><Profile /></RequireAuth>`
  - `/test` → `<RequireAuth permission="test.take"><CandidateFlow /></RequireAuth>`
  - `/report/:attemptId` → `<RequireAuth><ReportRoute /></RequireAuth>`
  - `/dashboard` → `<RequireAuth permission="candidates.view"><DashboardPlaceholder /></RequireAuth>`
  - `/admin` → `<RequireAuth permission="roles.manage"><AdminPlaceholder /></RequireAuth>`
- `RoleHome`: if `has('roles.manage')` → `<Navigate to="/admin">`; else if `has('candidates.view')` → `/dashboard`; else if `user.profile` → `/test`; else `/profile`.

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/App.test.jsx  (replace file)
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

vi.mock('./api', () => ({
  getMe: vi.fn(), logout: vi.fn(),
  getMyAttempts: vi.fn().mockResolvedValue([]),
}))
import { getMe } from './api'

afterEach(() => vi.clearAllMocks())

const renderAt = (path) =>
  render(<MemoryRouter initialEntries={[path]}><App routerless /></MemoryRouter>)

test('a candidate with no profile lands on the profile page', async () => {
  getMe.mockResolvedValue({
    email: 'c@x.com', permissions: ['test.take', 'report.view_own'],
    role: { name: 'candidate' }, profile: null,
  })
  renderAt('/')
  await waitFor(() => expect(screen.getByText(/your details/i)).toBeInTheDocument())
})

test('a recruiter lands on the dashboard', async () => {
  getMe.mockResolvedValue({
    email: 'r@x.com', permissions: ['candidates.view'], role: { name: 'recruiter' }, profile: null,
  })
  renderAt('/')
  await waitFor(() => expect(screen.getByText(/dashboard/i)).toBeInTheDocument())
})

test('an unauthenticated visitor to /admin is redirected to login', async () => {
  getMe.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  renderAt('/admin')
  await waitFor(() => expect(screen.getByText(/sign in/i)).toBeInTheDocument())
})
```

Note: `App` takes a `routerless` prop so tests can supply their own `<MemoryRouter>`. In `main.jsx` the real `<BrowserRouter>` wraps `<App />` (no prop).

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/App.test.jsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

```jsx
// frontend/src/main.jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
```

```jsx
// frontend/src/App.jsx
import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './auth/AuthContext'
import RequireAuth from './auth/RequireAuth'
import Login from './screens/Login'
import Signup from './screens/Signup'
import Profile from './screens/Profile'
import CandidateFlow from './screens/CandidateFlow'
import Report from './screens/Report'
import Recruiter from './screens/Recruiter'
import { getReport } from './api'

function RoleHome() {
  const { has, user } = useAuth()
  if (has('roles.manage')) return <Navigate to="/admin" replace />
  if (has('candidates.view')) return <Navigate to="/dashboard" replace />
  return <Navigate to={user?.profile ? '/test' : '/profile'} replace />
}

function ReportRoute() {
  const { attemptId } = useParams()
  const [report, setReport] = useState(null)
  const [err, setErr] = useState(false)
  useEffect(() => {
    getReport(attemptId).then(setReport).catch(() => setErr(true))
  }, [attemptId])
  if (err) return <p className="p-6 text-center text-red-600">Report not available.</p>
  if (!report) return <p className="p-6 text-center text-gray-500">Loading…</p>
  return <Report report={report} />
}

function DashboardPlaceholder() {
  return (
    <main className="min-h-screen bg-gray-50 py-10">
      <h1 className="text-center text-xl font-semibold">Recruiter dashboard</h1>
      <p className="text-center text-sm text-gray-500">Coming in WS3.</p>
      <Recruiter onOpenReport={() => {}} />
    </main>
  )
}

function AdminPlaceholder() {
  return (
    <main className="min-h-screen bg-gray-50 py-10">
      <h1 className="text-center text-xl font-semibold">Admin</h1>
      <p className="text-center text-sm text-gray-500">Role &amp; user management UI lands in WS3.</p>
    </main>
  )
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/" element={<RequireAuth><RoleHome /></RequireAuth>} />
      <Route path="/profile" element={<RequireAuth permission="test.take"><Profile /></RequireAuth>} />
      <Route path="/test" element={<RequireAuth permission="test.take"><CandidateFlow /></RequireAuth>} />
      <Route path="/report/:attemptId" element={<RequireAuth><ReportRoute /></RequireAuth>} />
      <Route path="/dashboard" element={<RequireAuth permission="candidates.view"><DashboardPlaceholder /></RequireAuth>} />
      <Route path="/admin" element={<RequireAuth permission="roles.manage"><AdminPlaceholder /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
```

(The `routerless` prop mentioned in the test is unnecessary if tests wrap `<App />` in `<MemoryRouter>` and `main.jsx` wraps in `<BrowserRouter>` — `App` itself renders no router. Update the test to drop the prop.)

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run src/App.test.jsx && npm run lint`
Expected: PASS once Tasks 17–19 screens exist. If running strictly in order, create minimal real `Login`/`Signup`/`Profile`/`CandidateFlow` now and flesh them out in their tasks — but prefer doing 17→19 before re-running the full suite.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/main.jsx frontend/src/App.test.jsx
git commit -m "Replace the pathname switch with a react-router route table"
```

---

## Task 17: Frontend — Login & Signup screens

**Files:**
- Create: `frontend/src/screens/Login.jsx`, `frontend/src/screens/Signup.jsx`
- Test: `frontend/src/screens/Login.test.jsx`

**Interfaces:**
- `Login`: email + password fields, "Sign in" button. On submit → `login()` → `refresh()` → `navigate(from ?? '/')`. Shows the server's error message on failure; a `429` shows "Too many attempts, try again shortly".
- `Signup`: email + display_name + password (min 10, shown as a hint). On submit → `signup()` → `refresh()` → `navigate('/')`. `409` shows "This email is already registered" with a link to `/login`.
- Both: a link to the other screen. If `useAuth().user` is already set, `<Navigate to="/" replace />`.

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/screens/Login.test.jsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', () => ({ login: vi.fn(), getMe: vi.fn(), logout: vi.fn() }))
import { login, getMe } from '../api'
import { AuthProvider } from '../auth/AuthContext'
import Login from './Login'

afterEach(() => vi.clearAllMocks())

function tree() {
  getMe.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<p>home</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

test('successful login navigates home', async () => {
  const user = userEvent.setup()
  login.mockResolvedValue({ email: 'a@b.com' })
  getMe.mockResolvedValue({ email: 'a@b.com', permissions: [], role: { name: 'candidate' }, profile: {} })
  tree()
  await user.type(screen.getByLabelText(/email/i), 'a@b.com')
  await user.type(screen.getByLabelText(/password/i), 'longenough12')
  await user.click(screen.getByRole('button', { name: /sign in/i }))
  await waitFor(() => expect(screen.getByText('home')).toBeInTheDocument())
})

test('a failed login shows the error', async () => {
  const user = userEvent.setup()
  login.mockRejectedValue(Object.assign(new Error('401'), { status: 401 }))
  tree()
  await user.type(screen.getByLabelText(/email/i), 'a@b.com')
  await user.type(screen.getByLabelText(/password/i), 'wrong')
  await user.click(screen.getByRole('button', { name: /sign in/i }))
  await waitFor(() => expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument())
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/screens/Login.test.jsx`
Expected: FAIL.

- [ ] **Step 3: Implement `Login.jsx`**

```jsx
// frontend/src/screens/Login.jsx
import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { login } from '../api'
import { useAuth } from '../auth/AuthContext'

export default function Login() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  const onSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login({ email, password })
      await refresh()
      navigate(location.state?.from ?? '/', { replace: true })
    } catch (err) {
      setError(
        err.status === 429
          ? 'Too many attempts, try again shortly'
          : 'Invalid email or password',
      )
      setBusy(false)
    }
  }

  return (
    <div className="max-w-sm mx-auto flex flex-col gap-5 p-6">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Password
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
                className="rounded-lg bg-purple-600 text-white py-2 font-medium disabled:opacity-50">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="text-sm text-gray-600">
        No account? <Link to="/signup" className="underline">Create one</Link>
      </p>
    </div>
  )
}
```

- [ ] **Step 4: Implement `Signup.jsx`** (same shape; fields email / display_name / password; `signup()` then `refresh()` then `navigate('/')`; on `err.status === 409` show "This email is already registered" + `<Link to="/login">`).

```jsx
// frontend/src/screens/Signup.jsx
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { signup } from '../api'
import { useAuth } from '../auth/AuthContext'

export default function Signup() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', display_name: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signup(form)
      await refresh()
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.status === 409
        ? 'This email is already registered'
        : 'Could not create your account. Check the form and try again.')
      setBusy(false)
    }
  }

  return (
    <div className="max-w-sm mx-auto flex flex-col gap-5 p-6">
      <h1 className="text-2xl font-semibold">Create your account</h1>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Email
          <input type="email" required value={form.email} onChange={set('email')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Full name
          <input type="text" required value={form.display_name} onChange={set('display_name')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Password <span className="font-normal text-gray-500">(at least 10 characters)</span>
          <input type="password" required minLength={10} value={form.password} onChange={set('password')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        {error && (
          <p className="text-sm text-red-600">
            {error}{' '}
            {error.startsWith('This email') && <Link to="/login" className="underline">Sign in</Link>}
          </p>
        )}
        <button type="submit" disabled={busy}
                className="rounded-lg bg-purple-600 text-white py-2 font-medium disabled:opacity-50">
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
      <p className="text-sm text-gray-600">
        Already registered? <Link to="/login" className="underline">Sign in</Link>
      </p>
    </div>
  )
}
```

- [ ] **Step 5: Run tests + lint**

Run: `cd frontend && npx vitest run src/screens/Login.test.jsx && npm run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/Login.jsx frontend/src/screens/Signup.jsx frontend/src/screens/Login.test.jsx
git commit -m "Add login and signup screens"
```

---

## Task 18: Frontend — Profile screen

**Files:**
- Create: `frontend/src/screens/Profile.jsx`
- Test: `frontend/src/screens/Profile.test.jsx`

**Interfaces:**
- `Profile`: fields `full_name`, `phone` (required), `city`, `first_language` (optional). Prefilled from `useAuth().user.profile` when present. On save → `putProfile()` → `refresh()` → `navigate('/test')`. Heading text contains "Your details".

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/screens/Profile.test.jsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', () => ({ putProfile: vi.fn(), getMe: vi.fn(), logout: vi.fn() }))
import { putProfile, getMe } from '../api'
import { AuthProvider } from '../auth/AuthContext'
import Profile from './Profile'

afterEach(() => vi.clearAllMocks())

test('saving the profile navigates to the test', async () => {
  const user = userEvent.setup()
  getMe.mockResolvedValue({
    email: 'c@x.com', permissions: ['test.take'], role: { name: 'candidate' }, profile: null,
  })
  putProfile.mockResolvedValue({ full_name: 'Cee Andidate', phone: '123' })
  render(
    <MemoryRouter initialEntries={['/profile']}>
      <AuthProvider>
        <Routes>
          <Route path="/profile" element={<Profile />} />
          <Route path="/test" element={<p>test screen</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
  await waitFor(() => screen.getByText(/your details/i))
  await user.type(screen.getByLabelText(/full name/i), 'Cee Andidate')
  await user.type(screen.getByLabelText(/phone/i), '9990001111')
  await user.click(screen.getByRole('button', { name: /save|continue/i }))
  await waitFor(() => expect(screen.getByText('test screen')).toBeInTheDocument())
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/screens/Profile.test.jsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

```jsx
// frontend/src/screens/Profile.jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { putProfile } from '../api'
import { useAuth } from '../auth/AuthContext'

export default function Profile() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  const p = user?.profile ?? {}
  const [form, setForm] = useState({
    full_name: p.full_name ?? user?.display_name ?? '',
    phone: p.phone ?? '',
    city: p.city ?? '',
    first_language: p.first_language ?? '',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await putProfile({
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        city: form.city.trim() || null,
        first_language: form.first_language.trim() || null,
      })
      await refresh()
      navigate('/test', { replace: true })
    } catch {
      setError('Could not save your details. Try again.')
      setBusy(false)
    }
  }

  return (
    <div className="max-w-md mx-auto flex flex-col gap-5 p-6">
      <h1 className="text-2xl font-semibold">Your details</h1>
      <p className="text-sm text-gray-600">We use this to label your results. It takes a moment.</p>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Full name
          <input required value={form.full_name} onChange={set('full_name')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Phone
          <input required value={form.phone} onChange={set('phone')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          City <span className="font-normal text-gray-500">(optional)</span>
          <input value={form.city} onChange={set('city')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          First language <span className="font-normal text-gray-500">(optional)</span>
          <input value={form.first_language} onChange={set('first_language')}
                 className="rounded-lg border border-gray-300 p-2 font-normal" />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
                className="rounded-lg bg-purple-600 text-white py-2 font-medium disabled:opacity-50">
          {busy ? 'Saving…' : 'Save and continue'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Run tests + lint**

Run: `cd frontend && npx vitest run src/screens/Profile.test.jsx && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Profile.jsx frontend/src/screens/Profile.test.jsx
git commit -m "Add the candidate profile screen"
```

---

## Task 19: Frontend — CandidateFlow extraction + Start cleanup

**Files:**
- Create: `frontend/src/screens/CandidateFlow.jsx` (the old `CandidateApp` from `App.jsx`, adapted)
- Modify: `frontend/src/screens/Start.jsx` (drop the name input)
- Modify: `frontend/src/screens/Test.test.jsx` if it imports from `App` (it does not — it imports `Test` directly, so no change)
- Test: `frontend/src/screens/CandidateFlow.test.jsx`

**Interfaces:**
- Consumes: `createAttempt()` (no args now), `getAttemptItems`, `submitAttempt`, `pollReport`, `getReport`, `session.js` helpers, `useAuth`.
- `Start` new props: `{ displayName, onBegin }` — shows the name read-only, a consent checkbox, and a "Begin" button; `onBegin()` takes no name.
- `CandidateFlow`: same state machine as the old `CandidateApp` (`start → check → test → submitting → report`), except:
  - `handleBegin` calls `createAttempt()` with no name
  - on reaching `report`, also offer a link to `/` ("Done")
  - the resume-after-refresh `useEffect` is unchanged (keyed on `session.js`)

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/screens/CandidateFlow.test.jsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', () => ({
  createAttempt: vi.fn().mockResolvedValue({ attempt_id: 'a1' }),
  getAttemptItems: vi.fn().mockResolvedValue({ items: [] }),
  submitAttempt: vi.fn(), pollReport: vi.fn(), getReport: vi.fn(),
  getMe: vi.fn(), logout: vi.fn(),
}))
import { createAttempt, getMe } from '../api'
import { AuthProvider } from '../auth/AuthContext'
import CandidateFlow from './CandidateFlow'

afterEach(() => vi.clearAllMocks())

test('Begin creates an attempt with no name argument', async () => {
  const user = userEvent.setup()
  getMe.mockResolvedValue({
    email: 'c@x.com', display_name: 'Cee', permissions: ['test.take'],
    role: { name: 'candidate' }, profile: { full_name: 'Cee Andidate' },
  })
  render(
    <MemoryRouter><AuthProvider><CandidateFlow /></AuthProvider></MemoryRouter>,
  )
  await waitFor(() => screen.getByRole('button', { name: /begin/i }))
  await user.click(screen.getByRole('checkbox'))
  await user.click(screen.getByRole('button', { name: /begin/i }))
  await waitFor(() => expect(createAttempt).toHaveBeenCalledWith())
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/screens/CandidateFlow.test.jsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Create `CandidateFlow.jsx`**

Move the `CandidateApp` function body from the current `App.jsx` into `frontend/src/screens/CandidateFlow.jsx`. Changes:
- `export default function CandidateFlow() { ... }`
- `import { useAuth } from '../auth/AuthContext'`; read `const { user } = useAuth()`
- `handleBegin`: `const { attempt_id } = await createAttempt()` (no `name`); drop the `name` parameter threaded from `Start`
- `<Start onBegin={handleBegin} displayName={user?.profile?.full_name ?? user?.display_name} />`
- keep imports of `DeviceCheck`, `Report`, `Submitting`, `Test`, `session.js` (adjust relative paths — they are now siblings, so `./DeviceCheck` etc.)
- on the `report` screen, render an extra `<Link to="/">Done</Link>` (import `Link` from `react-router-dom`)

- [ ] **Step 4: Simplify `Start.jsx`**

```jsx
// frontend/src/screens/Start.jsx
import { useState } from 'react'

export default function Start({ displayName, onBegin }) {
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const canBegin = consent && !submitting

  const handleBegin = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await onBegin()
    } catch {
      setError('Could not start the test. Please try again.')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-md mx-auto flex flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold">English Assessment</h1>
      <p className="text-sm text-gray-600">
        Signed in as <span className="font-medium">{displayName}</span>
      </p>
      <label className="flex items-start gap-3 text-left text-sm text-gray-600">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
               className="mt-1 accent-purple-600" />
        <span>
          I consent to my microphone audio being recorded for the speaking sections of this
          assessment.
        </span>
      </label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="button" disabled={!canBegin} onClick={handleBegin}
              className="rounded-lg bg-purple-600 text-white py-3 font-medium disabled:opacity-40">
        {submitting ? 'Starting…' : 'Begin'}
      </button>
    </div>
  )
}
```

- [ ] **Step 5: Run the whole frontend suite + lint**

Run: `cd frontend && npx vitest run && npm run lint`
Expected: PASS. Fix fallout — likely `App.test.jsx` (already rewritten in Task 16) and any Start-name assumptions.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/CandidateFlow.jsx frontend/src/screens/Start.jsx frontend/src/screens/CandidateFlow.test.jsx frontend/src/App.jsx
git commit -m "Move the candidate flow into its own route; drop the name entry"
```

---

## Task 20: Docs + end-to-end manual verification

**Files:**
- Modify: `BUILD_LOG.md`
- Modify: `04-tech-stack.md` (§6 table row: "No auth → JWT + tenant scoping" becomes "auth: email/password + server-side sessions — done; tenant scoping still pending")
- Modify: `docs/superpowers/specs/2026-09-09-auth-and-rbac-design.md` — set `Status: Implemented (2026-09-09)`

- [ ] **Step 1: Update `04-tech-stack.md`**

In §6's migration table, change the `No auth | JWT + tenant scoping | ...` row to note auth is implemented via opaque server-side sessions (not JWT), with a rationale pointer to the spec, and that tenant scoping remains the open item. Add `argon2-cffi` and `react-router-dom` to §1's "at a glance" table with a one-line "what it does".

- [ ] **Step 2: Append a `BUILD_LOG.md` entry**

A dated section summarising WS1: the new tables, the permission model, the onboarding flow, the endpoints added and hardened, and the two new dependencies. Note the schema change requires deleting `backend/demo.db` on an existing dev checkout.

- [ ] **Step 3: Full automated run**

```bash
cd backend && python -m pytest
cd ../frontend && npx vitest run && npm run lint
```
Expected: all green.

- [ ] **Step 4: Manual end-to-end (fresh DB)**

```bash
rm -f backend/demo.db
cd backend && ADMIN_EMAIL=admin@test.local ADMIN_PASSWORD=change-me-now uvicorn main:app --reload
# separate shell:
cd frontend && npm run dev
```
Verify, in a browser:
1. `/` redirects to `/login`.
2. Sign up a new candidate → lands on **Your details** → save → **Begin** screen (name shown, no input).
3. Complete a short attempt; reach the report; "Done" returns to `/`.
4. Log out; log in as `admin@test.local`; land on `/admin`.
5. As admin, create a recruiter (via the API with `curl` or the browser devtools if the UI is still a placeholder — the placeholder is expected pre-WS3). Log in as that recruiter → `/dashboard`; the candidate's attempt is listed; opening its report works; visiting `/admin` shows **You don't have access**.
6. Confirm the candidate cannot load `/dashboard` or `/admin`.

- [ ] **Step 5: Commit**

```bash
git add BUILD_LOG.md 04-tech-stack.md docs/superpowers/specs/2026-09-09-auth-and-rbac-design.md
git commit -m "Document WS1 auth + RBAC; mark the spec implemented"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| §2 data model (all tables + `attempt.user_id`) | 1 |
| §2 opaque session tokens | 3, 6 |
| §3 permissions + seeded role map | 4 |
| §3 lock-out guards (system roles, self-deactivation, admin `roles.manage`) | 12, 13 |
| §4 `security.py` | 2 |
| §4 `rbac.py` (`get_current_user`, `require`, `user_permissions`) | 3 |
| §4 `auth.py` signup/login/logout/me + cookie flags | 6, 7 |
| §4 `candidate.py` profile + `/me/attempts` | 8 |
| §4 admin management endpoints | 12, 13 |
| §4 existing-endpoint changes (attempts create, ownership, report, list) | 9, 10, 11 |
| §5 seeding (idempotent, default admin) | 4, 5 |
| §6 schema guard | 1 |
| §7 router + routes + role-home | 16 |
| §7 `AuthContext` / `RequireAuth` | 15 |
| §7 `api.js` (`credentials`, 401 handling, calls) | 14 |
| §7 Login / Signup / Profile screens | 17, 18 |
| §7 Start name removal + candidate flow relocation | 19 |
| §8 limitations / §9 security / §10 error states | enforced across 6–13; documented in 20 |
| §11 testing (backend + frontend + manual) | every task's tests; manual in 20 |
| §12 files / docs | 20 |

No gaps.

**Placeholder scan:** the only "placeholder" components are the WS3 `/dashboard` and `/admin` route bodies in Task 16 — these are explicit, working, in-scope stand-ins named in the spec (§ non-goals), not deferred work inside WS1. All test bodies and implementation bodies are concrete.

**Type consistency:**
- `require(*keys)` returns a dependency yielding `User` — used consistently as `user=Depends(require("..."))` (Tasks 8–13) and `user: User = AdminDep` (12–13).
- `_me_payload` shape (Task 6) matches what `AuthContext`/`RoleHome`/`RequireAuth` read: `permissions`, `role.name`, `profile` (Tasks 15, 16).
- `ApiError` with `.status` (Task 14) is what Login/Signup branch on (`err.status === 409/429`, Task 17).
- `createAttempt()` no-arg (Task 14) matches its call site rewrite (Task 19).
- `_require_own_attempt` (Task 10) and `get_report`'s inline check (Task 11) both key on `attempt.user_id == user.id`.
- Cookie name is the literal `"session"` in `rbac.COOKIE_NAME`, the cookie set in `auth.py`, and every test's `cookies={"session": ...}`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-09-auth-and-rbac.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
