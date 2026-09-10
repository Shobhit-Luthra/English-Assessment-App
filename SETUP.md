# Setup

Local development setup for the English Assessment System. Two processes:
a FastAPI backend (`backend/`) and a Vite/React frontend (`frontend/`).

## 1. Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Python | 3.11+ | Backend API and scoring pipeline |
| Node.js | 20+ | Frontend build and dev server |
| ffmpeg | any recent | Decoding browser audio (webm/opus, mp4) for Whisper |
| Ollama | 0.6+ | Runs the local judge model for speaking/writing scores |

The speaking/writing scoring pipeline also downloads a faster-whisper
`small` model (~460 MB) on first use and pulls the Ollama model
`qwen2.5:3b-instruct`. Objective sections (grammar, listening MCQ) work
without either.

Pre-flight check that ffmpeg, Ollama and Whisper are reachable:

```bash
ffmpeg -version
ollama list          # daemon must be running on localhost:11434
ollama pull qwen2.5:3b-instruct
```

## 2. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

On startup the backend:

- creates `backend/demo.db` (SQLite) and the schema if missing;
- seeds the permission catalogue and the system roles (`admin`,
  `recruiter`, `candidate`);
- creates a default admin user if no admin exists yet;
- warms the Whisper and Ollama models in a background thread.

### Schema changes

`init_db()` never `ALTER`s existing tables. If you pull a change that adds
columns, the backend fails loudly at startup with a message telling you to
delete `backend/demo.db` and restart. The dev database holds only seeded
and throwaway data, so this is safe.

### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `ADMIN_EMAIL` | `admin@example.com` | Email for the bootstrapped admin user |
| `ADMIN_PASSWORD` | *(random, logged once)* | Password for the bootstrapped admin. If unset, a random password is generated and written to the log with a warning — set this explicitly for anything but a throwaway run |
| `ASSESSMENT_ALLOW_FIXED_SELECTION` | unset | Set to `1` only for seed scripts that pin a fixed item selection; leave unset in normal runs |

The default admin is created only when the `user` table has no admin. To
re-bootstrap, delete `backend/demo.db` and restart.

## 3. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/api`, `/static` and `/audio` to
`http://localhost:8000`, so the backend must be running. There is no
frontend environment file — all requests are same-origin through the
proxy.

## 4. Authentication model

- Session cookie named `session`, HttpOnly, SameSite=Lax, 14-day TTL,
  `Secure` only when served over HTTPS.
- Login throttle is in-process (resets on restart): 10 failed attempts
  per `(email, IP)` and per `IP` within a rolling 15-minute window.
- Roles and permissions are seeded on every startup (idempotent). `admin`
  always receives the full permission catalogue, including permissions
  added in later releases.

## 5. Running the checks

```bash
# Backend — from backend/ with the venv active
python -m pytest -q

# Frontend — from frontend/
npm run test          # vitest
npm run lint          # oxlint
npm run build         # production build into frontend/dist
```

Expected on a clean checkout of `main`: backend 74 passed, frontend 31
passed, lint clean (two pre-existing `react` fast-refresh warnings in
`src/auth/AuthContext.jsx`).

## 6. Seed data (optional)

- `backend/seed_auth.py` — roles, permissions, default admin. Runs
  automatically at startup; no need to invoke directly.
- `backend/seed_attempts.py` — seeded candidate attempts across score
  bands for demoing the recruiter view. Needs a running backend and
  Ollama.
- `backend/seed_audio.ps1` — regenerates the reference speaking clips.
