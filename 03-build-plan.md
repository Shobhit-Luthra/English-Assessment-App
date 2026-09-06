# Build Plan — Task by Task

Every task has an **acceptance criterion**. If you can't state that it passed, the task isn't done and you don't move on.

Estimates assume focused work. Total ≈ 25 hours across 3 days plus a 1-hour pre-flight.

---

## DAY 0 — Pre-flight (1 h, do this today)

Purpose: discover environment problems while you still have three days to route around them.

### T0.1 · Install Ollama, pull the model · 15 min
```bash
# install Ollama for your OS, then:
ollama pull qwen2.5:3b-instruct
ollama run qwen2.5:3b-instruct "say hello"
```
**Accept:** model responds in the terminal.

### T0.2 · Timing test — the decisive number · 20 min
Write a throwaway script: fake transcript, fake feature values, Pydantic schema, one `ollama.chat` call with `format=`.
```python
import time, ollama
from pydantic import BaseModel
class S(BaseModel):
    fluency: int; grammar: int; justification: str
t = time.time()
r = ollama.chat(model="qwen2.5:3b-instruct",
    messages=[{"role":"user","content": FAKE_PROMPT}],
    format=S.model_json_schema(),
    options={"temperature":0,"num_predict":400}, keep_alive="30m")
print(time.time()-t, r["message"]["content"])
```
**Accept:** valid JSON returned, and you have written the elapsed seconds down.
**Decision gate:** > 45 s → use a smaller model or shorten `num_predict` before Day 1.

### T0.3 · Python env + ffmpeg + Whisper smoke test · 20 min
```bash
pip install fastapi uvicorn sqlmodel faster-whisper ollama pydantic python-multipart
ffmpeg -version   # must exist on PATH
```
Record a 10-second voice memo, transcribe it with `word_timestamps=True`.
**Accept:** transcript prints, and `segments[0].words[0].start` returns a float.

### T0.4 · Record model choice · 5 min
Write your chosen Whisper size and Ollama model at the top of your notes. Do not revisit this on Day 3.

---

## DAY 1 — Items and the text-only spine (~8 h)

### Morning — content first (2.5 h)

> Do not open an editor for backend code until T1.6 is done. Every hour spent on FastAPI before the items exist is an hour you spend rewriting the renderer.

### T1.1 · Write the rubric · 45 min
One page. Six bands. For each of: fluency, grammar, vocabulary, task fulfilment, tone.
Descriptors must be **observable**, not impressionistic — "pauses mid-clause more than twice per 100 words," not "sometimes hesitant."
**Accept:** you could hand this to a stranger and they'd score a transcript roughly as you would.

### T1.2 · Author 4 grammar/vocab MCQs · 20 min
One each: subject-verb agreement, tense consistency, preposition choice, contextual synonym.
**Accept:** each has exactly one defensible answer and three plausible distractors.

### T1.3 · Record 2 listening clips + write their MCQs · 40 min
30 seconds each. Clip 1: billing dispute. Clip 2: delivery complaint. Read from a script, deliberately natural.
MCQ 1 = main idea. MCQ 2 = specific detail.
**Accept:** clips saved as mp3/wav in `./static/listening/`, playable in a browser.

### T1.4 · Write the writing task · 10 min
**Accept:** prompt states the scenario, the required output type, and a word target.

### T1.5 · Write the 2 speaking prompts · 20 min
S1: ~40-word reference passage for read-aloud, customer-service register.
S2: situational prompt that forces explanation or sequence.
**Accept:** you answered S2 aloud yourself and produced ≥ 60 words without effort.

### T1.6 · Assemble `items.json` · 20 min
```json
{
  "items": [
    {"id":"g1","section":"grammar","type":"mcq",
     "prompt":"...","options":["...","...","...","..."],"answer":"b"},
    {"id":"l1","section":"listening","type":"mcq",
     "audio":"/static/listening/call1.mp3","prompt":"...",
     "options":[...],"answer":"c"},
    {"id":"w1","section":"writing","type":"text",
     "prompt":"...","word_target":100,"time_limit_s":180},
    {"id":"s1","section":"speaking","type":"read_aloud",
     "reference_text":"...","time_limit_s":30,"prep_s":10},
    {"id":"s2","section":"speaking","type":"situational",
     "prompt":"...","time_limit_s":45,"prep_s":20}
  ]
}
```
**Accept:** file parses; every item has `id`, `section`, `type`.

---

### Late morning — backend skeleton (1.5 h)

### T1.7 · FastAPI + SQLModel + SQLite · 45 min
Three tables per the PRD. `create_all()` on startup. Static file mount for `./static/`.
**Accept:** `uvicorn` starts, `demo.db` file appears on disk.

