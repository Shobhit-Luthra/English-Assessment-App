# English Proficiency Assessment Platform — Product PRD (v1)

**Scope:** the full product. The demo (see `02-demo-prd.md`) is a deliberate subset of this.
**Target buyer:** BPO / contact-center / staffing teams hiring frontline English-speaking agents at volume in India.

---

## 1. Problem Statement

BPO and contact-center recruiters screen thousands of candidates per month for frontline English roles. Screening today is done by human telephonic rounds — expensive, slow, inconsistent between interviewers, impossible to audit.

**The job to be done:** given 500 candidate phone numbers, return a ranked, defensible English-readiness score for each within 24 hours, at a per-candidate cost low enough to run on the entire top-of-funnel.

---

## 2. Goals & Non-Goals

### Goals

| # | Goal | Metric |
|---|---|---|
| G1 | Score five English competencies automatically | All five produce a band score |
| G2 | Machine scores agree with expert human raters | Pearson r ≥ 0.75, QWK ≥ 0.65 on holdout |
| G3 | Handle bulk hiring drives | 500/day sustained, 2,000/day burst |
| G4 | Fast turnaround | Objective < 2 s; full report < 120 s (p95) |
| G5 | Work on low-end Android + 4G | Complete on 2 GB RAM phone at 1 Mbps up |
| G6 | Multi-tenant from day one | Zero cross-tenant leakage in access tests |
| G7 | No accent bias | No significant score gap by region on matched-proficiency audio |

### Non-Goals (v1)

Live conversational role-play · video interviewing · ATS integrations (CSV export instead) · non-English languages · native mobile apps · IRT-based adaptive selection · full remote proctoring with ID verification.

---

## 3. Personas

**Recruiter / TA Ops** — creates drives, bulk-uploads candidates, sends invites, monitors completion, downloads shortlists. Non-technical, lives in a spreadsheet.

**Candidate** — 18–26, tier-2/3 city, Android phone, variable bandwidth, likely first proctored online test. Needs a forgiving UI and a mic check that works before anything is at stake.

**Hiring Manager / Client QA** — reads reports, spot-checks audio, challenges scores. Needs the recording next to the score it earned.

**Tenant Admin** — manages users, sets per-role thresholds, monitors quota.

---

## 4. Assessment Blueprint

### A — Grammar & Vocabulary (objective)
20 items / 8 min, drawn from a 200+ pool. Error identification, sentence completion, contextual synonym, preposition and article usage.

### B — Listening & Comprehension (objective)
12 items / 12 min. Simulated customer calls (billing dispute, delivery complaint, technical issue) in mixed accents — Indian, American, British, Australian, because that is the real job. Main-idea, detail, and inference MCQs plus 3 short-answer note-taking items scored semantically.

### C — Reading & Writing (hybrid)
Reading: 2 passages (policy snippet, customer email thread) → 8 MCQs.
Writing: email reply to a complaint (~120 words) + call summary in chat notes (~60 words).
Dimensions: task fulfilment, grammar accuracy, vocabulary range, organisation, tone.

### D — Spoken English (the core)

| Type | Count | Duration | Purpose |
|---|---|---|---|
| Read-aloud | 3 | 30 s | Known reference text → reliable alignment → cleanest pronunciation signal |
| Repeat sentence | 5 | 15 s | Elicited imitation; correlates strongly with overall proficiency |
| Picture/situation describe | 2 | 45 s | Fluency and vocabulary range without conversational scaffolding |
| Situational response | 3 | 60 s | Job-relevant spontaneous speech |

### E — Customer Interaction Readiness (derived in v1)

```
CIR = 0.35·(speaking fluency + coherence)
    + 0.25·(listening accuracy)
    + 0.20·(writing tone appropriateness)
    + 0.20·(situational-response task fulfilment)
```

