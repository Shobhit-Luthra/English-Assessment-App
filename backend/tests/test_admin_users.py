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
