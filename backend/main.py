import json
import logging
import os
import random
import subprocess
import threading
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session, init_db
from models import Attempt, Response, Score
from scoring.asr import warm_up as warm_up_asr
from scoring.judge import warm_up
from scoring.objective import score_section
from scoring.pipeline import run_scoring_pipeline
from selection import SelectionError, canonical_letter, option_permutations, select_items

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
BANK_PATH = BASE_DIR / "bank.json"
AUDIO_DIR = BASE_DIR / "audio"

SELECTION_COUNTS: dict[str, int] = {"grammar": 5, "listening": 2, "writing": 1, "speaking": 2}

# Only these are accepted from MediaRecorder in the two browsers we target
# (Chrome -> webm/opus, Safari -> mp4/aac). Anything else is rejected before
# it touches disk.
_ALLOWED_AUDIO_TYPES = {
    "audio/webm": "webm",
    "audio/webm;codecs=opus": "webm",
    "audio/mp4": "mp4",
}
_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB - generous for a <=45s clip

AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="English Assessment Demo API")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

from auth import router as auth_router  # noqa: E402

app.include_router(auth_router)

SessionDep = Annotated[Session, Depends(get_session)]

# Fields never sent to the client while a test is in progress - "answer" is
# the MCQ answer key; leaking it lets a candidate read it from the network
# tab and always score 100%.
_ANSWER_KEY_FIELDS = {"answer"}

_ITEMS_BY_ID: dict[str, dict] = {}
_BANK_BY_SECTION: dict[str, list[dict]] = {}


def _load_bank() -> None:
    items = json.loads(BANK_PATH.read_text(encoding="utf-8"))["items"]
    _ITEMS_BY_ID.clear()
    _BANK_BY_SECTION.clear()
    for item in items:
        _ITEMS_BY_ID[item["id"]] = item
        _BANK_BY_SECTION.setdefault(item["section"], []).append(item)
    for section, count in SELECTION_COUNTS.items():
        pool = _BANK_BY_SECTION.get(section, [])
        if len(pool) < count:
            raise RuntimeError(
                f"bank.json section '{section}' has {len(pool)} items, needs at least {count}"
            )
    speaking_types = {i["type"] for i in _BANK_BY_SECTION.get("speaking", [])}
    if "read_aloud" not in speaking_types or "situational" not in speaking_types:
        raise RuntimeError(
            "bank.json speaking section must contain at least one 'read_aloud' and one 'situational' item"
        )


def _warm_up_judge_in_background() -> None:
    try:
        warm_up_asr()
    except Exception:  # noqa: BLE001 - startup warm-up is best-effort
        logger.exception("Whisper warm-up failed; first real score will pay the model download")
    try:
        warm_up()
    except Exception:  # noqa: BLE001 - startup warm-up is best-effort
        logger.exception("Ollama warm-up call failed; first real score will pay the load cost")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _load_bank()
    from db import engine
    from seed_auth import ensure_default_admin, seed_auth

    # seed_auth commits several times internally, so give it a fresh session
    # that shares no pending work with request handlers.
    with Session(engine) as session:
        seed_auth(session)
        ensure_default_admin(session)
    # Fire-and-forget: don't block server startup on Ollama being ready.
    threading.Thread(target=_warm_up_judge_in_background, daemon=True).start()


class CreateAttemptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    item_ids: list[str] | None = None  # seed-only; ignored unless env flag set


class CreateAttemptResponse(BaseModel):
    attempt_id: str


def _resolve_selection(payload: CreateAttemptRequest, attempt_id: str) -> list[str]:
    if payload.item_ids is not None:
        if os.getenv("ASSESSMENT_ALLOW_FIXED_SELECTION") != "1":
            raise HTTPException(status_code=400, detail="item_ids not accepted")
        unknown = [i for i in payload.item_ids if i not in _ITEMS_BY_ID]
        if unknown or not payload.item_ids:
            raise HTTPException(status_code=400, detail="Unknown item id in fixed selection")
        return list(payload.item_ids)
    try:
        rng = random.Random(attempt_id)
        return select_items(_BANK_BY_SECTION, SELECTION_COUNTS, rng)
    except SelectionError:
        logger.exception("Item selection failed")
        raise HTTPException(status_code=500, detail="Question bank misconfigured")


@app.post("/api/attempts", response_model=CreateAttemptResponse)
def create_attempt(payload: CreateAttemptRequest, session: SessionDep):
    attempt = Attempt(name=payload.name.strip())
    attempt.item_ids = _resolve_selection(payload, attempt.id)
    selected_items = [_ITEMS_BY_ID[i] for i in attempt.item_ids]
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


def _lookup_item(item_id: str) -> dict:
    """Resolve an id stored on an attempt against the loaded bank. The bank
    can change under a live attempt (an item pulled from bank.json between
    attempt creation and scoring); surface that as a 409 rather than a 500."""
    item = _ITEMS_BY_ID.get(item_id)
    if item is None:
        logger.warning("attempt references item '%s' that is no longer in the bank", item_id)
        raise HTTPException(
            status_code=409, detail="This attempt's item set is no longer valid"
        )
    return item


@app.get("/api/attempts/{attempt_id}/items")
def get_attempt_items(attempt_id: str, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
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


@app.post("/api/attempts/{attempt_id}/response")
def submit_response(attempt_id: str, payload: SubmitResponseRequest, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
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


@app.post("/api/attempts/{attempt_id}/audio")
async def upload_audio(
    attempt_id: str,
    session: SessionDep,
    item_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    attempt = _get_attempt_or_404(session, attempt_id)
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


@app.post("/api/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, background_tasks: BackgroundTasks, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
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
        run_scoring_pipeline, attempt_id, _ITEMS_BY_ID, attempt_items_by_section
    )
    return {"ok": True}


@app.get("/api/attempts/{attempt_id}/report")
def get_report(attempt_id: str, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
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

    return {
        "attempt_id": attempt.id,
        "name": attempt.name,
        "status": attempt.status,
        "error": attempt.error,
        "scores": [
            {
                "dimension": s.dimension,
                "band": s.band,
                "evidence": s.evidence,
                "audio_url": _audio_url(s.evidence),
                "response_text": _response_text(s.evidence),
            }
            for s in scores
        ],
    }


@app.get("/api/attempts")
def list_attempts(session: SessionDep):
    attempts = session.exec(select(Attempt)).all()
    return [
        {"attempt_id": a.id, "name": a.name, "status": a.status, "created_at": a.created_at}
        for a in attempts
    ]
