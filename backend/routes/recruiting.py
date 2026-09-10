"""Recruiter/analyst endpoints: candidate directory and hire/reject decisions.

Any user with ``candidates.view`` (recruiter or admin) can list all candidates
with their attempt history and section bands. Only users with
``candidates.decide`` can change a candidate's Hire / Reject decision, and the
decider is recorded so admins can see who made each decision.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models import Attempt, CandidateProfile, Score, User
from rbac import require

router = APIRouter(prefix="/api/candidates", tags=["recruiting"])

# One row per candidate in the directory so the recruiter dashboard can be
# populated by a single request.


def _mean_band(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def _attempt_summary(attempt: Attempt, scores: list[Score]) -> dict:
    bands = {s.dimension: s.band for s in scores}
    speaking = [s.band for s in scores if s.dimension.startswith("speaking_fluency_")]
    writing_tones = [s.band for s in scores if s.dimension == "writing_tone"]
    grammar = bands.get("grammar")
    listening = bands.get("listening")
    # Fall back to the single-dimension evidence for attempts scored before the
    # composite section bands were introduced, so old report rows still resolve.
    speaking_band = bands.get("speaking")
    if speaking_band is None:
        speaking_band = _mean_band(speaking)
    writing_band = bands.get("writing")
    if writing_band is None:
        writing_band = _mean_band(writing_tones)
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "created_at": attempt.created_at.isoformat(),
        "cir": bands.get("cir"),
        "sections": {
            "understanding": _mean_band([v for v in (grammar, listening) if v is not None]),
            "speaking": speaking_band,
            "writing": writing_band,
            "grammar": grammar,
            "listening": listening,
        },
    }


def _pct_stronger(cir: int | None, peers: list[int]) -> float | None:
    """Share of peers the candidate beats by latest overall band. ``None``
    when there is no score or nobody to compare against."""
    if cir is None or not peers:
        return None
    if len(peers) == 1:
        return 50.0
    lower = sum(1 for c in peers if c < cir)
    return round((lower / (len(peers) - 1)) * 100)


def _candidate_dict(
    profile: CandidateProfile, user: User, attempts: list[dict], session: Session
) -> dict:
    decider = None
    if profile.decided_by:
        decider_user = session.get(User, profile.decided_by)
        decider = decider_user.display_name if decider_user else None
    return {
        "user_id": user.id,
        "full_name": profile.full_name,
        "email": user.email,
        "phone": profile.phone,
        "city": profile.city,
        "first_language": profile.first_language,
        "decision": profile.decision,
        "decided_by": decider,
        "decided_at": profile.decided_at.isoformat() if profile.decided_at else None,
        "attempts": attempts,
    }


@router.get("")
def list_candidates(
    user=Depends(require("candidates.view")), session: Session = Depends(get_session)
):
    profiles = session.exec(
        select(CandidateProfile).order_by(CandidateProfile.updated_at.desc())
    ).all()
    result = []
    for profile in profiles:
        user_row = session.get(User, profile.user_id)
        if user_row is None:
            continue
        attempts = session.exec(
            select(Attempt)
            .where(Attempt.user_id == user_row.id)
            .order_by(Attempt.created_at.desc())
        ).all()
        summaries = []
        for attempt in attempts:
            scores = session.exec(select(Score).where(Score.attempt_id == attempt.id)).all()
            summaries.append(_attempt_summary(attempt, scores))
        result.append(_candidate_dict(profile, user_row, summaries, session))

    latest_cirs: list[int] = []
    for row in result:
        latest = next((a for a in row["attempts"] if a["status"] == "done"), None)
        latest_cirs.append(latest["cir"] if latest else None)
    peers = [c for c in latest_cirs if c is not None]
    for row, latest_cir in zip(result, latest_cirs):
        row["pct_stronger"] = _pct_stronger(latest_cir, peers)
    return result


class DecisionRequest(BaseModel):
    decision: Literal["hired", "rejected", "pending"]


@router.post("/{user_id}/decision")
def set_decision(
    user_id: str,
    payload: DecisionRequest,
    user=Depends(require("candidates.decide")),
    session: Session = Depends(get_session),
):
    profile = session.get(CandidateProfile, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    profile.decision = payload.decision
    profile.decided_by = None if payload.decision == "pending" else user.id
    profile.decided_at = (
        None if payload.decision == "pending" else datetime.now(timezone.utc)
    )
    session.add(profile)
    session.commit()
    return {"user_id": user_id, "decision": profile.decision}