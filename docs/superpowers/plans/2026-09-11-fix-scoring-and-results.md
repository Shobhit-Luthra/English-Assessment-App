# Plan: fix scoring and results

## Context

The user reports metrics/results coming up empty on the analytics dashboard,
recruiter directory and candidate report. Read-only investigation found the
immediate cause is environmental (a freshly recreated `demo.db` with one
unsubmitted attempt; Ollama not running) — but tracing the scoring path found
real defects that make results incomplete or silently missing even when the
environment is healthy:

1. **Skipped items silently drop dimensions and the overall score.**
   `scoring/pipeline.py::_run` skips any speaking item without audio and any
   writing item without text. `situational_task_fulfilment` / `writing_tone`
   rows are then never written, `components` has a `None`, and **no `cir` row
   is created** — yet the attempt is marked `done`. It then shows "done" with no
   CIR on `/results`, no band in the recruiter directory, and is excluded from
   every analytics aggregate. The attempt currently in `demo.db` (s1 uploaded,
   s2 not) would land exactly here. A skipped task must score band 1, not vanish.
2. **Most of the judged rubric is thrown away.** The judge returns grammar,
   vocabulary, task_fulfilment (+ fluency / tone) per item
   (`scoring/schemas.py`), but the pipeline persists only `fluency`,
   `task_fulfilment` and `tone_appropriateness`, averaging the rest into an
   opaque `components: [float]` list. `Report.jsx` therefore shows writing as a
   single "Tone Appropriateness" number and speaking as fluency only.
3. **Judge output is not validated against the attempt.** `judged.speaking` /
   `judged.writing` are iterated as returned: an omitted item silently produces
   the gap in (1); a hallucinated `item_id` is stored as a real score row.
4. **qwen3:8b is a thinking model and the call does not disable thinking.**
   `judge.py` compensates with `num_predict: 2400`; when reasoning exhausts
   that, `message.content` is empty and `model_validate_json` raises →
   attempt `error`. `ollama` python 0.6.2 supports `think=False`.
5. **Error path leaks and dead-ends.** `attempt.error = str(e)` is returned
   verbatim by `/report` and rendered by `Report.jsx`; there is no way to
   re-run scoring, so an attempt that failed because Ollama was down is lost.
   `Results.jsx` renders `status === "error"` as "Scoring…" forever.
6. **Radar and recruiter views disagree.** `ScoreRadar` plots
   `writing_tone` / `situational_task_fulfilment` / fluency; the recruiter
   directory and analytics use the composite `speaking` / `writing` rows. The
   CIR formula (`CIR_WEIGHTS`) uses a third mix.

Docs still name `qwen2.5:3b-instruct`; code defaults to `qwen3:8b` (user chose
docs alignment only — but item 4 is a scoring-correctness fix, so `think=False`
is included here, with a fallback for servers that reject the parameter).

`docs/ENGINEERING_RULES.md` applies throughout.

## Changes

### 1. Pipeline: every attempt gets every dimension and a CIR
`backend/scoring/pipeline.py`
- Before transcription, build the expected sets: `expected_speaking`
  (`{item_id: item}` for all speaking items) and `expected_writing`.
- Speaking item with no audio → write the same rows a judged item would get,
  band 1, `evidence={"item_id", "missing": true}` (both
  `speaking_fluency_<id>` and, for situational, `situational_task_fulfilment`).
  Writing item with no text → `writing_tone` band 1, `missing: true`.
- Keep the deterministic S1 path unchanged (`deterministic_fluency_band`,
  `band_from_wer`).
- After `call_judge`, **validate**: drop any returned `item_id` not in the
  expected set (log a warning); for any expected-but-absent judged item, retry
  the judge once for the missing items only, then if still absent raise
  `JudgeIncompleteError`.
- Persist the full rubric on the existing rows (no schema change — `evidence`
  is JSON): `speaking_fluency_<id>.evidence.scores = {fluency, grammar,
  vocabulary, task_fulfilment}`, `writing_tone.evidence.scores = {grammar,
  vocabulary, tone_appropriateness, task_fulfilment}`. Composite `speaking` /
  `writing` rows keep `components` and gain `evidence.by_item`.
- CIR: with (1) every component is always present; keep `CIR_WEIGHTS`. If a
  component is still `None` (should be impossible) raise instead of silently
  finishing without `cir`.
- Failure handling in `run_scoring_pipeline`: map exceptions to a short
  category stored in `attempt.error` — `"judge_unavailable"` (ollama
  `ConnectError`/`ResponseError`), `"judge_invalid_output"`
  (`ValidationError` / `JudgeIncompleteError`), `"asr_failed"`, `"unknown"`;
  log the full traceback server-side only. Rows already written (objective,
  S1) are kept via a `session.commit()` before the judge call.

### 2. Judge call
`backend/scoring/judge.py`
- `call_judge`: pass `think=False`; on `ollama.ResponseError` mentioning the
  `think` option, retry once without it (older server). Keep `format=schema`,
  `temperature 0`, `num_ctx 8192`; drop `num_predict` to 1200 once thinking is
  off (JSON for 1 writing + 1 speaking item is ~300 tokens).
