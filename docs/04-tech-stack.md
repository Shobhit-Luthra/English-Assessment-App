# Tech Stack

Two columns matter: **what it is** (plain words) and **why this one over the obvious alternative**. Version pins are minimums, not exact.

---

## 1. At a glance

| Layer | Choice | What it actually does |
|---|---|---|
| Build tool | **Vite** | Dev server + bundler. Starts in ~300 ms instead of ~15 s |
| UI | **React 18** | Component rendering and state |
| Styling | **Tailwind CSS** | Utility classes in markup instead of a separate CSS file |
| Charts | **Recharts** | The radar chart on the report page |
| Audio capture | **MediaRecorder API** | Browser built-in. Records mic to a compressed blob |
| API framework | **FastAPI** | HTTP endpoints, request validation, background jobs |
| Server | **Uvicorn** | The ASGI process that actually runs FastAPI |
| ORM / models | **SQLModel** | Python classes ↔ database tables, one definition each |
| Database | **SQLite** | The entire DB is one file on disk |
| Validation | **Pydantic v2** | Type-checked data shapes; also generates the LLM output schema |
| Speech-to-text | **faster-whisper** | Audio → text + per-word timestamps |
| Audio decoding | **ffmpeg** | Converts browser webm/opus into what Whisper can read |
| LLM runtime | **Ollama** | Runs a language model locally, exposes it over localhost |
| Judge model | **qwen3:8b** | Scores language quality against the rubric (thinking disabled for the call) |
| Fluency scoring | **Plain Python** | Arithmetic over word timestamps. No library, no model |

**Total external services: zero. Total runtime cost: ₹0.**

---

## 2. Install

### System prerequisites
```bash
# ffmpeg — required, faster-whisper cannot decode webm without it
# macOS
brew install ffmpeg
# Ubuntu / WSL
sudo apt update && sudo apt install ffmpeg
# Windows: download from ffmpeg.org and add the bin/ folder to PATH

ffmpeg -version    # must print, or nothing downstream works
```

### Ollama
```bash
# install from ollama.com for your OS, then:
ollama pull qwen3:8b
ollama list                       # confirm it's there
```

### Python
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install "fastapi>=0.110" "uvicorn[standard]>=0.27" \
            "sqlmodel>=0.0.14" "pydantic>=2.6" \
            "faster-whisper>=1.0" "ollama>=0.3" \
            "python-multipart>=0.0.9"
```

`python-multipart` is easy to forget and only fails at the moment you first upload audio, with a confusing error. Install it now.

### Frontend
```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install recharts
npm install -D tailwindcss @tailwindcss/vite
```

---

## 3. Why these, and not the obvious alternatives

### FastAPI over Express/Node
Your ASR and feature extraction are Python. Splitting languages means an extra service, an extra process to babysit, and serialisation between them — for a three-day build with one concurrent user, that's pure cost. FastAPI also gives you `BackgroundTasks` for free, which replaces an entire queue system at this scale.

### SQLite over PostgreSQL
Zero install, zero daemon, ships inside Python. The database is a file you can delete and recreate in one second — which you will do repeatedly on Day 1. The production PRD calls for Postgres with row-level security; that's a v1 concern, and SQLModel means the migration is mostly a connection-string change.

### faster-whisper over `openai-whisper`
Same model weights, reimplemented on CTranslate2 — roughly **4× faster with lower memory**, and it supports `int8` quantisation so it runs sensibly on CPU. It also exposes `word_timestamps=True`, which is non-negotiable here: word-level timings *are* your fluency features.

> **Quantisation, plainly:** model weights are normally 32-bit floats. Quantisation stores them as 8-bit integers instead — roughly 4× smaller and faster, with a small accuracy cost. For a demo on a laptop, that trade is obviously correct.

### Ollama over a hosted API
Removes your last network dependency, your last API key, and your last quota. It also hands you a genuinely good answer when a recruiter asks where candidate voice data goes: *nowhere — it never leaves the machine.*

### qwen3:8b over qwen2.5:3b-instruct
The build started on the 3B for speed (~2 GB resident, 10–20 s on CPU) and was later switched to `qwen3:8b` (~5 GB on disk, ~6 GB resident) as the local judge (see `assessment-tool-fixes.md` §2). The 8B is a thinking model, so the judge call disables thinking — otherwise it spends the token budget reasoning and returns empty JSON. The pipeline still unloads Whisper before the judge call so the two never compete for RAM. `OLLAMA_JUDGE_MODEL` overrides the choice without a code change.

### Vite over Next.js
You need four screens and no server-side rendering, no routing, no SEO. Next.js buys you nothing here and costs you configuration.

### Tailwind over plain CSS
Not aesthetics — iteration speed. Restyling a report card is editing a `className`, not context-switching to a stylesheet.

### Recharts over Chart.js or D3
Declarative React components with a `<RadarChart>` primitive. D3 is more powerful and would cost you two hours you don't have.

---

## 4. Project structure

```
english-assessment/
├── backend/
│   ├── main.py              # FastAPI app, routes, startup warm-up
│   ├── models.py            # SQLModel: Attempt, Response, Score
│   ├── items.json           # the 9 items — written before any code
│   ├── scoring/
│   │   ├── objective.py     # answer-key comparison
│   │   ├── asr.py           # faster-whisper wrapper, module-level load
│   │   ├── features.py      # fluency arithmetic, WER
│   │   ├── judge.py         # Ollama call + Pydantic schemas
│   │   ├── clamp.py         # sanity clamp against features
│   │   └── pipeline.py      # sequential orchestrator
│   ├── audio/               # uploaded webm files
│   ├── static/listening/    # your 2 recorded call clips
│   └── demo.db              # SQLite
└── frontend/
    ├── src/
    │   ├── App.jsx          # screen state machine
    │   ├── hooks/useRecorder.js
    │   └── screens/
    │       ├── Start.jsx
    │       ├── DeviceCheck.jsx
    │       ├── Test.jsx
    │       ├── Submitting.jsx
    │       ├── Report.jsx
    │       └── Recruiter.jsx
    └── vite.config.js       # /api proxy to :8000
