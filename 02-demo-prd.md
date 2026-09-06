# Demo PRD — 3-Day Build

**Build window:** 3 days
**Cost:** ₹0 — fully local, no external API, no network at runtime
**Relationship to product PRD:** deliberate subset. Anything not named here is out, including things the product PRD marks v1-critical.

---

## 1. What this demo is for

**One sentence:** prove that automated scoring of spoken English produces scores a human would agree with.

Nobody watches a demo and doubts you can build CSV upload. They doubt the speech scoring is real.

**The moment it succeeds:** a viewer clicks play on a candidate's audio, hears a hesitant speaker, sees *Fluency: 3 / 6*, and believes the number came from the audio rather than a hardcoded array.

---

## 2. Success criteria

| # | Criterion | Check |
|---|---|---|
| D1 | Speaking response scored end-to-end, live | Record 45 s on phone → band within 30 s |
| D2 | Scores visibly discriminate proficiency | Strong vs weak seeded candidate differ ≥ 2 bands on speaking |
| D3 | Every score has visible evidence | Report shows transcript, fluency numbers, one-line justification |
| D4 | Runs with **no internet at all** | Disable wifi, complete a full attempt |
| D5 | Full test under 10 minutes | Timed self-run on the demo phone |
| D6 | Graceful failure path | If live recording breaks, seeded reports carry the demo |

D1 and D3 make the demo work. The rest is polish.

---

## 3. Scope

### In
Single-candidate test flow (9 items, ~8 min) · mic device check · auto-scoring of four dimensions + derived CIR · report page with radar chart and audio playback · read-only recruiter table · 4–5 pre-seeded scored attempts.

### Out — with reasons, so it doesn't creep back in

| Cut | Why |
|---|---|
| Multi-tenancy, RLS, auth | Nothing on screen depends on it |
| Item bank CRUD / admin UI | Items live in a JSON file |
| Redis, RQ, GPU workers | `BackgroundTasks` covers one concurrent user |
| wav2vec2 GOP pronunciation | 5-day build alone; read-aloud WER is the stand-in |
| LanguageTool | Java dependency; the LLM judge handles grammar |
| Adaptive selection, item rotation | Requires a pool that doesn't exist yet |
| CSV upload, SMS invites | Demo has one candidate and one link |
| Proctoring, tab detection | Zero narrative value in 5 minutes |
| PDF export | Screen-share is the delivery mechanism |
| Human calibration study | Phase 4 of the real plan — state as roadmap, never fake |

---

## 4. Item set (`items.json`)

Nine items. Written **before any code** — this file defines the API shape, the React renderer, and the scoring dispatch.

### A — Grammar & Vocabulary · 4 MCQs · ~2 min
Subject-verb agreement, tense consistency, preposition choice, contextual synonym. 4 options each, one correct.

### B — Listening · 2 MCQs · ~2 min
Two self-recorded 30-second customer-call clips (billing dispute, delivery complaint). One main-idea MCQ, one specific-detail MCQ.

### C — Writing · 1 item · ~3 min
*"A customer's order is 5 days late and they are frustrated. Write an email reply."* (~100 words). Scored on grammar, tone appropriateness, task fulfilment.

### D — Speaking · 2 items · ~2 min — **the centre of gravity**

| ID | Type | Duration | Purpose |
|---|---|---|---|
| S1 | Read-aloud, known reference text (~40 words) | 30 s | Reference known → WER computable → pronunciation proxy |
| S2 | Situational response | 45 s | Open speech → fluency features have room to appear |

**Prompt design constraint:** S2 must elicit ≥ 60 words of continuous speech. A prompt answerable in one sentence produces no usable fluency signal. Ask the candidate to *explain, justify, or walk through* — never to *choose or state*.

---

## 5. Scoring architecture

### 5.1 Who scores what

| Section | Scorer | Model? |
|---|---|---|
| Grammar & Vocab MCQs | Answer-key compare | None |
| Listening MCQs | Answer-key compare | None |
| Writing | LLM judge | Yes (text only) |
| Speaking S1 | Whisper → WER + fluency arithmetic | Whisper only |
| Speaking S2 | Whisper → fluency arithmetic + LLM judge | Both |
| CIR | Weighted arithmetic | None |

**The LLM never hears audio.** It receives a transcript and numbers.

```
audio → Whisper (ASR) → transcript + word timestamps
                              ↓
                  ┌───────────┴───────────┐
          Python arithmetic          LLM judge
        (fluency, deterministic)   (language quality)
```

Fluency is measurable, so it is measured — deterministic, instant, reproducible. Meaning is not measurable, so it is judged. The LLM *sees* fluency numbers as evidence; it does not compute them.

### 5.2 Fluency features (Whisper word timestamps)

```
PAUSE_THRESHOLD = 0.25 s

speech_rate        = words / total_duration × 60
articulation_rate  = words / (total_duration − silence) × 60
phonation_ratio    = (total_duration − silence) / total_duration
mean_length_of_run = words / (pause_count + 1)
pauses_per_100w    = pause_count / words × 100
filled_pause_rate  = filler_count / words × 100
```

Anchors for band mapping — sanity-check against own recordings on Day 2:

| Feature | Fluent | Hesitant |
|---|---|---|
| Speech rate | 130–160 wpm | < 100 wpm |
| Phonation ratio | > 0.65 | < 0.50 |
| Mean length of run | > 7 words | 3–4 words |

**Known limitation, to be stated aloud:** Whisper normalises transcripts and often drops disfluencies, so `filled_pause_rate` under-reports. Pause features come from timestamps and are unaffected — they carry the weight.