**v2:** replace with a live LLM-driven role-play (4–6 turns handling a simulated irate customer). Deferred because it requires streaming ASR + streaming TTS latency work orthogonal to the core scoring problem.

**Total candidate time: ~45 minutes.**

---

## 5. Scoring Architecture

### 5.1 Pipeline

```
audio (webm/opus)
   ↓ ffmpeg → 16 kHz mono wav
faster-whisper  ──────────────→ transcript
   ↓                                  ↓
WhisperX alignment            LanguageTool → grammar error density
   ↓                                  ↓
word + phoneme timestamps     sentence-transformers → prompt relevance
   ↓                                  ↓
wav2vec2 phoneme posteriors   CEFR wordlist → vocabulary range
   ↓                                  ↓
GOP scores per phoneme        LLM rubric judge → coherence, task fulfilment
   ↓                                  ↓
   └──────────→ FEATURE VECTOR ←──────┘
                      ↓
              LightGBM regressor
                      ↓
              Band 1–6 + sub-scores + evidence
```

### 5.2 Features

**Fluency** (from word timestamps): speech rate, articulation rate, silent pause count and mean duration, pauses per 100 words, mean length of run, filled-pause rate, repetition/false-start rate, phonation-time ratio.

**Pronunciation:** mean and 10th-percentile GOP, proportion of low-confidence phonemes, read-aloud WER, vowel/consonant duration variability.

**Lexical:** MTLD (length-corrected type-token ratio), proportion of B2+ CEFR tokens, lexical density.

**Grammatical:** errors per 100 words by category, mean clause length, subordination ratio.

**Semantic:** prompt-relevance cosine similarity, LLM rubric scores for coherence and task fulfilment.

### 5.3 Cold start (no labels)

**Stage 0** — rubric-weighted heuristic. Internal only.
**Stage 1** — LLM-as-judge with 6-band descriptors, deterministic settings, structured output, median of 3 runs.
**Stage 2** — 200-response calibration set, 2 trained human raters. Compute human-human IRR (your ceiling), then machine-human Pearson r, QWK, mean absolute band error.
**Stage 3** — LightGBM on the feature vector at 500+ labels. LLM judge becomes one input feature, not the answer. Report feature importances.
**Stage 4** — bias audit across region, gender, L1 on proficiency-matched samples.

### 5.4 Reporting scale

6 bands mapped to CEFR-style descriptors (A1 → C1). Claim **"CEFR-referenced,"** never "CEFR-aligned," without a formal alignment study.

---

## 6. Data Model

Every table carries `tenant_id`, enforced via PostgreSQL Row-Level Security so a forgotten `WHERE` cannot leak data.

```
tenants      id, name, plan, quota_monthly, quota_used
users        id, tenant_id, email, role[admin|recruiter|manager]
drives       id, tenant_id, name, role_profile, pass_threshold, blueprint_id
blueprints   id, tenant_id, sections[jsonb], weights[jsonb], time_limits
items        id, tenant_id|null, section, type, payload[jsonb],
             answer_key[jsonb], difficulty_b, exposure_count, active
item_pools   id, blueprint_section, item_ids[]
candidates   id, tenant_id, name, phone, email, external_ref
attempts     id, drive_id, candidate_id, status, started_at, submitted_at,
             invite_token, integrity_flags[jsonb]
responses    id, attempt_id, item_id, response_type, raw_text,
             audio_uri, duration_ms, submitted_at
features     id, response_id, feature_vector[jsonb], asr_transcript,
             alignment[jsonb], model_versions[jsonb]
scores       id, response_id|attempt_id, dimension, raw, band,
             confidence, scorer_version, evidence[jsonb]
reports      id, attempt_id, overall_band, section_bands[jsonb],
             cir_score, recommendation, generated_at, pdf_uri
audit_log    id, tenant_id, actor_id, action, target, at
```

`model_versions` on every feature row exists so you can explain why a candidate scored 4 in January and their twin scored 5 in July. Score reproducibility is an enterprise requirement.

