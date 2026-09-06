# Demo PRD — English Proficiency Assessment Tool

**Build window:** 3 days
**Status:** pre-build spec
**Owner:** Shobhit Luthra
**Relationship to full PRD:** this is a deliberate subset. Anything not named here is out, including things the full PRD marks as v1-critical.

---

## 1. What this demo is for

**One sentence:** prove that automated scoring of spoken English produces scores a human would agree with.

Everything else — the item bank, bulk upload, multi-tenancy, proctoring — is plumbing that a viewer already assumes you can build. Nobody watches a demo and doubts you can do CSV upload. They doubt the speech scoring is real.

**The moment the demo succeeds:** a viewer clicks play on a candidate's audio, hears a hesitant speaker, sees "Fluency: 3 / 6," and believes the number came from the audio rather than from a hardcoded array.

---

## 2. Success criteria

| # | Criterion | How it's checked |
|---|---|---|
| D1 | A speaking response is scored end-to-end, live | Record 45 s on a phone → band appears within 30 s |
| D2 | Scores visibly discriminate proficiency | A strong and a weak seeded candidate differ by ≥ 2 bands on speaking |
| D3 | Every score has visible evidence | Report shows transcript, fluency numbers, and a one-line justification |
| D4 | Runs without internet except the LLM call | ASR is local; demo survives bad venue wifi |
| D5 | Full test completes in under 10 minutes | Timed self-run on mobile data |
| D6 | Graceful failure path exists | If live recording breaks, seeded reports carry the demo |

If D1 and D3 hold, the demo works. The rest is polish.

---

## 3. Scope

### In

- Single-candidate test flow, 9 items, ~8 minutes
- Mic device check before the test begins
- Auto-scoring of all four dimensions + derived CIR composite
- Individual report page with radar chart and audio playback
- Recruiter list view (read-only table, sortable by band)
- 4–5 pre-seeded scored attempts

### Out — with the reason, so it doesn't creep back in

| Cut | Why |
|---|---|
| Multi-tenancy, RLS, auth | Nothing on screen depends on it |
| Item bank CRUD / admin UI | Items live in a JSON file |
| Redis, RQ, GPU workers | `BackgroundTasks` covers one concurrent user |
| wav2vec2 GOP pronunciation | 5-day build alone; read-aloud WER is the stand-in |
| LanguageTool | Java dependency; the LLM judge handles grammar |
| Adaptive item selection, item rotation | Requires a pool that doesn't exist yet |
| CSV bulk upload, SMS invites | Demo has one candidate and one link |
| Proctoring, tab detection, voice consistency | Zero narrative value in 5 minutes |
| PDF export | Screen-share is the delivery mechanism |
| Human calibration study | Phase 4 of the real plan; state it as roadmap, don't fake it |

---

## 4. The item set (`items.json`)

Nine items. This file is written **before any code** — it defines the API shape, the React renderer, and the scoring dispatch.

### Section A — Grammar & Vocabulary (4 items, ~2 min)
MCQ, 4 options each, single correct answer.
Coverage: subject-verb agreement, tense consistency, preposition choice, contextual synonym.

### Section B — Listening (2 items, ~2 min)
Two self-recorded 30-second audio clips simulating customer calls (one billing dispute, one delivery complaint). One MCQ each — one main-idea, one specific-detail.

### Section C — Writing (1 item, ~3 min)
Constructed response, ~100 words: *"A customer's order is 5 days late and they are frustrated. Write an email reply."*
Scored on grammar, tone appropriateness, task fulfilment.

### Section D — Speaking (2 items, ~2 min) — **the demo's centre of gravity**

| ID | Type | Duration | Purpose |
|---|---|---|---|
| S1 | Read-aloud, known reference text (~40 words) | 30 s | Reference text is known → WER is computable → pronunciation proxy |
| S2 | Situational response | 45 s | Open speech → fluency features have room to appear |

**Prompt design constraint:** S2 must elicit ≥ 60 words of continuous speech. A prompt answerable in one sentence produces no usable fluency signal. Prompts must ask the candidate to explain, justify, or walk through a sequence — not to choose or state.

---

## 5. Scoring specification

### 5.1 Objective sections
Exact-match against answer key. `raw_correct / total → band 1–6` by fixed thresholds.

### 5.2 Fluency features (computed from Whisper word timestamps)

```
PAUSE_THRESHOLD = 0.25 s

speech_rate       = words / total_duration × 60
articulation_rate = words / (total_duration − silence) × 60
phonation_ratio   = (total_duration − silence) / total_duration
mean_length_of_run= words / (pause_count + 1)
pauses_per_100w   = pause_count / words × 100
filled_pause_rate  = filler_count / words × 100
```

Reference anchors used for band mapping (to be sanity-checked against own recordings on Day 2):

| Feature | Fluent | Hesitant |
|---|---|---|
| Speech rate | 130–160 wpm | < 100 wpm |
| Phonation ratio | > 0.65 | < 0.50 |
| Mean length of run | > 7 words | 3–4 words |

