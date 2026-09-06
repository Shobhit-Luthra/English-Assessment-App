# Build Log

Tracks task completion against `03-build-plan.md`. One line per task once its acceptance criterion is verified.

## Day 0 — Pre-flight

- **Model choice:** Whisper `small` (CPU, int8) · Ollama `qwen2.5:3b-instruct`
- T0.1 — Ollama installed (winget, pre-existing), model pulled, terminal smoke test passed ("Hello! How can I assist you today?")
- T0.2 — Structured-output timing test: 1.70s (well under the 45s gate), valid JSON, sane bands
- T0.3 — Python 3.14.6 env + ffmpeg (winget) + faster-whisper smoke test passed: transcript correct, `words[0].start` returned a float
- T0.4 — Model choice recorded above

## Day 1 — Items and the text-only spine

- T1.1 — Rubric written: 6 bands x {fluency, grammar, vocabulary, task fulfilment, tone}, observable descriptors (`backend/scoring/rubric.md`)
- T1.2 — 4 grammar/vocab MCQs authored (subject-verb agreement, tense, preposition, contextual synonym)
- T1.3 — 2 listening clips synthesized (SAPI TTS, two alternating voices) at `backend/static/listening/call{1,2}.wav`, ~33s/~38s, each with an MCQ. **Known placeholder:** TTS-generated, not human-recorded — the PRD calls for a genuine recording; swap before a live demo if a more natural clip is wanted.
- T1.4 — Writing task authored (late-order email reply, 100-word target, 180s)
- T1.5 — Speaking prompts S1 (43-word read-aloud reference) and S2 (situational, forces a "walk me through" explanation) authored
- T1.6 — `items.json` assembled: 9 items, parses, every item has `id`/`section`/`type`
- T1.7 — FastAPI + SQLModel + SQLite skeleton (`main.py`, `models.py`, `db.py`); `/static` mounted; `demo.db` created on startup
- T1.8 — `GET /api/items` and `POST /api/attempts` verified via curl
- T1.9 — `POST /api/attempts/{id}/response` verified: two submits for the same `item_id` produce exactly one row (upsert via unique constraint), 400 on unknown item, 404 on unknown attempt
- **Security fix:** `GET /api/items` was returning `items.json` verbatim, including the MCQ `"answer"` field — a candidate could read the answer key from the network tab. Fixed by serving a filtered copy with `answer` stripped; scoring uses the raw in-memory copy server-side. Also added an `attempt.status` guard so responses/submission can't be replayed after an attempt leaves `in_progress`.
- **Accepted risk (by design, not a gap):** there is no auth. Any attempt UUID grants full read/write on that attempt, and `GET /api/attempts` (recruiter view) is unauthenticated. This is the explicit scope cut in `02-demo-prd.md` §3 ("Multi-tenancy, RLS, auth — Nothing on screen depends on it") and §6 migration table (auth is "the only genuine greenfield addition" for production). Not fixed here; flagged so it isn't mistaken for an oversight.
- T1.10 — Vite + React + Tailwind v4 scaffold; `/api` and `/static` proxied to `:8000`; verified via curl through the Vite dev server with the backend running
- T1.11 — Screen state machine (`useState`, no router): `start → test → submitting → report`. (`check` deferred to Day 2 — building a mic-permission gate before a recorder exists would be a placeholder, not a real gate.)
- T1.12 — MCQ item component: renders prompt/options/audio player, posts to the API on selection
- T1.13 — Writing item component: textarea with live word count against `word_target`
- T1.14 — Timer component: per-item countdown, auto-advances via `onExpire`
- T1.15 — Objective scorer (`scoring/objective.py`): fixed-threshold band mapping; verified all-correct → band 6, all-wrong → band 1
- T1.16 — `POST /submit` (scores grammar+listening, locks the attempt) and `GET /report` verified end-to-end via curl
- T1.17 — Bare report screen (numbers only, no chart yet)
- Frontend build (`npm run build`) and lint (`oxlint`) both clean. **Not yet verified in an actual browser** — no browser-automation tool is available in this environment; verification so far is production build + lint + manual code trace + curl against the API through the Vite proxy. A real click-through (ideally on a phone, per D1) is still owed before Day 1 is considered done.