---

## 7. Architecture

```
Candidate PWA ──┐
                ├──► FastAPI (app tier) ──► Postgres
Recruiter UI ───┘         │
                          ├──► Redis + RQ ──► Scoring Worker (GPU T4)
                          │                    whisper · wav2vec2
                          │                    LanguageTool · LightGBM
                          └──► R2 / S3 (audio blobs)
```

**Audio upload path:** MediaRecorder → opus ~24 kbps → presigned PUT direct to R2 (audio never transits the app server) → chunked with resume → client posts object key → job enqueued. Failed uploads persist in IndexedDB and retry in background.

**Capacity:** 500 candidates/day × ~5 min speaking ≈ 42 audio-hours/day. faster-whisper medium on a T4 runs ~8–12× realtime batched → ~4–5 GPU-hours/day. One T4 covers v1. Queue depth is the scaling signal.

---

## 8. Integrity — "integrity-lite" v1

**In:** randomised draw from pools ≥ 5× items served · per-item exposure counting with auto-retirement · single-use session-bound invite tokens · tab-visibility logging (flag, don't auto-fail) · response-time anomaly flags · speaker-embedding consistency check across speaking items.

**Out:** face detection, ID verification, screen recording, browser lockdown.

---

## 9. Compliance & Ethics

- Explicit pre-recording consent in plain language with stated retention
- DPDP Act 2023: voice recordings are personal data — purpose limitation, 180-day audio retention then deletion (scores retained), deletion request path
- Data residency in an India region if selling PAN-India enterprise
- Quarterly four-fifths-rule check on pass rates across available demographic slices
- Every score ships with evidence. No black-box bands

---

## 10. 12-Week Plan

| Phase | Weeks | Exit criterion |
|---|---|---|
| 0 · Blueprint & item bank | 1–2 | A complete paper test a human could administer and score |
| 1 · Thin end-to-end slice | 3–4 | Create drive → take grammar test on phone → see score |
| 2 · Audio capture & ASR | 5–6 | Record over 4G → transcript with word timings in Postgres |
| 3 · Scoring engine v1 | 7–8 | Any spoken response yields a full feature vector and band |
| 4 · Calibration & validation | 9 | A defensible number: "r = 0.78 vs expert raters, n = 200" |
| 5 · Recruiter console | 10–11 | An untrained recruiter runs a 50-candidate drive unaided |
| 6 · Scale & integrity | 12 | Demoable to a real buyer at 2,000 concurrent |

Phase 2 carries a mandatory early check: run 20 Indian-accented samples through faster-whisper and measure WER. Learn it in week 5, not week 10.

---

## 11. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| ASR WER high on Indian-accented English | Scores are noise | Validate Phase 2. Fallback: fine-tune on IndicSUPERB/Svarah, or hosted ASR with better coverage |
| Human-human IRR < 0.7 | No ceiling to aim at | Tighter rubric descriptors; train raters on 20 anchor samples first |
| GOP pipeline too complex | Pronunciation unscored | Ship fluency + read-aloud WER as proxy; add GOP in v1.1 |
| Item leakage | Scores stop discriminating | Pools ≥ 5× served, exposure retirement, from day one |
| Upload failures on poor networks | Candidate drop-off | IndexedDB buffering, background retry, resumable upload |
| LLM judge cost at scale | Unit economics break | Judge open-ended items only; cache by prompt+transcript hash; migrate to LightGBM |
| Accent bias | Legal and ethical failure | Phase 4 bias audit; intelligibility-not-conformity rubric wording |

---

## 12. Definition of Done (v1)

A recruiter uploads 500 candidates Monday morning. By Monday evening they have a ranked list across five dimensions, can play any candidate's audio next to the score it earned, export the top 80 to CSV, and answer their client's *"how do you know this is accurate?"* with a validation report showing r = 0.78 against expert human raters.
