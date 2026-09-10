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