```

---

## 5. Configuration that will bite you

### Vite proxy — do this first or you'll fight CORS all day
```js
// vite.config.js
export default {
  server: {
    proxy: { '/api': 'http://localhost:8000' },
    host: true,          // exposes on LAN so your phone can reach it
  },
}
```
`host: true` is what lets you test on your actual phone over wifi. Without it Vite binds to localhost only and your phone gets nothing.

### Load Whisper once, at module level
```python
# scoring/asr.py
from faster_whisper import WhisperModel
_model = WhisperModel("small", device="cpu", compute_type="int8")
```
Loading inside the request handler reloads ~1 GB on every call. Slow enough to look broken.

### Ollama keep-alive
```python
options={"temperature": 0, "num_predict": 400, "num_ctx": 4096}
keep_alive="30m"
```
Default unload is ~5 minutes idle. An unload between rehearsal and demo adds 15–30 s to your first live score.

### MediaRecorder MIME type
```js
new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
```
Safari historically prefers `audio/mp4`. Feature-detect with `MediaRecorder.isTypeSupported()` if you might demo from an iPhone — but Chrome on Android is the safer demo device regardless.

### Mic access requires a secure context
`getUserMedia` only works on `https://` or `localhost`. Testing on your phone over LAN means `http://192.168.x.x`, which browsers treat as insecure — **the mic will silently fail.** Two options: `vite --https` with a self-signed cert, or tunnel via `ngrok`. Discover this on Day 2 morning, not Day 3 night.

---

## 6. Migration path to production

Nothing here is a dead end. Each swap is roughly a config change, not a rewrite.

| Demo | Production | Effort |
|---|---|---|
| SQLite | PostgreSQL + row-level security | Connection string + migration; SQLModel definitions unchanged |
| `BackgroundTasks` | Redis + RQ workers | Extract the pipeline function into a job; it's already a single entry point |
| Local `./audio/` | S3 / Cloudflare R2, presigned upload | New endpoint returning a presigned URL; client uploads direct |
| Ollama 3B | Hosted LLM or a larger self-hosted model | Swap the judge module; schema stays identical |
| Whisper `small` CPU | Whisper `medium` on a T4 | Change two constructor args |
| `items.json` | `items` table + admin CRUD | The JSON schema becomes the table schema |
| No auth | JWT + tenant scoping | The only genuine greenfield addition |

The one thing you should design for now and can't retrofit cheaply is **tenant scoping**. It's out of demo scope — but if you find yourself adding auth mid-build, add `tenant_id` to all three tables while you're in there.

---

## 7. What you are deliberately not using

Naming these matters, because someone will ask why.

| Not used | Why not, for this build |
|---|---|
| **WhisperX** | Better forced alignment, but faster-whisper's word timestamps are sufficient for fluency features. Adds a heavy dependency |
| **wav2vec2 + GOP** | Real phoneme-level pronunciation scoring. A five-day build on its own; read-aloud WER stands in |
| **LanguageTool** | Grammar error density. Requires a Java runtime; the LLM judge covers it adequately at demo scale |
| **sentence-transformers** | Semantic relevance scoring. The LLM judge already assesses task fulfilment |
| **LightGBM** | Feature-vector → band regression. Needs 500+ human labels you don't have yet |
| **Redis / Celery** | Job queueing. One concurrent user does not need a queue |
| **Docker** | Adds a build step and a GPU-passthrough headache to a three-day timeline |

Every one of these appears in the production PRD. None of them belongs in a three-day demo.
