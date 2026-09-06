import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session, init_db
from models import Attempt, Response, Score
from scoring.objective import score_section

BASE_DIR = Path(__file__).parent
ITEMS_PATH = BASE_DIR / "items.json"

app = FastAPI(title="English Assessment Demo API")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

SessionDep = Annotated[Session, Depends(get_session)]

_ITEM_IDS: set[str] = set()
_ITEMS_PUBLIC: dict = {}
_ITEMS_BY_SECTION: dict[str, list[dict]] = {}

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


@app.post("/api/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, session: SessionDep):
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

    attempt.status = "done"
    session.add(attempt)
    session.commit()
    return {"ok": True}


@app.get("/api/attempts/{attempt_id}/report")
def get_report(attempt_id: str, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
    scores = session.exec(select(Score).where(Score.attempt_id == attempt_id)).all()
    return {
        "attempt_id": attempt.id,
        "name": attempt.name,
        "status": attempt.status,
        "scores": [
            {"dimension": s.dimension, "band": s.band, "evidence": s.evidence} for s in scores
        ],
    }


@app.get("/api/attempts")
def list_attempts(session: SessionDep):
    attempts = session.exec(select(Attempt)).all()
    return [
        {"attempt_id": a.id, "name": a.name, "status": a.status, "created_at": a.created_at}
        for a in attempts
    ]
