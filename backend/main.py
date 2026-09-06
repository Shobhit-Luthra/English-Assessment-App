import json
import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session, init_db
from models import Attempt, Response, Score
from scoring.objective import score_section
from scoring.pipeline import run_scoring_pipeline

BASE_DIR = Path(__file__).parent
ITEMS_PATH = BASE_DIR / "items.json"
AUDIO_DIR = BASE_DIR / "audio"

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

SessionDep = Annotated[Session, Depends(get_session)]

_ITEM_IDS: set[str] = set()
_ITEMS_PUBLIC: dict = {}
_ITEMS_BY_SECTION: dict[str, list[dict]] = {}
_ITEMS_BY_ID: dict[str, dict] = {}

# Fields never sent to the client while a test is in progress - "answer" is
# the MCQ answer key; leaking it lets a candidate read it from the network
# tab and always score 100%.
_ANSWER_KEY_FIELDS = {"answer"}


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))["items"]
    _ITEM_IDS.update(item["id"] for item in items)
    _ITEMS_PUBLIC["items"] = [
        {k: v for k, v in item.items() if k not in _ANSWER_KEY_FIELDS} for item in items
    ]
    for item in items:
        _ITEMS_BY_SECTION.setdefault(item["section"], []).append(item)
        _ITEMS_BY_ID[item["id"]] = item


class CreateAttemptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class CreateAttemptResponse(BaseModel):
    attempt_id: str


@app.get("/api/items")
def get_items():
    return _ITEMS_PUBLIC


@app.post("/api/attempts", response_model=CreateAttemptResponse)
def create_attempt(payload: CreateAttemptRequest, session: SessionDep):
    attempt = Attempt(name=payload.name.strip())
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return CreateAttemptResponse(attempt_id=attempt.id)


class SubmitResponseRequest(BaseModel):
    item_id: str
    text: str = Field(max_length=5000)


def _get_attempt_or_404(session: Session, attempt_id: str) -> Attempt:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


@app.post("/api/attempts/{attempt_id}/response")
def submit_response(attempt_id: str, payload: SubmitResponseRequest, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt is no longer accepting responses")
    if payload.item_id not in _ITEM_IDS:
        raise HTTPException(status_code=400, detail="Unknown item_id")

    existing = session.exec(
        select(Response).where(
            Response.attempt_id == attempt_id,
            Response.item_id == payload.item_id,
        )
    ).first()

    if existing:
        existing.text = payload.text
        session.add(existing)
    else:
        session.add(Response(attempt_id=attempt_id, item_id=payload.item_id, text=payload.text))

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
    if item_id not in _ITEM_IDS:
        raise HTTPException(status_code=400, detail="Unknown item_id")

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

    responses = session.exec(select(Response).where(Response.attempt_id == attempt_id)).all()
    responses_by_item = {r.item_id: r.text for r in responses if r.text is not None}

    for dimension in ("grammar", "listening"):
        section_items = _ITEMS_BY_SECTION.get(dimension, [])
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

    background_tasks.add_task(run_scoring_pipeline, attempt_id, _ITEMS_BY_ID, _ITEMS_BY_SECTION)
    return {"ok": True}


@app.get("/api/attempts/{attempt_id}/report")
def get_report(attempt_id: str, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
    scores = session.exec(select(Score).where(Score.attempt_id == attempt_id)).all()
    responses = session.exec(select(Response).where(Response.attempt_id == attempt_id)).all()
    audio_by_item = {r.item_id: r.audio_path for r in responses if r.audio_path}

    def _audio_url(evidence: dict) -> str | None:
        item_id = evidence.get("item_id")
        path = audio_by_item.get(item_id)
        return f"/{path.replace(chr(92), '/')}" if path else None

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
