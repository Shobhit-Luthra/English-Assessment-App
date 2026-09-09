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
