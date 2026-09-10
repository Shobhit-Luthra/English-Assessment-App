"""Attempt lifecycle endpoints: create, answer, record audio, submit, report.

These endpoints cover a candidate's attempt through to the recruiter-facing
attempt listing. The heavy lifting (audio transcription + LLM scoring) runs
in a background task started at submit time.
"""

import logging
import os
import random
import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from bank import SELECTION_COUNTS, get_all_items, get_bank_by_section, get_item
from db import get_session
from models import Attempt, CandidateProfile, Response, Score
from rbac import CurrentUser, require, user_permissions
from scoring.objective import score_section
from scoring.pipeline import run_scoring_pipeline
from selection import SelectionError, canonical_letter, option_permutations, select_items

logger = logging.getLogger(__name__)

router = APIRouter(tags=["attempts"])

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "audio"

# Fields never sent to the client while a test is in progress - "answer" is
# the MCQ answer key; leaking it lets a candidate read it from the network
# tab and always score 100%.
_ANSWER_KEY_FIELDS = {"answer"}

# Only these are accepted from MediaRecorder in the two browsers we target
# (Chrome -> webm/opus, Safari -> mp4/aac). Anything else is rejected before
# it touches disk.
_ALLOWED_AUDIO_TYPES = {
    "audio/webm": "webm",
    "audio/webm;codecs=opus": "webm",
    "audio/mp4": "mp4",
}
_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB - generous for a <=45s clip

SessionDep = Annotated[Session, Depends(get_session)]

AUDIO_DIR.mkdir(parents=True, exist_ok=True)


class CreateAttemptRequest(BaseModel):
    item_ids: list[str] | None = None  # seed-only; ignored unless env flag set


class CreateAttemptResponse(BaseModel):
    attempt_id: str


def _resolve_selection(payload: CreateAttemptRequest, attempt_id: str) -> list[str]:
    if payload.item_ids is not None:
        if os.getenv("ASSESSMENT_ALLOW_FIXED_SELECTION") != "1":
            raise HTTPException(status_code=400, detail="item_ids not accepted")
        unknown = [i for i in payload.item_ids if get_item(i) is None]
        if unknown or not payload.item_ids:
            raise HTTPException(status_code=400, detail="Unknown item id in fixed selection")
        return list(payload.item_ids)
    try:
        rng = random.Random(attempt_id)
        return select_items(get_bank_by_section(), SELECTION_COUNTS, rng)
    except SelectionError:
        logger.exception("Item selection failed")
        raise HTTPException(status_code=500, detail="Question bank misconfigured")