### T1.8 · `GET /api/items` and `POST /api/attempts` · 30 min
**Accept:** curl returns your items JSON; creating an attempt returns a UUID and inserts a row.

### T1.9 · `POST /api/attempts/{id}/response` (text) · 20 min
Accepts `item_id` + `text`. Upsert, so re-submitting an item overwrites.
**Accept:** two posts for the same `item_id` produce one row, not two.

---

### Afternoon — React and end-to-end text flow (4 h)

### T1.10 · Vite + React + Tailwind scaffold · 20 min
Proxy `/api` to the FastAPI port in `vite.config.js`.
**Accept:** a fetch to `/api/items` from the browser returns data without a CORS error.

### T1.11 · Screen state machine · 30 min
`useState` over `start | check | test | submitting | report`. No router.
**Accept:** buttons move you through all five states.

### T1.12 · MCQ item component · 40 min
Renders prompt, options as radio cards, optional audio player for listening items. Selecting posts to the API.
**Accept:** answering a grammar item persists a row in SQLite.

### T1.13 · Writing item component · 20 min
Textarea with live word count against the target.
**Accept:** count updates as you type; text persists on Next.

### T1.14 · Timer component · 20 min
Per-item countdown driving auto-advance at zero.
**Accept:** timer visibly counts and advances the screen when it hits zero.

### T1.15 · Objective scorer · 30 min
Server-side compare against answer keys → raw correct → band via fixed thresholds.
**Accept:** a known-correct set of answers yields band 6; all-wrong yields band 1.

### T1.16 · `POST /submit` + `GET /report` · 40 min
Submit scores objective sections synchronously, writes `Score` rows, sets status. Report returns bands + evidence.
**Accept:** submit → report returns grammar and listening bands as JSON.

### T1.17 · Bare report screen · 30 min
Numbers only. No chart, no styling beyond legible.
**Accept:** **you take a full text-only test on your phone and see real bands.**

> **Day 1 milestone:** end-to-end text test working on a phone. If this isn't true at the end of Day 1, cut the listening section on Day 2 rather than compressing audio work.

---

## DAY 2 — Audio and the scoring engine (~8 h)

### Morning — capture and upload (2.5 h)

### T2.1 · `useRecorder` hook · 45 min
MediaRecorder → `audio/webm;codecs=opus`, chunk collection, hard stop at the item time limit.
**Accept:** produces a Blob you can play back in the browser.

### T2.2 · Device check screen · 45 min
Mic permission request → 5 s record → playback → "I could hear myself" confirm. Blocking.
**Accept:** cannot reach the test without confirming.

### T2.3 · Speaking item component · 45 min
Prep countdown → auto-start recording → visible timer → auto-stop → single playback → submit. No re-record.
**Accept:** the flow runs without any button being clickable out of order.

### T2.4 · `POST /audio` endpoint · 30 min
Multipart, saves to `./audio/{attempt_id}/{item_id}.webm`, writes `Response` row with `audio_path` and `duration_ms`.
**Accept:** file lands on disk and `ffprobe` reports the expected duration.

---

### Afternoon — ASR and features (3 h)

### T2.5 · Whisper transcription function · 30 min
Load once at module level, not per call. `word_timestamps=True`. Flatten segments to a word list.
**Accept:** returns transcript string + list of `(word, start, end)`.

### T2.6 · Fluency feature extractor · 60 min
Implement all six formulas from PRD §5.2 as pure functions over the word list.
**Accept:** unit-check against a hand-computed 5-word example.

### T2.7 · Read-aloud WER · 30 min
Normalise case and punctuation, then token-level Levenshtein against `reference_text`.
**Accept:** identical strings → 0.0; completely different → ~1.0.

### T2.8 · Threshold calibration · 45 min
Record three S2 responses: fluent, moderate, deliberately halting. Run all three through the extractor. Print the feature table.
**Accept:** `speech_rate`, `phonation_ratio`, and `mean_length_of_run` **visibly separate** the three. If they don't, your `PAUSE_THRESHOLD` is wrong — tune before proceeding.

> This is the most important 45 minutes of the build. If features don't discriminate here, nothing downstream can.

---

### Evening — the judge (2.5 h)

### T2.9 · Pydantic schemas, discriminated by item type · 30 min
```python
class SpeakingScore(BaseModel):
    item_id: str; fluency: int; grammar: int
    vocabulary: int; task_fulfilment: int; justification: str

class WritingScore(BaseModel):
    item_id: str; grammar: int; vocabulary: int
    tone_appropriateness: int; task_fulfilment: int; justification: str

class AttemptScores(BaseModel):
    speaking: list[SpeakingScore]
    writing: list[WritingScore]
```
**Accept:** `model_json_schema()` emits valid JSON Schema.

