# English Proficiency Assessment Platform — PRD & Implementation Plan

**Working name:** VoxHire (placeholder)
**Version:** 0.1 — pre-build specification
**Owner:** Shobhit Luthra
**Target buyer:** BPO / contact-center / customer-service staffing teams hiring frontline agents at volume in India

---

## 1. Problem Statement

BPO and contact-center recruiters screen thousands of candidates per month for frontline English-speaking roles. Screening today is done by human telephonic rounds — expensive, slow, inconsistent between interviewers, and impossible to audit.

**The job to be done:** given a list of 500 candidate phone numbers, return a ranked, defensible English-readiness score for each within 24 hours, at a per-candidate cost low enough to run on the entire top-of-funnel.

---

## 2. Goals & Non-Goals

### Goals (v1)

| # | Goal | Success metric |
|---|---|---|
| G1 | Score five English competencies automatically | All five produce a band score on a defined scale |
| G2 | Machine scores agree with expert human raters | Pearson r ≥ 0.75, QWK ≥ 0.65 on holdout set |
| G3 | Handle bulk hiring drives | 500 candidates/day sustained, 2,000/day burst |
| G4 | Fast turnaround | Objective score < 2 s; full report < 120 s (p95) |
| G5 | Work on low-end Android + 4G | Complete a test on a 2GB RAM phone at 1 Mbps upload |
| G6 | Multi-tenant from day one | Zero cross-tenant data leakage in access-control tests |
| G7 | No accent bias | No statistically significant score gap by region on matched-proficiency audio |

### Non-Goals (explicitly out of v1)

- Live conversational role-play simulation (deferred to v2)
- Video interviewing / recorded video responses
- ATS integrations (Naukri, Darwinbox, Keka) — CSV export instead
- Languages other than English
- Mobile native apps (PWA only)
- Adaptive/IRT-based item selection (v2)
- Full remote proctoring with identity verification (see §9 for the v1 "integrity-lite" decision)

---

## 3. Personas

**P1 — Recruiter / TA Ops (primary buyer-user)**
Creates a hiring drive, bulk-uploads candidates via CSV, sends invite links over SMS/WhatsApp, monitors completion, downloads a ranked shortlist. Not technical. Lives in a spreadsheet.

**P2 — Candidate**
18–26, tier-2/tier-3 city, Android phone, variable bandwidth, may never have taken an online proctored test. Anxious. Needs an unambiguous, forgiving UI with a mic check that works before anything is at stake.

**P3 — Hiring Manager / Client QA**
Reads individual reports, spot-checks audio, challenges scores. Needs to hear the recording next to the score that was given for it.

**P4 — Tenant Admin**
Manages users, sets pass thresholds per role, sees usage against plan quota.

---

## 4. The Assessment Blueprint

This is the product's spine. Get this wrong and no amount of engineering saves it.

### Section A — Grammar & Vocabulary (auto-scored, objective)
- 20 items, 8 minutes, drawn randomly from a pool of 200+
- Item types: error identification, sentence completion, contextual synonym, preposition/article usage
- Scoring: raw correct → scaled band
- **Build note:** this is your item-bank engine. Everything else reuses it.

### Section B — Listening & Comprehension (auto-scored, objective)
- 12 items, 12 minutes
- Audio prompts: simulated customer calls (billing dispute, delivery complaint, technical issue), delivered in mixed accents — Indian, American, British, Australian — because that's the real job
- Item types: main-idea MCQ, specific-detail MCQ, inference MCQ, plus 3 short-answer "note-taking" items (scored semantically, not by exact string)
- **Build note:** short-answer scoring uses sentence embeddings vs. reference answers with a similarity threshold, backstopped by the LLM judge on borderline cases.

### Section C — Reading & Writing (hybrid scoring)
- Reading: 2 passages (a policy snippet, a customer email thread) → 8 comprehension MCQs
- Writing: 2 constructed responses
  - Task 1: write a customer email reply to a given complaint (~120 words)
  - Task 2: summarise a call in chat-style notes (~60 words)
- Scoring dimensions: task fulfilment, grammar accuracy, vocabulary range, organisation, tone appropriateness
- **Build note:** LanguageTool for mechanical error density; LLM rubric judge for the rest.

### Section D — Spoken English (the hard one)
Four item types, escalating in openness:

| Item type | Purpose | Why this type |
|---|---|---|
| D1. Read-aloud (3 items) | Pronunciation, clarity | Reference text is known → forced alignment is reliable → cleanest pronunciation signal you'll get |
| D2. Repeat sentence (5 items) | Working memory, phonology | Classic elicited-imitation; correlates surprisingly well with overall proficiency |
| D3. Picture/situation describe (2 items, 45 s) | Fluency, vocabulary range | Open speech without conversational scaffolding |
| D4. Situational response (3 items, 60 s) | Job-relevant spontaneous speech | "A customer says their order is 5 days late. Respond." |