**Known limitation, to be stated aloud in the demo:** Whisper normalises transcripts and frequently drops disfluencies, so `filled_pause_rate` under-reports. Pause features derive from timestamps and are unaffected — they carry the weight.

### 5.3 Pronunciation proxy (S1 only)
`WER = levenshtein(reference_tokens, transcript_tokens) / len(reference_tokens)`

### 5.4 LLM rubric judge
Input: item prompt + transcript + computed acoustic features.
Output: strict JSON — `fluency`, `grammar`, `vocabulary`, `task_fulfilment` (each 1–6) + one-sentence justification.
Settings: `temperature=0`, one retry on parse failure.
Rubric instruction includes an explicit directive to score intelligibility, never accent conformity.

### 5.5 CIR composite

```
CIR = 0.35·speaking_fluency + 0.25·listening + 0.20·writing_tone + 0.20·situational_task_fulfilment
```

---

## 6. Screens

| Screen | Contents |
|---|---|
| **Start** | Name entry, recording-consent notice, "Begin" |
| **Device check** | Mic permission → 5 s record → playback → confirm. **Blocking gate.** |
| **Test** | One item per screen, visible timer, explicit Next. Speaking items: 20 s prep → record → single playback → submit, no re-record |
| **Submitting** | "Scoring your responses — about 30 seconds" with progress indicator |
| **Report** | Overall band; radar chart (5 axes); per-dimension bands; **audio player beside the score it produced**; transcript with judge justification |
| **Recruiter** | Read-only table: name, overall band, 5 sub-bands, timestamp, link to report. Sortable by band |

Navigation is `useState`, not a router.

---

## 7. Technical spec

```
Frontend   Vite + React + Tailwind + Recharts
Backend    FastAPI + SQLModel + SQLite (single file)
Async      FastAPI BackgroundTasks
Audio      MediaRecorder → audio/webm;codecs=opus → POST → ./audio/
ASR        faster-whisper "small", device=cpu, compute_type=int8,
           word_timestamps=True
Judge      Claude API, structured JSON
Deps       fastapi uvicorn sqlmodel faster-whisper anthropic python-multipart
           + ffmpeg on PATH (required to decode webm)
```

### Data model — three tables

```python
Attempt   id(uuid) · name · status(in_progress|scoring|done) · created_at
Response  id · attempt_id · item_id · text? · audio_path? · duration_ms?
Score     id · attempt_id · dimension · band · evidence(JSON)
```

`evidence` holds transcript, feature dict, and judge justification — it is what the report page renders, and what makes D3 achievable.

### API surface — six endpoints

```
POST /api/attempts                        → create, returns attempt_id
GET  /api/items                           → serve items.json
POST /api/attempts/{id}/response          → text response (MCQ/writing)
POST /api/attempts/{id}/audio             → multipart audio + item_id
POST /api/attempts/{id}/submit            → triggers background scoring
GET  /api/attempts/{id}/report            → bands + evidence
GET  /api/attempts                        → recruiter list
```

---

## 8. Build sequence

| Day | Morning | Afternoon / Evening |
|---|---|---|
| **1** | `items.json` (2 h) → data model, FastAPI skeleton | React shell, 4 screens, MCQ + writing end-to-end scored |
| **2** | MediaRecorder, device check, upload endpoint | faster-whisper + feature extractor + LLM judge |
| **3** | Report page, radar chart, audio player | Recruiter table, **seed 4–5 attempts**, rehearse on the demo phone |

---

## 9. Demo narrative (5 minutes)

1. Recruiter table, sorted by band — *"Here's a recruiter with a pipeline."*
2. Open a **low-band** report → **play the audio** → point at the fluency number and its justification
3. Open a **high-band** report on the same items → contrast
4. Take a 90-second speaking item live → score appears
5. Roadmap in one line: item bank, bulk upload, validation study against expert human raters

Step 2 is the demo. Steps 1, 3, 4, 5 are framing.

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Live recording fails at the venue | ~30% | Seeded attempts — pivot to recruiter table without breaking stride |
| Venue wifi dies | Medium | ASR is local; only the LLM call needs network. Pre-cache judge output for seeded attempts |
| Whisper WER poor on the demoer's accent | Medium | Test on Day 2 morning, not Day 3 night. Fall back to `medium` model if needed |
| Scoring slower than 30 s | Medium | `small` + int8 on CPU ≈ 5–10× realtime. Measure Day 2; drop to `base` if it drags |
| LLM returns unparseable JSON | Low | try/except + one retry; fall back to feature-only heuristic band |
| Feature thresholds mis-calibrated → all candidates score 4 | Medium | Record 3 deliberately different-proficiency samples on Day 2 and tune anchors against them |

---

## 11. What this demo explicitly does not claim

Say these out loud rather than waiting to be caught:

- Scores are **not** validated against human raters yet — that's the Phase 4 study, n = 200
- **Not** CEFR-aligned; CEFR-*referenced* band descriptors only
- Pronunciation is a proxy (read-aloud WER), not phoneme-level GOP scoring
- Item pool is 9 items, not the 200+ a real deployment needs

Naming a limitation before someone finds it reads as engineering judgment. Being caught hiding one costs the whole demo.
