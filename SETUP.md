# Setup

How to get the English Assessment System running locally, from a clean
machine to a populated recruiter dashboard. Everything runs on your machine;
there are no external services or API keys.

Two processes: a FastAPI backend (`backend/`, port 8000) and a Vite/React
frontend (`frontend/`, port 5173). Speaking and writing answers are scored by
faster-whisper (speech-to-text) and a local Ollama model (the "judge").

## 1. Install prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.11+ | Backend API and scoring pipeline |
| Node.js | 20+ | Frontend build and dev server |
| ffmpeg | any recent | Decodes browser audio (webm/opus, mp4) for Whisper; `ffprobe` measures clip length |
| Ollama | 0.9+ | Runs the judge model locally |

Windows: `winget install ffmpeg` and the Ollama installer from ollama.com.
macOS: `brew install ffmpeg ollama`. Ubuntu/WSL: `sudo apt install ffmpeg`
plus the Ollama install script.

Then pull the judge model and confirm everything answers:

```bash
ollama pull qwen3:8b        # ~5 GB download, ~6 GB RAM/VRAM while loaded
ffmpeg -version
ffprobe -version
ollama list                 # must show qwen3:8b; the daemon must be running
```

The first time an attempt is scored, faster-whisper downloads its `small`
model (~460 MB) too. The backend warms both models in the background at
startup so the first candidate does not wait for downloads.

## 2. Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

On startup the backend:

- creates `backend/demo.db` (SQLite) and the schema if missing;
- seeds the permission catalogue and the three system roles (`admin`,
  `recruiter`, `candidate`);
- creates the bootstrap accounts below (and resets their passwords);
- marks any attempt left in `scoring` by a previous crash as `error` so it
  can be re-scored;
- warms Whisper and the Ollama model on a background thread.

Check it: `curl http://localhost:8000/api/health` →
`{"ollama": true, "whisper": true}` once warm-up has finished.

### Bootstrap accounts

| Account | Email | Password | Created |
|---|---|---|---|
| Admin | `ADMIN_EMAIL` (default `admin@example.com`) | `ADMIN_PASSWORD` (default `admin12345`) | always |
| Demo recruiter | `recruiter@example.com` | `recruiter12345` | always |

Both passwords are re-applied on **every** startup, so a password changed
through the Admin screen reverts at the next restart. This is a local-demo
convenience; set `ADMIN_PASSWORD` for anything that is not a throwaway run,
and treat the demo recruiter as such.

Candidates create their own accounts through **Sign up** on the landing page.

### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `ADMIN_EMAIL` | `admin@example.com` | Bootstrap admin email |
| `ADMIN_PASSWORD` | `admin12345` | Bootstrap admin password (re-applied at every startup) |
| `OLLAMA_JUDGE_MODEL` | `qwen3:8b` | Ollama model used as the speaking/writing judge. Thinking is disabled for the call; on an Ollama server too old to accept that option the call is retried without it |
| `ASSESSMENT_ALLOW_FIXED_SELECTION` | unset | Set to `1` only when running `seed_attempts.py`; lets a client pin the item set instead of drawing it randomly |

### Schema changes

`init_db()` never `ALTER`s existing tables. If you pull a change that adds a
column, the backend refuses to start and tells you to delete
`backend/demo.db`. The dev database holds only seeded and throwaway data,
so delete it and restart. (A backup is left as
`demo.db.schema-mismatch-backup`; both are git-ignored.)

## 3. Run the frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The Vite dev server proxies `/api`, `/static` and `/audio` to
`http://localhost:8000`, so the backend must be running. There is no frontend
environment file.

## 4. Put data on the dashboards

A fresh database has no completed attempts, so the recruiter directory and
analytics are empty until at least one test reaches `done`. Either take a
test yourself (sign up as a candidate → fill in your details → Start test)
or seed four candidates across the score bands through the real pipeline:

```bash
# terminal 1 — from backend/, venv active, Ollama running
ASSESSMENT_ALLOW_FIXED_SELECTION=1 uvicorn main:app --port 8000
# PowerShell: $env:ASSESSMENT_ALLOW_FIXED_SELECTION='1'; uvicorn main:app --port 8000

# terminal 2 — from backend/
python seed_attempts.py
```

Expected output is four lines ending `status=done` with a CIR spread of
roughly 1 → 6, taking one to two minutes per candidate on CPU. Then log in as
the demo recruiter to see `/dashboard` and `/analytics`.

## 5. How scoring works (what to expect)

1. **Submit** scores grammar and listening instantly from the answer key and
   puts the attempt in `scoring`.
2. A background task transcribes each recording with Whisper, computes the
   read-aloud fluency band deterministically, unloads Whisper, then makes one
   Ollama call that scores the situational speaking task and the email on
   the full rubric (grammar, vocabulary, task fulfilment, fluency / tone).
3. Every dimension is always written: a task the candidate skipped scores
   band 1 and is shown as "Not attempted". The overall CIR band is
   `0.35·speaking fluency + 0.25·listening + 0.20·writing tone + 0.20·task fulfilment`.
4. If Whisper or Ollama fails, the attempt ends in `error` with a short
   reason (`judge_unavailable`, `judge_invalid_output`, `asr_failed`,
   `interrupted`). Grammar, listening and the read-aloud band are kept. Any
   recruiter or admin can press **Re-score** on the report page once the
   engine is back; candidates see "Scoring failed" on My results.

The candidate's "Scoring your responses" screen checks `/api/health` and says
so up front if Ollama is down.

## 6. Authentication model

- Session cookie `session`: HttpOnly, SameSite=Lax, 14-day TTL, `Secure`
  only over HTTPS.
- Authorization is permission-based (`test.take`, `report.view_own`,
  `candidates.view`, `candidates.decide`, `analytics.view`, `roles.manage`,
  `settings.manage`), enforced on the backend; `admin` always holds the full
  catalogue.
- Login throttle: 10 failures per `(email, IP)` and per IP in a rolling
  15-minute window, in-process (resets on restart, and skipped for
  loopback addresses).

## 7. Running the checks

```bash
# backend — from backend/ with the venv active (no Ollama/ffmpeg needed)
python -m pytest -q

# frontend — from frontend/
npm run test          # vitest
npm run lint          # oxlint (six pre-existing react warnings)
npm run build         # production build into frontend/dist
```

Expected on a clean checkout of `main`: backend 117 passed, frontend 58
passed, build clean.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Backend refuses to start: "attempt table is missing … columns" | Old `demo.db`; delete it and restart |
| `/api/health` shows `"ollama": false` | Ollama daemon not running or not reachable on `localhost:11434`; start it and reload |
| Attempt ends in `judge_unavailable` | Ollama was down or `qwen3:8b` not pulled; fix, then Re-score from the report |
| Attempt ends in `asr_failed` | ffmpeg not on PATH, or the recording could not be decoded |
| Attempt ends in `interrupted` | Backend restarted mid-scoring; Re-score |
| First scoring takes minutes | One-time Whisper (~460 MB) and Ollama model loads |
| Dashboards empty | No attempt has reached `done` yet — see §4 |