- Add `build_prompt(..., only_item_ids=...)` support for the partial retry.
- Prompt: list the exact `item_id`s that must appear in the output so the
  model cannot omit one.

### 3. Re-score endpoint and health
`backend/routes/attempts.py`
- `POST /api/attempts/{attempt_id}/rescore` — `require("candidates.view")`;
  only when `status == "error"`; deletes every row except `grammar`,
  `listening` (objective) and re-queues `run_scoring_pipeline` with the same
  `items_by_section` rebuilt from `attempt.item_ids` (reuse the loop already in
  `submit_attempt` — extract `_items_by_section(attempt)`).
- `get_report`: return `error` as the category string only (it now is), plus
  `error_message` mapped server-side from a fixed dict of user-safe sentences.
`backend/main.py`
- `GET /api/health` → `{"ollama": bool, "whisper": bool}` (cheap: `ollama.list()`
  with a 2 s timeout; whisper = model object loaded). No auth, no internals.

### 4. Results & report UI
`frontend/src/screens/Report.jsx`
- Header: CIR band + recommendation (unchanged thresholds).
- Radar (`ScoreRadar.jsx`): plot the five CIR-relevant dimensions the backend
  actually stores — Grammar, Listening, Speaking (composite), Writing
  (composite), Task fulfilment — so it matches the recruiter view.
- Speaking cards: show `evidence.scores` as a 4-cell sub-skill row (Fluency /
  Grammar / Vocabulary / Task) when present; keep transcript, reference text,
  acoustic stats, audio.
- Writing card: title "Writing", composite band, 4-cell sub-skill row, response
  text, justification.
- Missing items: render the card with a "Not attempted" badge instead of a
  band.
- `status === "error"`: show `error_message`; for users with
  `candidates.view` show a "Re-score" button → `rescoreAttempt(id)` then poll
  with the existing `pollReport`.
`frontend/src/screens/Results.jsx`
- Distinct rows for `in_progress` (Resume), `scoring` (Scoring…), `error`
  ("Scoring failed — a recruiter can re-run it"), `done` (View report + CIR).
`frontend/src/screens/Submitting.jsx` / `flows/CandidateFlow.jsx`
- On entering `submitting`, call `getHealth()`; if `ollama === false` show
  "The scoring engine is offline; your answers are saved and will be scored
  when it is back" instead of the spinner text, and stop polling after the
  report returns `error`.
`frontend/src/api.js`: add `rescoreAttempt`, `getHealth`.
`frontend/src/screens/Analytics.jsx`, `Recruiter.jsx`: one-line empty state
when there are no completed attempts ("Metrics appear after the first
completed assessment").

### 5. Seed script and docs
- `backend/requirements.txt`: add `httpx` (only transitively present).
- `backend/seed_attempts.py`: drop the ignored `name` field; print the
  categorised error if an attempt ends in `error`.
- `SETUP.md`, `docs/04-tech-stack.md`, `docs/BUILD_LOG.md`: `qwen3:8b`,
  `OLLAMA_JUDGE_MODEL` in the env table, note the RAM need and the
  "seed_attempts populates the dashboards" step.

## Tests
- `tests/test_scoring_scope.py`: missing speaking audio → band-1 rows +
  `cir` present; missing writing text → same; judge omits an item → retry
  called, then `judge_invalid_output`; judge returns unknown `item_id` →
  ignored; full sub-scores persisted in `evidence.scores`; every failure
  category maps correctly and objective rows survive.
- `tests/test_attempts_api.py`: rescore — 403 for candidate, 409 unless
  `error`, resets to `scoring`, keeps `grammar`/`listening`; `/report` never
  contains a traceback string; `/api/health` shape.
- Frontend vitest: `Report` renders sub-skill rows, "Not attempted", error +
  rescore button (permission-gated); `Results` renders the four statuses;
  `Submitting` offline message.
- Existing suites must stay green: backend 74 → more, frontend 31 → more.

## Verification
```bash
cd backend && python -m pytest -q
cd frontend && npm run lint && npm run test && npm run build
```
End-to-end (Ollama running, `ollama pull qwen3:8b`):
1. `ASSESSMENT_ALLOW_FIXED_SELECTION=1 uvicorn main:app --port 8000`;
   `python seed_attempts.py` → 4 attempts `done`, each with a CIR and a spread.
2. As recruiter: `/dashboard` shows bands, `/analytics` non-zero; open a report
   → sub-skill rows visible for speaking and writing.
3. Submit an attempt that skips S2 → report shows S2 "Not attempted", CIR still
   present.
4. Stop Ollama, submit → `/results` shows "Scoring failed", report shows the
   safe message; start Ollama, Re-score → `done`.

## Out of scope (from the earlier broader request; do after this lands)
Security audit (unauthenticated `/audio` mount is the priority), dead-code
removal, bundle splitting, UI polish pass. Each is its own follow-up.