### T2.10 · Prompt builder · 45 min
Embeds the rubric, item prompts, transcripts, and features **with interpretations attached**. One prompt covering all open-ended items in the attempt.
**Accept:** printed prompt is under ~3,000 tokens and reads coherently to you.

### T2.11 · Ollama judge call · 30 min
`format=AttemptScores.model_json_schema()`, `temperature=0`, `keep_alive="30m"`.
**Accept:** returns a parsed `AttemptScores` for a real attempt.

### T2.12 · Sanity clamp · 20 min
```python
if feats["speech_rate"] < 90 and feats["mean_length_of_run"] < 4:
    score.fluency = min(score.fluency, 3)
```
**Accept:** feed your deliberately-halting recording; fluency does not exceed 3.

### T2.13 · Sequential pipeline orchestrator · 45 min
`BackgroundTasks` job: transcribe all audio → extract features → **release Whisper** → one judge call → clamp → compute CIR → write `Score` rows → status `done`.
**Accept:** **speak into your phone, and 30 seconds later a real band appears.**

> **Day 2 milestone:** D1 satisfied. The demo now technically works. Everything on Day 3 is making it convincing.

---

## DAY 3 — Making it look like a product (~8 h)

### Morning — the report page (3 h)

### T3.1 · CIR composite · 20 min
Weighted arithmetic per PRD §5.5.
**Accept:** hand-compute one attempt and match.

### T3.2 · Radar chart · 45 min
Recharts `<RadarChart>`, five axes, domain 0–6.
**Accept:** renders with real data, not placeholders.

### T3.3 · Audio player beside its score · 40 min
For each speaking item: player, its band, its justification, side by side.
**Accept:** **you can click play and the score sits in the same visual block.** This is the demo's most important pixel.

### T3.4 · Transcript + evidence display · 30 min
Transcript text, the fluency numbers in a small table, the judge's one-liner.
**Accept:** D3 satisfied — every band has visible evidence.

### T3.5 · Overall band + recommendation banner · 25 min
Large band number, colour-coded, "Recommended / Borderline / Not recommended" against a fixed threshold.
**Accept:** colour changes when you edit a band value in the DB.

---

### Afternoon — recruiter view and safety net (3 h)

### T3.6 · Recruiter table · 45 min
`GET /api/attempts` → table with name, overall, five sub-bands, timestamp, report link. Click a header to sort.
**Accept:** sorting by overall band reorders correctly.

### T3.7 · Seed 4–5 attempts · 60 min
Record yourself and 2–3 others at deliberately different proficiency levels. Run each through the real pipeline. Leave them in the DB.
**Accept:** D2 and D6 satisfied — the table shows a visible band spread, and pulling the network cable still leaves you a demo.

### T3.8 · Warm-up on startup · 15 min
Fire a dummy Ollama call on FastAPI startup so the model is resident before anyone touches the app.
**Accept:** first real scoring after a restart is no slower than the second.

### T3.9 · Airplane-mode test · 15 min
Disable all networking. Complete a full attempt.
**Accept:** D4 satisfied.

### T3.10 · Mobile responsive pass · 45 min
Test at 380 px width. Tap targets ≥ 44 px. No horizontal scroll.
**Accept:** the whole flow is comfortable one-handed on the actual demo phone.

---

### Evening — rehearsal (1.5 h)

### T3.11 · Three full run-throughs · 45 min
On the real demo phone, on mobile data, following the §8 narrative. Time yourself.
**Accept:** D5 satisfied and you hit 5 minutes without notes.

### T3.12 · Write the limitations card · 20 min
The four items from PRD §10 on one index card or slide.
**Accept:** you can deliver them from memory.

### T3.13 · Failure drill · 25 min
Deliberately deny mic permission mid-demo and practise the pivot to seeded reports.
**Accept:** the pivot takes under 10 seconds and you don't say "um, so it normally works."

---

## Cut line — if you're behind

Drop in this order. Each cut is safe; the ones below the line are not.

1. **Listening section** (T1.3, and its items) — saves ~1 h, costs one bullet in the narrative
2. **Radar chart** (T3.2) — a clean bar list carries the same information
3. **Recruiter sorting** (half of T3.6) — a static table is fine
4. **Read-aloud item S1** — S2 alone can carry the speaking demo
5. **Mobile polish** (T3.10) — demo from a laptop instead

— **do not cut below this line** —

- T2.8 threshold calibration
- T3.3 audio-beside-score
- T3.7 seeded attempts
- T3.11 rehearsal

Those four are the demo. Everything else is supporting cast.
