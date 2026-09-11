"""FastAPI app bootstrap.

Creates the app, mounts static/audio directories, registers all routers, and
runs startup tasks (DB init, question-bank load, auth seeding, model warm-up).
No route handlers live here - those are in the ``routes`` package.
"""

import logging
import os
import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from bank import load_bank
from db import init_db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent

app = FastAPI(title="English Assessment Demo API")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

from routes import admin, analytics, attempts, auth, candidate, recruiting  # noqa: E402

app.include_router(auth.router)
app.include_router(attempts.router)
app.include_router(candidate.router)
app.include_router(admin.router)
app.include_router(recruiting.router)
app.include_router(analytics.router)


_LOCAL_DEV_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


def _allowed_origins(request: Request) -> set[str]:
    """Return same-origin plus explicitly configured browser origins.

    Vite's development proxy is included by default; production deployments
    should set APP_ALLOWED_ORIGINS to the public UI origin(s), comma-separated.
    """
    configured = {
        value.strip().rstrip("/")
        for value in os.getenv("APP_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    }
    return {str(request.base_url).rstrip("/"), *_LOCAL_DEV_ORIGINS, *configured}


def _is_production() -> bool:
    return os.getenv("APP_ENV", "development").lower() == "production"


@app.middleware("http")
async def browser_security(request: Request, call_next):
    """Apply baseline browser defenses and reject cross-site mutations.

    Cookie-authenticated APIs must not accept a browser's state-changing
    request merely because the browser attached a session cookie. Production
    requires an explicit approved Origin; development keeps CLI workflows
    possible while still rejecting known cross-site requests.
    """
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site")
        approved = origin and origin.rstrip("/") in _allowed_origins(request)
        if (
            fetch_site == "cross-site"
            or (_is_production() and not approved)
            or (origin and not approved)
        ):
            return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked"})

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "microphone=(self)")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


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


def _ollama_reachable() -> bool:
    import ollama

    try:
        ollama.Client(timeout=2).list()
        return True
    except Exception:  # noqa: BLE001 - any failure means "not reachable"
        return False


def _whisper_loaded() -> bool:
    from scoring import asr

    return asr._model is not None


@app.get("/api/health")
def health() -> dict:
    """Engine availability for the UI's pre-scoring check. Booleans only:
    no versions, hosts or paths."""
    return {"ollama": _ollama_reachable(), "whisper": _whisper_loaded()}


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    load_bank()

    from db import engine
    from scoring.pipeline import fail_interrupted_attempts
    from seed_auth import ensure_default_admin, seed_auth
    from security import clear_throttles

    clear_throttles()
    # seed_auth commits several times internally, so give it a fresh session
    # that shares no pending work with request handlers.
    with Session(engine) as session:
        seed_auth(session)
        ensure_default_admin(session)
        fail_interrupted_attempts(session)

    # Fire-and-forget: don't block server startup on model warm-up.
    threading.Thread(target=_warm_up_in_background, daemon=True).start()
