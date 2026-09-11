import json
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent


@pytest.fixture
def bank_dict():
    return json.loads((BACKEND_DIR / "bank.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _restore_bank():
    yield
    from bank import load_bank
    try:
        load_bank()
    except Exception:
        pass


from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402


@pytest.fixture
def auth_engine(monkeypatch):
    import db
    import models  # noqa: F401  -- register every table on SQLModel.metadata
    import seed_auth

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    with Session(engine) as s:
        seed_auth.seed_auth(s)
    return engine


@pytest.fixture
def api(auth_engine, monkeypatch):
    import db
    import main
    from bank import load_bank

    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.local")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")

    def _get_session():
        with Session(auth_engine) as s:
            yield s

    main.app.dependency_overrides[db.get_session] = _get_session
    load_bank()
    with TestClient(main.app) as c:
        c._engine = auth_engine
        yield c
    main.app.dependency_overrides.clear()


def _select_role(name):
    from models import Role

    return select(Role).where(Role.name == name)


def make_user(session, *, email, password, role_name, with_profile=False):
    from models import CandidateProfile, User
    from security import hash_password

    role = session.exec(_select_role(role_name)).first()
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        display_name=email.split("@")[0],
        role_id=role.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    if with_profile:
        session.add(
            CandidateProfile(user_id=user.id, full_name="Test User", phone="0000000000")
        )
        session.commit()
    return user


def login(api, email, password):
    r = api.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def authenticate_candidate(client, email="fixture-cand@x.com"):
    """Seed the auth tables on this client's engine and log in as a candidate
    with a completed profile. Legacy attempt/response/scoring tests use their
    own local ``client`` fixture; since attempt creation is now gated behind
    ``test.take`` + a profile, they call this once to obtain a valid session
    cookie."""
    import seed_auth

    with Session(client._engine) as s:
        seed_auth.seed_auth(s)
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "longenough12", "display_name": "Fixture Cand",
    })
    assert r.status_code == 200, r.text
    client.put("/api/candidate/profile", json={"full_name": "Fixture Cand", "phone": "1"})
    return client
