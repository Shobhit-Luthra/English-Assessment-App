# backend/auth.py
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from db import get_session
from models import CandidateProfile, Role, SessionToken, User
from rbac import COOKIE_NAME, CurrentUser, user_permissions
from security import (
    ThrottledError, check_login_allowed, hash_password, new_session_token,
    record_login_failure, reset_login_failures, verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SESSION_TTL = timedelta(days=14)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# A real argon2 hash to verify against when the email is unknown, so a
# failed login costs the same whether or not the account exists (no
# user-enumeration timing oracle).
_DUMMY_HASH = hash_password("timing-equalisation-placeholder")


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


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response,
          session: Session = Depends(get_session)):
    client_ip = request.client.host if request.client else "?"
    # Two throttle scopes: one per (email, IP) so a single account under
    # attack locks quickly, and one per IP so credential spraying across
    # many emails from one host is also capped.
    throttle_keys = [f"{payload.email}|{client_ip}", f"ip|{client_ip}"]
    for key in throttle_keys:
        try:
            check_login_allowed(key)
        except ThrottledError as exc:
            raise HTTPException(
                status_code=429, detail="Too many attempts. Try again later.",
                headers={"Retry-After": str(exc.retry_after)},
            )

    user = session.exec(select(User).where(User.email == payload.email)).first()
    # Always run one argon2 verification so timing does not reveal whether
    # the email exists.
    stored_hash = user.password_hash if user is not None else _DUMMY_HASH
    password_ok = verify_password(payload.password, stored_hash)
    if user is None or not user.is_active or not password_ok:
        for key in throttle_keys:
            record_login_failure(key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    for key in throttle_keys:
        reset_login_failures(key)
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
