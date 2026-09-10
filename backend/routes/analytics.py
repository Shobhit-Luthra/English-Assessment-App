from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from db import get_session
from models import Attempt, CandidateProfile, Score
from rbac import require

router = APIRouter()


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _percentile(values: list[int], pct: float) -> float | None:
    """Linear-interpolation percentile (same as PERCENTILE.INC in spreadsheets).
    ``pct`` is the percentage of candidates at or below the returned value."""
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * (pct / 100.0)
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    frac = index - lo
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * frac, 2)


def _speaking_band(scores: list[Score], dims: dict) -> float | None:
    """Composite speaking band (preferred) or fluency average for pre-fix data."""
    if dims.get("speaking") is not None:
        return float(dims["speaking"])
    values = [s.band for s in scores if s.dimension.startswith("speaking_fluency_")]
    return _average(values)


def _writing_band(scores: list[Score], dims: dict) -> float | None:
    """Composite writing band (preferred) or tone for pre-fix data."""
    if dims.get("writing") is not None:
        return float(dims["writing"])
    if dims.get("writing_tone") is not None:
        return float(dims["writing_tone"])
    return None


@router.get("/api/analytics/overview")
def analytics_overview(session: Session = Depends(get_session),
                       user=Depends(require("analytics.view"))):
    """Aggregate metrics across everyone who has taken the assessment.

    Each candidate is counted once, using their latest completed attempt, so
    retakes do not inflate headcounts or section averages."""
    attempts = session.exec(select(Attempt)).all()
    score_rows = session.exec(select(Score)).all()

    scores_by_attempt: dict[str, list[Score]] = defaultdict(list)
    for s in score_rows:
        scores_by_attempt[s.attempt_id].append(s)

    completed = sorted(
        (a for a in attempts if a.status == "done"),
        key=lambda a: a.created_at,
    )
    latest_by_user: dict = {}
    for a in completed:
        if a.user_id not in latest_by_user or a.created_at > latest_by_user[a.user_id].created_at:
            latest_by_user[a.user_id] = a

    section_totals: dict[str, list[float]] = defaultdict(list)
    cirs: list[int] = []
    for a in latest_by_user.values():
        rows = scores_by_attempt.get(a.id, [])
        dims = {s.dimension: s.band for s in rows}
        grammar = dims.get("grammar")
        listening = dims.get("listening")
        picks = {
            "understanding": _average([v for v in (grammar, listening) if v is not None]),
            "grammar": grammar,
            "listening": listening,
            "speaking": _speaking_band(rows, dims),
            "writing": _writing_band(rows, dims),
            "task_fulfilment": dims.get("situational_task_fulfilment"),
        }
        for key, value in picks.items():
            if value is not None:
                section_totals[key].append(value)
        if dims.get("cir") is not None:
            cirs.append(dims["cir"])

    recommended = sum(1 for c in cirs if c >= 5)
    borderline = sum(1 for c in cirs if c == 4)
    not_recommended = sum(1 for c in cirs if c < 4)

    decisions = {"hired": 0, "rejected": 0, "pending": 0}
    tested_ids = {a.user_id for a in latest_by_user.values()}
    if tested_ids:
        profiles = session.exec(
            select(CandidateProfile).where(CandidateProfile.user_id.in_(tested_ids))
        ).all()
    else:
        profiles = []
    for p in profiles:
        decisions[p.decision] = decisions.get(p.decision, 0) + 1
    decisions["total"] = len(profiles)

    return {
        "total_candidates_tested": len(tested_ids),
        "total_attempts": len(attempts),
        "completed_attempts": len(completed),
        "in_progress_attempts": sum(1 for a in attempts if a.status not in ("done", "error")),
        "cir": {
            "average": _average(cirs),
            "recommended": recommended,
            "borderline": borderline,
            "not_recommended": not_recommended,
            "pass_rate": round(recommended / len(cirs), 4) if cirs else None,
        },
        "benchmarks": {
            "median": _percentile(cirs, 50),
            "top_25": _percentile(cirs, 75),
        },
        "sections": {
            "understanding": _average(section_totals.get("understanding", [])),
            "grammar": _average(section_totals.get("grammar", [])),
            "listening": _average(section_totals.get("listening", [])),
            "speaking": _average(section_totals.get("speaking", [])),
            "writing": _average(section_totals.get("writing", [])),
            "task_fulfilment": _average(section_totals.get("task_fulfilment", [])),
        },
        "decisions": decisions,
    }