### Section E — Customer Interaction Readiness (derived in v1)

**v1:** a weighted composite, not a separate test.

```
CIR = 0.35·(Spoken fluency + coherence)
    + 0.25·(Listening accuracy)
    + 0.20·(Writing tone appropriateness)
    + 0.20·(Situational-response task fulfilment from D4)
```

**v2:** replace with a live LLM-driven role-play where the candidate handles a simulated irate customer over 4–6 turns.

> **Scope decision recorded:** building a real interaction simulator in v1 doubles the timeline and requires latency work (streaming ASR + streaming TTS) that is orthogonal to the core scoring problem. Defer it.

### Total candidate time: ~45 minutes

---

## 5. Scoring Architecture

### 5.1 Pipeline for a single spoken response

```
audio (webm/opus)
   ↓ transcode → 16kHz mono wav (ffmpeg)
   ↓
faster-whisper  ──────────────→ transcript
   ↓                                  ↓
WhisperX alignment            LanguageTool → grammar error density
   ↓                                  ↓
word + phoneme timestamps     sentence-transformers → prompt relevance
   ↓                                  ↓
wav2vec2 phoneme posteriors   CEFR wordlist mapping → vocab range
   ↓                                  ↓
GOP scores per phoneme        Claude rubric judge → coherence, task fulfilment
   ↓                                  ↓
   └──────────→ FEATURE VECTOR ←──────┘
                      ↓
              LightGBM regressor (or rubric-weighted sum pre-calibration)
                      ↓
              Band score 1–6 + sub-scores + evidence
```

### 5.2 Feature inventory

**Fluency features** (from word timestamps — cheap, high signal):
- Speech rate (words/min) and articulation rate (words/min excluding pauses)
- Silent pause count, mean pause duration, pauses per 100 words
- Mean length of run (words between pauses ≥ 250 ms)
- Filled-pause rate (`um`, `uh`, `like`, `actually` as disfluency)
- Repetition and false-start rate
- Phonation-time ratio (speaking time ÷ total time)

**Pronunciation features:**
- Mean and 10th-percentile GOP across phonemes
- Proportion of phonemes below a confidence threshold
- For read-aloud only: word error rate vs. reference text
- Vowel/consonant duration variability

**Lexical features:**
- Type-token ratio (length-corrected — use MTLD, plain TTR is length-biased)
- Proportion of tokens in CEFR B2+ bands
- Lexical density (content words ÷ total words)

**Grammatical features:**
- Errors per 100 words by category (agreement, tense, article, preposition)
- Mean clause length, subordination ratio

**Semantic / discourse features:**
- Cosine similarity to prompt embedding (relevance)
- LLM rubric scores for coherence, task fulfilment, tone

### 5.3 Cold-start strategy (you have no labels)

**Stage 0 — Rubric-weighted heuristic.** Hand-set weights from the applied-linguistics literature. Ship this to yourself only, never to a customer.

**Stage 1 — LLM-as-judge.** Give Claude the transcript, the computed acoustic features, and a 6-band descriptor rubric. Ask for a band + justification per dimension. Deterministic settings, structured JSON output, run 3× and take the median to reduce variance.

**Stage 2 — Human calibration set.** Collect 200 spoken responses. Have 2 trained raters score each against your rubric (get an English-language-teaching person; this is worth paying for). Compute:
- Inter-rater reliability between the two humans (your ceiling — if humans only agree at r = 0.7, your model cannot beat 0.7)
- Machine vs. human-mean agreement: Pearson r, QWK, mean absolute error in bands

**Stage 3 — Supervised model.** With 500+ labels, train LightGBM on the feature vector. Keep the LLM judge as one input feature, not the whole answer. Report feature importances — buyers love an explainable score.

**Stage 4 — Bias audit.** Slice score distributions by candidate region, gender, and first language on proficiency-matched samples. Any systematic gap is a bug, not a finding.

### 5.4 Score reporting scale

Report on a 6-band scale mapped to CEFR-style descriptors (A1 → C1). Do **not** claim official CEFR alignment without a formal alignment study — that's a legal/marketing claim, not an engineering one. Use "CEFR-referenced."

---

## 6. Data Model (core tables)

Every table carries `tenant_id`. Every query filters by it. Enforce with PostgreSQL Row-Level Security so a forgotten `WHERE` clause can't leak data.

