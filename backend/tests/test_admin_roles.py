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
