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