```
tenants          id, name, plan, quota_monthly, quota_used
users            id, tenant_id, email, role[admin|recruiter|manager]
drives           id, tenant_id, name, role_profile, pass_threshold, blueprint_id
blueprints       id, tenant_id, sections[jsonb], weights[jsonb], time_limits
items            id, tenant_id|null, section, type, payload[jsonb],
                 answer_key[jsonb], difficulty_b, exposure_count, active
item_pools       id, blueprint_section, item_ids[]
candidates       id, tenant_id, name, phone, email, external_ref
attempts         id, drive_id, candidate_id, status, started_at,
                 submitted_at, invite_token, integrity_flags[jsonb]
responses        id, attempt_id, item_id, response_type,
                 raw_text, audio_uri, duration_ms, submitted_at
features         id, response_id, feature_vector[jsonb], asr_transcript,
                 alignment[jsonb], model_versions[jsonb]
scores           id, response_id|attempt_id, dimension, raw, band,
                 confidence, scorer_version, evidence[jsonb]
reports          id, attempt_id, overall_band, section_bands[jsonb],
                 cir_score, recommendation, generated_at, pdf_uri
audit_log        id, tenant_id, actor_id, action, target, at
```

**Why `model_versions` on every feature row:** when you improve the ASR model in month 6, you must be able to explain why a candidate scored 4 in January and their twin scored 5 in July. Score reproducibility is an enterprise requirement.

---

## 7. Architecture

```
┌──────────────┐         ┌──────────────┐
│ Candidate    │         │ Recruiter    │
│ PWA (mobile) │         │ Console      │
└──────┬───────┘         └──────┬───────┘
       │                        │
       └────────┬───────────────┘
                ▼
        ┌───────────────┐
        │  FastAPI      │  auth, drives, items, attempts,
        │  (app tier)   │  presigned upload URLs, reports
        └───┬───────┬───┘
            │       │
   ┌────────▼──┐  ┌─▼──────────┐
   │ Postgres  │  │ Redis + RQ │
   └───────────┘  └─┬──────────┘
                    │  job: score_response(response_id)
            ┌───────▼──────────┐      ┌──────────────┐
            │ Scoring Worker   │◄────►│ R2 / S3      │
            │ (GPU: T4)        │      │ audio blobs  │
            │ whisper·wav2vec2 │      └──────────────┘
            │ LanguageTool·LGB │
            └───────┬──────────┘
                    │
              ┌─────▼──────┐
              │ Claude API │  rubric judge
              └────────────┘
```

**Audio upload path (critical for 4G):**
1. Browser records with `MediaRecorder` → `audio/webm;codecs=opus` at ~24 kbps mono
2. Client requests a presigned PUT URL from the API — audio never transits your app server
3. Upload directly to R2, chunked, with retry-on-failure and resume
4. Client posts the object key back; API enqueues the scoring job
5. If upload fails, audio stays in IndexedDB and retries in the background — the candidate is never blocked

**Capacity math (validate these numbers yourself early):**
- 500 candidates/day × ~5 min speaking = ~42 hours of audio/day
- faster-whisper medium on a T4 runs ~8–12× realtime with batching → ~4–5 GPU-hours/day
- One T4 comfortably covers v1 volume; queue depth is your scaling signal, not CPU

---

## 8. User Flows

### Recruiter: run a drive
1. Create drive → pick blueprint → set pass threshold
2. Upload CSV (name, phone, email) → validation preview → confirm
3. System generates single-use invite tokens; recruiter downloads links or triggers SMS
4. Live dashboard: invited / started / completed / flagged
5. Results table sortable by band, filterable by threshold → export CSV or bulk PDF

### Candidate: take the test
1. Open link on phone → consent screen (recording notice, data retention) → OTP verify
2. **Device check** — mic permission, 5-second record-and-playback, bandwidth probe. Blocking gate. Most support tickets die here if you build it well.
3. Section-by-section, one item per screen, visible timer, explicit "next" (no auto-advance surprises)
4. Speaking items: 20 s prep → record → single playback → submit. No re-record.
5. Submit → "we're scoring, this takes about a minute" → confirmation

### Manager: review a candidate
Report shows overall band, five sub-bands, the CIR composite, per-dimension evidence (the actual transcript with flagged grammar errors highlighted, the audio player, the fluency chart), and a recommendation against the drive threshold.

---

## 9. Integrity (the "integrity-lite" v1 decision)

Full proctoring is a separate product. But bulk hiring leaks items to WhatsApp groups within a week, so v1 needs the cheap 80%:

