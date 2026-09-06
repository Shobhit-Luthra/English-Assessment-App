import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session, init_db
from models import Attempt, Response

BASE_DIR = Path(__file__).parent
ITEMS_PATH = BASE_DIR / "items.json"

app = FastAPI(title="English Assessment Demo API")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

SessionDep = Annotated[Session, Depends(get_session)]

_ITEM_IDS: set[str] = set()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))["items"]
    _ITEM_IDS.update(item["id"] for item in items)


class CreateAttemptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class CreateAttemptResponse(BaseModel):
    attempt_id: str


@app.get("/api/items")
def get_items():
    return json.loads(ITEMS_PATH.read_text(encoding="utf-8"))


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
    _get_attempt_or_404(session, attempt_id)
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