@router.post("/api/attempts", response_model=CreateAttemptResponse)
def create_attempt(payload: CreateAttemptRequest, session: SessionDep,
                   user=Depends(require("test.take"))):
    profile = session.get(CandidateProfile, user.id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete your profile first")
    attempt = Attempt(name=profile.full_name, user_id=user.id)
    attempt.item_ids = _resolve_selection(payload, attempt.id)
    selected_items = [get_item(i) for i in attempt.item_ids]
    attempt.option_order = option_permutations(selected_items, random.Random(attempt.id + "opts"))
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return CreateAttemptResponse(attempt_id=attempt.id)


def _public_item(item: dict, permutation: list[int] | None) -> dict:
    public = {k: v for k, v in item.items() if k not in _ANSWER_KEY_FIELDS}
    if permutation is not None and "options" in public:
        public["options"] = [item["options"][idx] for idx in permutation]
    return public


def _get_attempt_or_404(session: Session, attempt_id: str) -> Attempt:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


def _require_own_attempt(session: Session, attempt_id: str, user) -> Attempt:
    """Resolve an attempt that must belong to ``user``. Unknown and
    not-owned collapse to the same 404 so ownership is not an oracle."""
    attempt = session.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


def _lookup_item(item_id: str) -> dict:
    """Resolve an id stored on an attempt against the loaded bank. The bank
    can change under a live attempt (an item pulled from bank.json between
    attempt creation and scoring); surface that as a 409 rather than a 500."""
    item = get_item(item_id)
    if item is None:
        logger.warning("attempt references item '%s' that is no longer in the bank", item_id)
        raise HTTPException(
            status_code=409, detail="This attempt's item set is no longer valid"
        )
    return item


@router.get("/api/attempts/{attempt_id}/items")
def get_attempt_items(attempt_id: str, session: SessionDep,
                      user=Depends(require("test.take"))):
    attempt = _require_own_attempt(session, attempt_id, user)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt is no longer accepting responses")
    responses = session.exec(select(Response).where(Response.attempt_id == attempt_id)).all()
    text_by_item = {r.item_id: r.text for r in responses if r.text is not None}

    items = []
    for item_id in attempt.item_ids:
        item = _lookup_item(item_id)
        public = _public_item(item, attempt.option_order.get(item_id))
        # The candidate's own saved answer (their essay text), so a resume
        # after refresh restores the textarea. Not sent for mcq (stored value
        # is the canonical letter, not the shuffled display position) and not
        # for speaking (those are audio).
        if item["type"] == "text" and item_id in text_by_item:
            public["response_text"] = text_by_item[item_id]
        items.append(public)
    return {"items": items}


class SubmitResponseRequest(BaseModel):
    item_id: str
    text: str = Field(max_length=5000)


@router.post("/api/attempts/{attempt_id}/response")
def submit_response(attempt_id: str, payload: SubmitResponseRequest, session: SessionDep,
                    user=Depends(require("test.take"))):
    attempt = _require_own_attempt(session, attempt_id, user)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt is no longer accepting responses")
    if payload.item_id not in attempt.item_ids:
        raise HTTPException(status_code=400, detail="Item not in this attempt")

    text = payload.text
    item = _lookup_item(payload.item_id)
    if item["type"] == "mcq":
        permutation = attempt.option_order.get(payload.item_id)
        given = text.strip().lower()
        if permutation is not None and given in ("a", "b", "c", "d", "e", "f")[: len(permutation)]:
            text = canonical_letter(given, permutation)

    existing = session.exec(
        select(Response).where(
            Response.attempt_id == attempt_id,
            Response.item_id == payload.item_id,
        )
    ).first()

    if existing:
        existing.text = text
        session.add(existing)
    else:
        session.add(Response(attempt_id=attempt_id, item_id=payload.item_id, text=text))

    session.commit()
    return {"ok": True}


def _probe_duration_ms(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=10,
    )
    return int(float(result.stdout.strip()) * 1000)


@router.post("/api/attempts/{attempt_id}/audio")
async def upload_audio(
    attempt_id: str,
    session: SessionDep,
    item_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    user=Depends(require("test.take")),
):
    attempt = _require_own_attempt(session, attempt_id, user)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt is no longer accepting responses")
    if item_id not in attempt.item_ids:
        raise HTTPException(status_code=400, detail="Item not in this attempt")

    ext = _ALLOWED_AUDIO_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(status_code=400, detail="Unsupported audio type")

    data = await file.read(_MAX_AUDIO_BYTES + 1)
    if len(data) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    attempt_dir = AUDIO_DIR / attempt_id
    attempt_dir.mkdir(parents=True, exist_ok=True)
    # item_id is checked against the server's own item whitelist above, so
    # this path is never attacker-controlled.
    dest = attempt_dir / f"{item_id}.{ext}"
    dest.write_bytes(data)

    try:
        duration_ms = _probe_duration_ms(dest)
    except (subprocess.SubprocessError, ValueError, OSError):
        duration_ms = None

    existing = session.exec(
        select(Response).where(Response.attempt_id == attempt_id, Response.item_id == item_id)
    ).first()
    if existing:
        existing.audio_path = str(dest.relative_to(BASE_DIR))
        existing.duration_ms = duration_ms
        session.add(existing)
    else:
        session.add(
            Response(
                attempt_id=attempt_id,
                item_id=item_id,
                audio_path=str(dest.relative_to(BASE_DIR)),
                duration_ms=duration_ms,
            )
        )
    session.commit()
    return {"ok": True, "duration_ms": duration_ms}


@router.post("/api/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, background_tasks: BackgroundTasks, session: SessionDep,
                   user=Depends(require("test.take"))):
    attempt = _require_own_attempt(session, attempt_id, user)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt already submitted")

    attempt_items_by_section: dict[str, list[dict]] = {}
    for item_id in attempt.item_ids:
        item = _lookup_item(item_id)
        attempt_items_by_section.setdefault(item["section"], []).append(item)

    responses = session.exec(select(Response).where(Response.attempt_id == attempt_id)).all()
    responses_by_item = {r.item_id: r.text for r in responses if r.text is not None}

    for dimension in ("grammar", "listening"):
        section_items = attempt_items_by_section.get(dimension, [])
        result = score_section(section_items, responses_by_item)
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension=dimension,
                band=result["band"],
                evidence=result["evidence"],
            )
        )

    # Objective sections score synchronously (instant); audio transcription
    # and the LLM judge run in the background - they take ~30s and the
    # client polls /report until status leaves "scoring".
    attempt.status = "scoring"
    session.add(attempt)
    session.commit()

    background_tasks.add_task(
        run_scoring_pipeline, attempt_id, get_all_items(), attempt_items_by_section
    )
    return {"ok": True}


@router.get("/api/attempts/{attempt_id}/report")
def get_report(attempt_id: str, session: SessionDep, user: CurrentUser):
    attempt = _get_attempt_or_404(session, attempt_id)
    perms = user_permissions(user, session)
    is_owner = attempt.user_id == user.id
    if not ("candidates.view" in perms or (is_owner and "report.view_own" in perms)):
        raise HTTPException(status_code=403, detail="Not allowed")
    scores = session.exec(select(Score).where(Score.attempt_id == attempt_id)).all()
    responses = session.exec(select(Response).where(Response.attempt_id == attempt_id)).all()
    audio_by_item = {r.item_id: r.audio_path for r in responses if r.audio_path}
    text_by_item = {r.item_id: r.text for r in responses if r.text}

    def _audio_url(evidence: dict) -> str | None:
        item_id = evidence.get("item_id")
        path = audio_by_item.get(item_id)
        return f"/{path.replace(chr(92), '/')}" if path else None

    def _response_text(evidence: dict) -> str | None:
        return text_by_item.get(evidence.get("item_id"))

    def _item_meta(evidence: dict) -> dict:
        """Attach the item's type and the read-aloud reference text so the
        report can show what was expected next to what was said. The reference
        text is the passage the candidate already saw on screen during the
        test, so it is safe to surface."""
        item = get_item(evidence.get("item_id", ""))
        if item is None:
            return {}
        return {"item_type": item.get("type"), "reference_text": item.get("reference_text")}

    return {
        "attempt_id": attempt.id,
        "name": attempt.name,
        "status": attempt.status,
        "error": attempt.error,
        "scores": [
            {
                "dimension": s.dimension,
                "band": s.band,
                "evidence": {**s.evidence, **_item_meta(s.evidence)},
                "audio_url": _audio_url(s.evidence),
                "response_text": _response_text(s.evidence),
            }
            for s in scores
        ],
    }


@router.get("/api/attempts")
def list_attempts(session: SessionDep, user=Depends(require("candidates.view"))):
    attempts = session.exec(select(Attempt)).all()
    return [
        {"attempt_id": a.id, "name": a.name, "status": a.status,
         "created_at": a.created_at, "user_id": a.user_id}
        for a in attempts
    ]