**In v1:**
- Randomised item draw from pools ≥ 5× the items served
- Exposure counting per item; auto-retire above a threshold
- Single-use invite tokens, bound to one session
- Tab-visibility change logging (log it, flag it, don't auto-fail)
- Response-time anomaly flags (impossibly fast objective sections)
- Voice consistency check across speaking items — is it the same speaker throughout? (speaker embedding cosine similarity; cheap, catches the most common cheat)

**Not in v1:** face detection, ID verification, screen recording, browser lockdown.

---

## 10. Compliance & Ethics

- **Consent:** explicit, before recording, in plain language, with retention period stated
- **DPDP Act 2023 (India):** voice recordings are personal data. Purpose limitation, stated retention (recommend 180 days then delete audio, keep scores), and a deletion request path
- **Data residency:** if you promise PAN-India enterprise sales, host in an India region (AWS ap-south-1 / Azure Central India). Say so in the sales deck
- **Adverse impact monitoring:** run the four-fifths rule check on pass rates across available demographic slices. Log it quarterly
- **Score transparency:** every score ships with evidence. No black-box band numbers

---

## 11. Implementation Plan — 12 weeks

Assumes part-time solo work. Each phase ends in something demoable.

---

### Phase 0 — Blueprint & item bank (Week 1–2) · *unsexy, decisive*
- Write the 6-band rubric with descriptors for each dimension
- Author or source 200 grammar/vocab items, 12 listening scenarios with audio, 4 reading passages, 13 speaking prompts
- Define the blueprint JSON schema
- **Exit:** a complete paper version of the test that a human could administer and score

> Do not skip this to start coding. An engineering-perfect platform serving bad items produces bad scores.

---

### Phase 1 — Thin end-to-end slice (Week 3–4)
- FastAPI + Postgres + Next.js skeleton, JWT auth, tenant scaffolding with RLS
- Item bank CRUD, blueprint assembly, randomised draw
- Candidate flow for Section A only, auto-scored
- **Exit:** you can create a drive, send yourself a link, take a 20-item grammar test on your phone, and see a score

---

### Phase 2 — Audio capture & ASR (Week 5–6)
- `MediaRecorder` capture, device check gate, IndexedDB buffering, presigned chunked upload with retry
- Redis + RQ, GPU worker container
- faster-whisper transcription + WhisperX alignment → store transcript and word timings
- **Exit:** record on a phone over 4G, transcript with word timestamps lands in Postgres

*Validate here:* run 20 Indian-accented samples through faster-whisper and eyeball the WER. If it's bad, you learn now, not in week 10.

---

### Phase 3 — Scoring engine v1 (Week 7–8)
- Fluency feature extractor from timestamps
- wav2vec2 phoneme model + GOP computation
- LanguageTool integration, CEFR wordlist mapping, embedding relevance
- Claude rubric judge with structured JSON output
- Heuristic weighted combination → band score
- **Exit:** any spoken response produces a full feature vector and a band with evidence

---

### Phase 4 — Calibration & validation (Week 9) · *the credibility phase*
- Collect 200 real spoken responses (classmates, campus, a small paid pool)
- 2 human raters score against the rubric
- Compute human-human IRR, then machine-human r and QWK
- Tune weights; train LightGBM if label count allows
- Write the validation report
- **Exit:** a number you can put on a slide, e.g. "r = 0.78 against expert raters, n = 200"

---

### Phase 5 — Recruiter console & reporting (Week 10–11)
- CSV bulk upload with validation preview
- Drive dashboard, live status, invite generation
- Individual report page: bands, evidence, audio playback, transcript with error highlights
- PDF report generation, CSV bulk export
- **Exit:** a recruiter who has never seen the product can run a 50-candidate drive unaided

---

### Phase 6 — Scale hardening & integrity (Week 12)
- Load test to 2,000 concurrent attempts (Locust)
- Item exposure tracking and rotation
- Voice consistency check, tab-switch logging, timing anomaly flags
- Retention job (auto-delete audio at 180 days)
- Sentry, structured logging, queue-depth alerting
- **Exit:** demoable to a real buyer

---

## 12. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| ASR WER too high on Indian-accented English | Scores are noise | Validate in Phase 2, not Phase 10. Fallback: fine-tune Whisper on IndicSUPERB/Svarah, or route to a hosted ASR with better Indian coverage |
| Human-human IRR is low (< 0.7) | No ceiling to aim at | Tighten rubric descriptors, train raters on 20 anchor samples first |
| GOP pipeline too complex to get working | Pronunciation dimension is unscored | Ship v1 with fluency + WER-on-read-aloud as pronunciation proxy; add GOP in v1.1 |
| Item leakage | Scores stop discriminating | Pools ≥ 5× served size, exposure retirement, from day one |
| Audio upload failures on poor networks | Candidate drop-off | IndexedDB buffering + background retry + resumable upload |
| LLM judge cost at scale | Unit economics break | Judge only open-ended items; cache by prompt+transcript hash; move to LightGBM once labelled |
| Accent bias in scores | Legal and ethical failure, unsellable | Bias audit in Phase 4, intelligibility-not-conformity rubric wording |

---

## 13. What "done" looks like for v1

A recruiter uploads 500 candidates on Monday morning. By Monday evening they have a ranked list with band scores across five dimensions, can play any candidate's audio next to the score it earned, export the top 80 to CSV, and answer their client's "how do you know this is accurate?" with a validation report showing r = 0.78 against expert human raters.

Nothing more. Nothing less.