### 5.3 Pronunciation proxy (S1 only)

`WER = levenshtein(reference_tokens, transcript_tokens) / len(reference_tokens)`

### 5.4 LLM rubric judge — local via Ollama

**Model:** `qwen2.5:3b-instruct` on CPU; `qwen2.5:7b-instruct` if a GPU is present.

| Model | RAM (q4) | Judge call, CPU |
|---|---|---|
| qwen2.5:3b-instruct | ~2 GB | 10–20 s |
| qwen2.5:7b-instruct | ~5 GB | 30–60 s |

**Batching:** all open-ended responses for one attempt go in a **single call** returning a scores array.

**Resource contention (critical):** Whisper and Ollama compete for the same CPU and RAM. The pipeline runs **strictly sequentially** — transcribe everything → release the Whisper model → one batched judge call. Concurrent execution causes swapping and multi-minute stalls.

**`keep_alive="30m"`** on every call. Ollama unloads idle models after ~5 min; an unload between rehearsal and demo adds 15–30 s to the first live score. Fire a warm-up call immediately before presenting.

**Input:** item prompts + transcripts + acoustic features **with interpretation attached** — `phonation_ratio=0.42 (below 0.65 fluent threshold; silent 58% of the time)`. Small models reason poorly over bare numbers, well over labelled evidence.

**Output:** enforced via Ollama's `format=` parameter taking a Pydantic JSON schema. Discriminated by item type — speaking items get `fluency`, writing items get `tone_appropriateness`; a flat shared schema produces garbage fields for half the items.

**Settings:** `temperature=0`, `num_predict=400`, `num_ctx=4096`.

**Sanity clamp:** schema constraint guarantees the JSON parses, not that bands are sensible. Post-process against features — if `speech_rate < 90` and `mean_length_of_run < 4`, cap fluency at band 3 regardless of model output.

Rubric instruction explicitly directs scoring of intelligibility, never accent conformity.

### 5.5 CIR composite

```
CIR = 0.35·speaking_fluency + 0.25·listening
    + 0.20·writing_tone + 0.20·situational_task_fulfilment
```

---

## 6. Screens

| Screen | Contents |
|---|---|
| **Start** | Name entry, recording-consent notice, Begin |
| **Device check** | Mic permission → 5 s record → playback → confirm. **Blocking gate** |
| **Test** | One item per screen, visible timer, explicit Next. Speaking: 20 s prep → record → single playback → submit, no re-record |
| **Submitting** | "Scoring your responses — about 30 seconds", progress indicator |
| **Report** | Overall band · radar chart (5 axes) · per-dimension bands · **audio player beside the score it produced** · transcript with judge justification |
| **Recruiter** | Read-only table: name, overall band, 5 sub-bands, timestamp, report link. Sortable by band |

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
Judge      Ollama, qwen2.5:3b-instruct, schema-constrained via format=
Deps       fastapi uvicorn sqlmodel faster-whisper ollama pydantic
           python-multipart
           + ffmpeg on PATH (decodes webm)
           + Ollama installed, model pulled ahead of time
```

### Data model — three tables

```python
Attempt   id(uuid) · name · status(in_progress|scoring|done) · created_at
Response  id · attempt_id · item_id · text? · audio_path? · duration_ms?
Score     id · attempt_id · dimension · band · evidence(JSON)
```

`evidence` holds transcript, feature dict, and judge justification. It is what the report renders and what makes D3 achievable.

### API surface — seven endpoints

```
POST /api/attempts                  → create, returns attempt_id
GET  /api/items                     → serve items.json
POST /api/attempts/{id}/response    → text response (MCQ / writing)
POST /api/attempts/{id}/audio       → multipart audio + item_id
POST /api/attempts/{id}/submit      → triggers background scoring
GET  /api/attempts/{id}/report      → bands + evidence
GET  /api/attempts                  → recruiter list
```

---

## 8. Demo narrative (5 minutes)

1. Recruiter table sorted by band — *"here's a recruiter with a pipeline"*
2. Open a **low-band** report → **play the audio** → point at the fluency number and its justification
3. Open a **high-band** report on the same items → contrast
4. Take a 90-second speaking item live → score appears
5. Roadmap in one line: item bank, bulk upload, validation study against expert raters

Step 2 is the demo. The rest is framing.

---

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Whisper and Ollama contend for RAM → stall | **High if concurrent** | Strictly sequential pipeline |
| Live recording fails at the venue | ~30% | Seeded attempts — pivot to recruiter table without breaking stride |
| Ollama unloads model between rehearsal and demo | Medium | `keep_alive="30m"` + warm-up call |
| Judge latency blows the 30 s target | Medium | Drop to 3B; cap `num_predict`; measure Day 2, not Day 3 |
| Small model emits schema-valid nonsense bands | Medium | Interpreted features in prompt + sanity clamp |
| Whisper WER poor on the demoer's accent | Medium | Test Day 2 morning; fall back to `medium` |
| Feature thresholds mis-calibrated → everyone scores 4 | Medium | Record 3 deliberately different-proficiency samples Day 2 and tune |
| Scoring slower than 30 s | Medium | Measure Day 2; drop Whisper to `base` if needed |

---

## 10. What this demo explicitly does not claim

Say these before someone finds them:

- Scores are **not** validated against human raters — that's the Phase 4 study, n = 200
- **Not** CEFR-aligned; CEFR-*referenced* descriptors only
- Pronunciation is a proxy (read-aloud WER), not phoneme-level GOP
- Item pool is 9 items, not the 200+ a real deployment needs

Naming a limitation before being caught reads as engineering judgment. Being caught hiding one costs the whole demo.
