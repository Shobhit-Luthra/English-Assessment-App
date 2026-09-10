"""FastAPI app bootstrap.

Creates the app, mounts static/audio directories, registers all routers, and
runs startup tasks (DB init, question-bank load, auth seeding, model warm-up).
No route handlers live here - those are in the ``routes`` package.
"""

import logging
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from bank import AUDIO_DIR, load_bank
from db import init_db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent

app = FastAPI(title="English Assessment Demo API")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

from routes import admin, analytics, attempts, auth, candidate, recruiting  # noqa: E402

app.include_router(auth.router)
app.include_router(attempts.router)
app.include_router(candidate.router)
app.include_router(admin.router)
app.include_router(recruiting.router)
app.include_router(analytics.router)


def _warm_up_in_background() -> None:
    from scoring.asr import warm_up as warm_up_asr
    from scoring.judge import warm_up as warm_up_judge

    try:
        warm_up_asr()
    except Exception:  # noqa: BLE001 - startup warm-up is best-effort
        logger.exception("Whisper warm-up failed; first real score will pay the model download")
    try:
        warm_up_judge()
    except Exception:  # noqa: BLE001 - startup warm-up is best-effort
        logger.exception("Ollama warm-up call failed; first real score will pay the load cost")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    load_bank()

    from db import engine
    from seed_auth import ensure_default_admin, seed_auth
    from security import clear_throttles

    clear_throttles()
    # seed_auth commits several times internally, so give it a fresh session
    # that shares no pending work with request handlers.
    with Session(engine) as session:
        seed_auth(session)
        ensure_default_admin(session)

    # Fire-and-forget: don't block server startup on model warm-up.
    threading.Thread(target=_warm_up_in_background, daemon=True).start()